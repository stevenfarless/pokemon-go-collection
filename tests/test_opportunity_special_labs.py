from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import opportunity_special_labs


class OpportunitySpecialLabsTests(unittest.TestCase):
    def write_json(self, root: Path, relative: str, payload: object) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def seed_personalization(self, root: Path) -> None:
        self.write_json(
            root,
            "data/reference/index.json",
            {
                "entries": [
                    {"dex": 1, "species_id": "bulbasaur", "display_name": "Bulbasaur", "form_key": "normal", "released": True, "types": ["grass", "poison"], "owned_count": 0, "owned_record_ids": [], "route": "reference.html?species=bulbasaur"},
                    {"dex": 2, "species_id": "ivysaur", "display_name": "Ivysaur", "form_key": "normal", "released": True, "types": ["grass", "poison"], "owned_count": 1, "owned_record_ids": ["owned-2"], "route": "reference.html?species=ivysaur"},
                ]
            },
        )
        self.write_json(
            root,
            "data/gap-radar.json",
            {
                "species": [
                    {"dex": 1, "species_id": "bulbasaur", "name": "Bulbasaur", "species_state": "missing", "owned_record_ids": []},
                    {"dex": 2, "species_id": "ivysaur", "name": "Ivysaur", "species_state": "yes", "owned_record_ids": ["owned-2"]},
                ],
                "forms": [
                    {"dex": 1, "species_id": "bulbasaur", "form_key": "normal", "state": "missing"},
                    {"dex": 2, "species_id": "ivysaur", "form_key": "normal", "state": "yes"},
                ],
            },
        )
        self.write_json(root, "data/roster-readiness.json", {"weakest": [{"type": "grass"}]})

    def test_stale_acquisition_snapshot_never_becomes_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.seed_personalization(root)
            path = "data/external/snapshots/events.json"
            self.write_json(root, path, {"freshness": {"state": "fresh"}, "facts": [{"featured_dex": [1]}]})
            self.write_json(
                root,
                "data/external/index.json",
                {"snapshots": [{"provider": "example", "data_category": "events", "path": path, "freshness": {"state": "stale"}}]},
            )
            result = opportunity_special_labs.build_opportunity_finder(
                root,
                {"build_id": "abcdef123456", "export_timestamp": "2026-08-28T12:00:00Z"},
            )
            self.assertEqual(result["opportunity_count"], 0)
            self.assertEqual(result["no_verified_current_path"][0]["dex"], 1)
            self.assertTrue(result["safety"]["fresh_only"])

    def test_multiple_fresh_channels_preserve_unknown_rate_and_restrictions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.seed_personalization(root)
            event_path = "data/external/snapshots/events.json"
            raid_path = "data/external/snapshots/raids.json"
            self.write_json(
                root,
                event_path,
                {"freshness": {"state": "fresh"}, "facts": [{"featured_dex": [1], "end": "2026-08-28T20:00:00Z", "ticket_required": True}]},
            )
            self.write_json(
                root,
                raid_path,
                {"freshness": {"state": "fresh"}, "facts": [{"boss_dex": 1, "end": "2026-08-30T20:00:00Z", "encounter_rate": "source-defined"}]},
            )
            self.write_json(
                root,
                "data/external/index.json",
                {
                    "snapshots": [
                        {"provider": "official-events", "authority": "Official", "classification": "Official current data", "data_category": "events", "dataset_timestamp": "2026-08-28T10:00:00Z", "source_reference": "event-source", "path": event_path, "freshness": {"state": "fresh"}},
                        {"provider": "official-raids", "authority": "Official", "classification": "Official current data", "data_category": "raids", "dataset_timestamp": "2026-08-28T10:00:00Z", "source_reference": "raid-source", "path": raid_path, "freshness": {"state": "fresh"}},
                    ]
                },
            )
            result = opportunity_special_labs.build_opportunity_finder(
                root,
                {"build_id": "abcdef123456", "export_timestamp": "2026-08-28T12:00:00Z"},
            )
            bulbasaur = [item for item in result["opportunities"] if item["dex"] == 1]
            self.assertEqual({item["channel"] for item in bulbasaur}, {"events", "raids"})
            event = next(item for item in bulbasaur if item["channel"] == "events")
            raid = next(item for item in bulbasaur if item["channel"] == "raids")
            self.assertEqual(event["group"], "ending_soon")
            self.assertEqual(event["restrictions"]["state"], "qualified")
            self.assertEqual(event["encounter_rate"]["state"], "unknown")
            self.assertEqual(raid["encounter_rate"]["state"], "source-provided")
            self.assertTrue(event["personalization"]["missing_species"])

    def test_special_mechanics_joins_exact_owned_prerequisites_and_moves(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.write_json(
                output,
                "data/pokemon.json",
                {
                    "records": [
                        {"pokemon_number": 800, "name": "Necrozma", "cp": 2000, "identity": {"record_id": "necrozma-1"}, "moves": {"fast": "Shadow Claw", "charged": "Future Sight"}},
                        {"pokemon_number": 791, "name": "Solgaleo", "cp": 3000, "identity": {"record_id": "solgaleo-1"}, "moves": {"fast": "Fire Spin", "charged": "Psychic Fangs"}},
                        {"pokemon_number": 483, "name": "Dialga", "form": "Origin", "cp": 3500, "identity": {"record_id": "dialga-1"}, "moves": {"fast": "Dragon Breath", "charged": "Roar of Time"}},
                        {"pokemon_number": 484, "name": "Palkia", "form": "Origin", "cp": 3400, "identity": {"record_id": "palkia-1"}, "moves": {"fast": "Dragon Breath", "charged": "Aqua Tail"}},
                    ]
                },
            )
            result = opportunity_special_labs.build_special_mechanics_lab(repo_root, output, {"build_id": "abcdef123456"})
            fusion = next(item for item in result["mechanics"] if item["kind"] == "fusion")
            dusk = next(item for item in fusion["recipes"] if item["id"] == "dusk-mane-necrozma")
            self.assertTrue(dusk["owned_prerequisites"]["exact_owned_pair_available"])
            self.assertFalse(dusk["resource_readiness"]["numeric_cost_fully_reviewed"])
            self.assertEqual(dusk["local_state"], "unknown-until-user-confirmed")

            adventure = next(item for item in result["mechanics"] if item["kind"] == "adventure-effect")
            roar = next(item for item in adventure["effects"] if item["id"] == "roar-of-time")
            rend = next(item for item in adventure["effects"] if item["id"] == "spacial-rend")
            self.assertEqual(roar["usable_owned_record_ids"], ["dialga-1"])
            self.assertEqual(rend["usable_owned_record_ids"], [])
            self.assertFalse(result["safety"]["tm_learnability_inferred"])
            self.assertEqual(result["registry"]["dataset_version"], "2026-08-28.1")


if __name__ == "__main__":
    unittest.main()
