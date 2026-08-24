import unittest

from scripts import player_labs


class PlayerLabsTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {"build_id": "abcdef123456"}
        self.snapshot = {
            "dataset_version": "test-1", "classification": "Verified community data",
            "source": {"commit": "a" * 40},
            "coverage": {"move_pools": "snapshot only", "evolution_candy_and_special_requirements": "synthetic test"},
            "mechanics": {"cp_multiplier_levels": {"20.0": 0.5974}},
            "entries": [
                {"dex": 1, "species_id": "bulbasaur", "display_name": "Bulbasaur", "base_name": "Bulbasaur", "form_key": "normal", "released": True, "types": ["grass", "poison"], "base_stats": {"attack": 118, "defense": 111, "stamina": 128}, "moves": {"fast": ["VINE_WHIP"], "charged": ["SLUDGE_BOMB"], "elite_or_exclusive": [], "legacy": []}, "family": {"id": "family-bulbasaur", "evolution_species_ids": ["ivysaur"], "evolution_candy_cost": 25, "special_requirements": {}}, "transformation": {"kind": None}},
                {"dex": 2, "species_id": "ivysaur", "display_name": "Ivysaur", "base_name": "Ivysaur", "form_key": "normal", "released": True, "types": ["grass", "poison"], "base_stats": {"attack": 151, "defense": 143, "stamina": 155}, "moves": {"fast": ["VINE_WHIP"], "charged": ["SLUDGE_BOMB"], "elite_or_exclusive": ["FRENZY_PLANT"], "legacy": []}, "family": {"id": "family-bulbasaur", "evolution_species_ids": [], "evolution_candy_cost": 100, "special_requirements": {}}, "transformation": {"kind": None}},
                {"dex": 3, "species_id": "venusaur_mega", "display_name": "Venusaur (Mega)", "base_name": "Venusaur", "form_key": "mega", "released": True, "types": ["grass", "poison"], "base_stats": {"attack": 241, "defense": 246, "stamina": 190}, "moves": {"fast": [], "charged": [], "elite_or_exclusive": [], "legacy": []}, "family": {"id": "family-bulbasaur", "evolution_species_ids": [], "evolution_candy_cost": None, "special_requirements": None}, "transformation": {"kind": "mega"}},
            ],
        }
        self.records = [{
            "identity": {"record_id": "rec-1"}, "pokemon_number": 1, "name": "Bulbasaur", "form": None, "cp": 637,
            "ivs": {"attack": 15, "defense": 14, "stamina": 13, "average_percent": 93.3, "total": 42},
            "level": {"minimum": 20, "maximum": 20}, "moves": {"fast": "Vine Whip", "charged": "Sludge Bomb", "charged_second": None},
            "status": {"shadow_purified": "normal", "favorite": True},
            "pvp": {"great": {"rank_percent": 97.2, "rank_number": 42}, "ultra": {}, "little": {}},
        }]
        self.by_id, self.by_key = player_labs._knowledge_maps(self.snapshot)

    def test_naming_fixed_width_is_sortable(self):
        payload = player_labs.build_naming_studio(self.records, self.snapshot, self.by_key, self.manifest)
        naming = payload["records"][0]["naming"]
        self.assertEqual(naming["iv45"], "42")
        self.assertEqual(naming["ivpct3"], "093")
        self.assertEqual(naming["iv1000"], "0933")
        self.assertLess("009", "010")
        self.assertLess("0999", "1000")

    def test_gap_radar_excludes_transformations_and_unknown_attributes(self):
        payload = player_labs.build_gap_radar(self.records, self.snapshot, self.by_key, {}, self.manifest)
        self.assertEqual(payload["denominators"]["species"], 2)
        self.assertEqual(payload["species"][0]["species_state"], "yes")
        self.assertEqual(payload["species"][1]["species_state"], "missing")
        self.assertEqual(payload["attribute_support"]["shiny"], "browser-local-explicit-only")

    def test_roster_score_does_not_zero_missing_facts(self):
        full = player_labs._roster_score(self.records[0])
        sparse = player_labs._roster_score({"cp": 637, "ivs": {}, "level": {}, "moves": {}})
        self.assertIsNotNone(sparse["score"])
        self.assertGreater(sparse["score"], 0)
        self.assertLess(sparse["confidence"], full["confidence"])

    def test_evolution_projection_uses_exact_iv_and_level(self):
        target = self.by_id["ivysaur"]
        result = player_labs.project_cp(self.records[0], target, self.snapshot["mechanics"])
        self.assertEqual(result["state"], "projected")
        self.assertGreater(result["cp"], 0)
        blocked = player_labs.project_cp({**self.records[0], "level": {"minimum": 19, "maximum": 20}}, target, self.snapshot["mechanics"])
        self.assertEqual(blocked["state"], "blocked")

    def test_unknown_evolution_requirements_block_definitive_now(self):
        snapshot = {**self.snapshot, "entries": [dict(item) for item in self.snapshot["entries"]]}
        snapshot["entries"][0] = {**snapshot["entries"][0], "family": {**snapshot["entries"][0]["family"], "evolution_candy_cost": None, "special_requirements": None}}
        by_id, by_key = player_labs._knowledge_maps(snapshot)
        payload = player_labs.build_evolution_lab(self.records, snapshot, by_id, by_key, {}, self.manifest)
        self.assertFalse(payload["records"][0]["decision"]["definitive"])
        self.assertEqual(payload["records"][0]["decision"]["state"], "review")

    def test_stale_or_unprovided_move_window_is_not_current(self):
        payload = player_labs.build_evolution_lab(self.records, self.snapshot, self.by_id, self.by_key, {}, self.manifest)
        self.assertEqual(payload["records"][0]["current_exclusive_move_window"]["state"], "unavailable-or-unspecified")
        move = player_labs.build_move_lab(self.records, self.snapshot, self.by_key, {}, self.manifest)
        self.assertFalse(move["records"][0]["stable_pool_is_current_acquisition_proof"])

    def test_frustration_requires_fresh_explicit_flag(self):
        shadow = {**self.records[0], "moves": {"fast": "Vine Whip", "charged": "Frustration", "charged_second": None}, "status": {"shadow_purified": "shadow"}}
        payload = player_labs.build_move_lab([shadow], self.snapshot, self.by_key, {}, self.manifest)
        item = payload["records"][0]
        self.assertEqual(item["frustration"]["state"], "unavailable-or-unverified")
        self.assertFalse(item["purification"]["suggested_to_remove_frustration"])

    def test_fresh_explicit_move_fact_can_enable_current_signal(self):
        current = {"moves": {"snapshots": [{"provider": "test"}], "facts_by_dex": {"1": [{"fact": {"pokemon_number": 1, "elite_tm_available": True}, "provider": "test", "dataset_timestamp": "2026-08-23T00:00:00Z", "source_reference": "test"}]}, "global_facts": []}}
        move = player_labs.build_move_lab(self.records, self.snapshot, self.by_key, current, self.manifest)
        self.assertEqual(move["records"][0]["current_acquisition"]["state"], "fresh-explicit")


if __name__ == "__main__":
    unittest.main()
