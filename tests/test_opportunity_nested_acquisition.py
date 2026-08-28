from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import opportunity_special_labs


class NestedOpportunityTests(unittest.TestCase):
    def write_json(self, root: Path, relative: str, payload: object) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_nested_raid_bosses_inherit_window_and_keep_per_boss_region_and_form(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_json(
                root,
                "data/reference/index.json",
                {
                    "entries": [
                        {"dex": 978, "species_id": "tatsugiri-droopy", "display_name": "Tatsugiri (Droopy)", "form_key": "droopy-form", "released": True, "types": ["dragon", "water"], "owned_count": 0, "route": "reference.html?species=tatsugiri-droopy"},
                        {"dex": 54, "species_id": "psyduck-costume", "display_name": "Psyduck (Swim Ring)", "form_key": "swim-ring-costume", "released": True, "types": ["water"], "owned_count": 0, "route": "reference.html?species=psyduck-costume"},
                    ]
                },
            )
            self.write_json(
                root,
                "data/gap-radar.json",
                {
                    "species": [
                        {"dex": 978, "species_id": "tatsugiri-droopy", "name": "Tatsugiri", "species_state": "missing"},
                        {"dex": 54, "species_id": "psyduck-costume", "name": "Psyduck", "species_state": "missing"},
                    ],
                    "forms": [
                        {"dex": 978, "form_key": "droopy-form", "state": "missing"},
                        {"dex": 54, "form_key": "swim-ring-costume", "state": "missing"},
                    ],
                },
            )
            self.write_json(root, "data/roster-readiness.json", {"weakest": []})
            snapshot = "data/external/snapshots/raids.json"
            self.write_json(
                root,
                snapshot,
                {
                    "freshness": {"state": "fresh"},
                    "facts": [
                        {
                            "rotation_id": "regional-raids",
                            "starts_at": "2026-08-28T10:00:00Z",
                            "ends_at": "2026-08-30T10:00:00Z",
                            "timezone": "UTC",
                            "bosses": [
                                {"dex": 978, "name": "Tatsugiri", "form": "Droopy Form", "region": "Americas"},
                                {"dex": 54, "name": "Psyduck", "form": "swim ring costume", "region": "global"},
                            ],
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
                            "provider": "official-raids",
                            "authority": "Official",
                            "data_category": "raids",
                            "dataset_timestamp": "2026-08-28T09:00:00Z",
                            "source_reference": "official",
                            "path": snapshot,
                            "freshness": {"state": "fresh"},
                        }
                    ]
                },
            )
            result = opportunity_special_labs.build_opportunity_finder(
                root,
                {"build_id": "abcdef123456", "export_timestamp": "2026-08-28T12:00:00Z"},
            )
            self.assertEqual(result["opportunity_count"], 2)
            tatsugiri = next(item for item in result["opportunities"] if item["dex"] == 978)
            self.assertEqual(tatsugiri["join_state"], "exact-species-form")
            self.assertEqual(tatsugiri["window"]["end"], "2026-08-30T10:00:00Z")
            self.assertEqual(tatsugiri["restrictions"]["details"]["region"], "Americas")


if __name__ == "__main__":
    unittest.main()
