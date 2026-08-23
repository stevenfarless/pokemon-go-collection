from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import advanced_labs


class AdvancedLabsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = {"build_id": "0123456789ab"}
        self.record = {
            "identity": {"record_id": "owned-1"},
            "pokemon_number": 1,
            "name": "Bulbasaur",
            "form": None,
            "cp": 1000,
            "hp": 100,
            "ivs": {
                "attack": 10,
                "defense": 10,
                "stamina": 10,
                "average_percent": 66.7,
                "is_hundo": False,
            },
            "level": {"minimum": 20.0, "maximum": 20.0},
            "moves": {"fast": "Vine Whip", "charged": "Power Whip", "charged_second": None},
            "status": {"shadow_purified": "normal"},
        }
        self.entry = {
            "dex": 1,
            "species_id": "bulbasaur",
            "display_name": "Bulbasaur",
            "form_key": "normal",
            "base_stats": {"attack": 118, "defense": 111, "stamina": 128},
            "types": ["grass", "poison"],
            "buddy_distance_km": 3,
            "family": {"id": "bulbasaur", "evolution_species_ids": ["ivysaur"]},
            "transformation": {"kind": None},
            "transformations": ["mega-bulbasaur"],
            "dynamax_eligibility": None,
            "gigantamax_eligibility": None,
        }
        self.mega_entry = {
            "dex": 1,
            "species_id": "mega-bulbasaur",
            "display_name": "Mega Bulbasaur",
            "form_key": "mega",
            "base_stats": {"attack": 200, "defense": 200, "stamina": 200},
            "types": ["grass", "poison"],
            "transformation": {"kind": "mega"},
        }
        self.snapshot = {
            "dataset_version": "test",
            "source": {"commit": "a" * 40},
            "mechanics": {
                "cp_formula": "test",
                "cp_multiplier_levels": {"20.0": 0.5974},
            },
        }
        self.by_key = {(1, "normal"): [self.entry]}
        self.by_id = {"bulbasaur": self.entry, "mega-bulbasaur": self.mega_entry}
        self.domains = {
            "mega-primal": {"status": "supported", "normalized_facts": ["reviewed"], "source_ids": ["mega-level"]},
            "max-pokemon": {"status": "supported", "normalized_facts": ["reviewed"], "source_ids": ["max-pokemon"]},
            "hyper-training": {"status": "supported", "normalized_facts": ["reviewed"], "source_ids": ["hyper-training"]},
            "buddy": {"status": "partial", "normalized_facts": [], "source_ids": []},
            "raids": {"status": "partial", "normalized_facts": [], "source_ids": []},
        }

    def test_hyper_cp_is_deterministic_and_warns_on_caps(self) -> None:
        first = advanced_labs.hyper_cp(
            self.record,
            self.entry,
            self.snapshot["mechanics"],
            {"attack": 15, "defense": 15, "stamina": 15},
        )
        second = advanced_labs.hyper_cp(
            self.record,
            self.entry,
            self.snapshot["mechanics"],
            {"attack": 15, "defense": 15, "stamina": 15},
        )
        self.assertEqual(first, second)
        self.assertEqual(first["state"], "projected")
        self.assertGreater(first["cp"], 0)
        self.assertEqual(first["target_ivs"], {"attack": 15, "defense": 15, "stamina": 15})

    def test_hyper_builder_blocks_shadow_and_hundo(self) -> None:
        shadow = json.loads(json.dumps(self.record))
        shadow["identity"]["record_id"] = "shadow"
        shadow["status"]["shadow_purified"] = "shadow"
        hundo = json.loads(json.dumps(self.record))
        hundo["identity"]["record_id"] = "hundo"
        hundo["ivs"].update({"attack": 15, "defense": 15, "stamina": 15, "is_hundo": True})
        payload = advanced_labs.build_hyper_lab(
            [shadow, hundo], self.snapshot, self.by_key, self.domains, self.manifest
        )
        by_id = {item["record_id"]: item for item in payload["records"]}
        self.assertEqual(by_id["shadow"]["eligibility"], "ineligible-shadow")
        self.assertEqual(by_id["hundo"]["eligibility"], "ineligible-already-4-star")
        self.assertIn("irreversible", by_id["hundo"]["irreversible_warning"].lower())

    def test_mega_capability_does_not_infer_exact_record_history(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            payload = advanced_labs.build_mega_lab(
                [self.record], self.snapshot, self.by_id, self.by_key, root, self.domains, self.manifest
            )
        self.assertEqual(len(payload["records"]), 1)
        item = payload["records"][0]
        self.assertTrue(item["capability"]["can_transform"])
        self.assertTrue(item["capability"]["does_not_prove_history"])
        self.assertEqual(item["local_state"]["first_mega_unlocked"], "unknown")
        self.assertEqual(item["local_state"]["mega_level"], "unknown")
        self.assertEqual(payload["current_matching"]["state"], "unavailable")

    def test_max_builder_never_infers_owned_max_state_from_capability(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            payload = advanced_labs.build_max_lab(
                [self.record], self.snapshot, self.by_key, root, self.domains, self.manifest
            )
        item = payload["records"][0]
        self.assertTrue(item["species_capability"]["does_not_prove_owned_max_state"])
        self.assertEqual(item["local_state"]["dynamax"], "unknown")
        self.assertEqual(item["local_state"]["gigantamax"], "unknown")
        self.assertFalse(payload["current_bosses"]["planning_allowed"])
        self.assertTrue(payload["battle_contract"]["normal_raid_rankings_are_not_max_simulations"])

    def test_raid_simulation_fails_closed_on_stale_current_boss(self) -> None:
        result = advanced_labs.simulate_raid(
            {"hp": 10000, "defense": 180, "timer_seconds": 300},
            [self.record],
            self.by_key,
            self.snapshot["mechanics"],
            source_freshness="stale",
        )
        self.assertEqual(result["state"], "blocked")
        self.assertIn("not fresh", result["reason"])

    def test_raid_simulation_uses_only_owned_records_and_group_size_improves_ttw(self) -> None:
        boss = {"hp": 10000, "defense": 180, "timer_seconds": 300}
        solo = advanced_labs.simulate_raid(
            boss, [self.record], self.by_key, self.snapshot["mechanics"], source_freshness="fresh", group_size=1
        )
        duo = advanced_labs.simulate_raid(
            boss, [self.record], self.by_key, self.snapshot["mechanics"], source_freshness="fresh", group_size=2
        )
        self.assertEqual(solo["state"], "simulated")
        self.assertEqual(solo["team"][0]["record_id"], "owned-1")
        self.assertTrue(all(item["owned"] for item in solo["team"]))
        self.assertLess(duo["estimated_ttw_seconds"], solo["estimated_ttw_seconds"])
        self.assertEqual(solo["model_version"], advanced_labs.RAID_MODEL_VERSION)
        self.assertIn("assumptions", solo)

    def test_buddy_queue_seeds_exact_records_and_known_distance(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "data" / "investments").mkdir(parents=True)
            (root / "data" / "investments" / "records.json").write_text(
                json.dumps({"records": []}), encoding="utf-8"
            )
            payload = advanced_labs.build_buddy_queue(
                [self.record], self.snapshot, self.by_key, root, self.domains, self.manifest
            )
        item = payload["candidates"][0]
        self.assertEqual(item["record_id"], "owned-1")
        self.assertEqual(item["buddy_distance_km"], 3)
        self.assertTrue(any(objective["kind"] == "evolution" for objective in item["objectives"]))
        self.assertIn("record=owned-1", item["action_pack"])


if __name__ == "__main__":
    unittest.main()
