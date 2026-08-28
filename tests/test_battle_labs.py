from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import battle_labs


class BattleLabPublisherTests(unittest.TestCase):
    def write_json(self, root: Path, relative: str, payload: object) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def seed_candidates(self, root: Path) -> None:
        for league in ("great", "ultra", "little", "master"):
            self.write_json(
                root,
                f"data/candidates/{league}-league.json",
                {"status": "available", "candidate_count": 2, "candidates": []},
            )
        self.write_json(
            root,
            "data/candidates/rocket-battle-inputs.json",
            {"status": "available", "candidate_count": 4, "candidates": []},
        )

    def test_missing_current_data_blocks_current_pvp_and_rocket_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.seed_candidates(root)
            self.write_json(root, "data/external/index.json", {"snapshots": []})
            manifest = {"build_id": "abcdef123456"}

            pvp = battle_labs.build_pvp_battle_lab(root, manifest)
            rocket = battle_labs.build_rocket_planner(root, manifest)

            self.assertEqual(pvp["current_simulation"]["state"], "blocked")
            self.assertTrue(pvp["comparison_contract"]["exact_owned_record_mapping"])
            self.assertEqual(rocket["current_lineups"]["state"], "blocked")
            self.assertTrue(rocket["recommendation_contract"]["stale_lineup_advice_blocks"])
            self.assertEqual(rocket["owned_candidates"]["candidate_count"], 4)

    def test_fresh_rocket_snapshot_preserves_branching_and_source_counter_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.seed_candidates(root)
            snapshot_path = "data/external/snapshots/rocket.json"
            self.write_json(
                root,
                snapshot_path,
                {
                    "freshness": {"state": "fresh"},
                    "facts": [
                        {
                            "encounter_id": "leader-example",
                            "leader": "Example",
                            "slots": [[{"dex": 1}], [{"dex": 2}, {"dex": 3}], [{"dex": 4}]],
                            "counter_species_dexes": [68, 150, 448],
                            "shadow_encounter": {"dex": 4},
                        }
                    ],
                },
            )
            self.write_json(
                root,
                "data/external/index.json",
                {
                    "snapshots": [
                        {
                            "provider": "verified-community-example",
                            "data_category": "rocket-lineups",
                            "dataset_timestamp": "2026-08-28T00:00:00Z",
                            "source_reference": "example-source",
                            "authority": "verified-community",
                            "path": snapshot_path,
                            "freshness": {"state": "fresh"},
                        }
                    ]
                },
            )
            result = battle_labs.build_rocket_planner(root, {"build_id": "abcdef123456"})
            self.assertEqual(result["current_lineups"]["state"], "fresh")
            self.assertEqual(result["current_lineups"]["encounter_count"], 1)
            encounter = result["current_lineups"]["encounters"][0]
            self.assertEqual(encounter["counter_species_dexes"], [68, 150, 448])
            self.assertEqual(encounter["counter_mapping_state"], "source-backed")
            self.assertEqual(len(encounter["slots"]), 3)
            self.assertEqual(encounter["source"]["provider"], "verified-community-example")

    def test_fresh_pvp_source_does_not_overclaim_matchup_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.seed_candidates(root)
            snapshot_path = "data/external/snapshots/pvp.json"
            self.write_json(root, snapshot_path, {"freshness": {"state": "fresh"}, "facts": [{"cup": "Example Cup"}]})
            self.write_json(
                root,
                "data/external/index.json",
                {
                    "snapshots": [
                        {
                            "provider": "example-pvp-source",
                            "data_category": "pvp-meta",
                            "dataset_timestamp": "2026-08-28T00:00:00Z",
                            "source_reference": "example",
                            "path": snapshot_path,
                            "freshness": {"state": "fresh"},
                        }
                    ]
                },
            )
            result = battle_labs.build_pvp_battle_lab(root, {"build_id": "abcdef123456"})
            self.assertEqual(result["current_simulation"]["state"], "fresh-source-available")
            self.assertIn("still requires", result["current_simulation"]["reason"])
            self.assertEqual(result["comparison_contract"]["matchup_results"].startswith("Wins/losses/ties remain unavailable"), True)


if __name__ == "__main__":
    unittest.main()
