import json
import tempfile
import unittest
from pathlib import Path

from scripts import product_experience


class ProductExperienceTests(unittest.TestCase):
    def manifest(self):
        return {
            "build_id": "123456789abc",
            "generated_at_utc": "2026-08-23T12:00:00Z",
            "export_timestamp": "2026-08-23T11:00:00Z",
        }

    def knowledge(self):
        return {
            "dataset_version": "fixture-1",
            "classification": "Verified community data",
            "entries": [
                {
                    "dex": 25,
                    "species_id": "PIKACHU",
                    "display_name": "Pikachu",
                    "base_name": "Pikachu",
                    "form_label": "Normal",
                    "form_key": "normal",
                    "form_aliases": [],
                    "types": ["Electric"],
                    "family": {"family_id": "PIKACHU_FAMILY"},
                    "released": True,
                    "transformation": {},
                    "moves": {"fast": ["Thunder Shock"], "charged": ["Wild Charge"]},
                },
                {
                    "dex": 25,
                    "species_id": "PIKACHU_COSTUME",
                    "display_name": "Pikachu",
                    "base_name": "Pikachu",
                    "form_label": "Costume",
                    "form_key": "costume",
                    "form_aliases": ["hat"],
                    "types": ["Electric"],
                    "family": {"family_id": "PIKACHU_FAMILY"},
                    "released": True,
                    "transformation": {},
                    "moves": {"fast": ["Thunder Shock"]},
                },
                {
                    "dex": 26,
                    "species_id": "RAICHU",
                    "display_name": "Raichu",
                    "base_name": "Raichu",
                    "form_label": "Normal",
                    "form_key": "normal",
                    "form_aliases": [],
                    "types": ["Electric"],
                    "family": {"family_id": "PIKACHU_FAMILY"},
                    "released": True,
                    "transformation": {},
                    "moves": {"charged": ["Wild Charge"]},
                },
            ],
        }

    def records(self):
        return [
            {
                "pokemon_number": 25,
                "name": "Pikachu",
                "form": None,
                "cp": 500,
                "identity": {"record_id": "record-normal"},
                "ivs": {"average_percent": 100},
                "moves": {"fast": "Thunder Shock", "charged": "Wild Charge"},
                "status": {"shadow_purified": "normal"},
            }
        ]

    def test_reference_covers_unowned_forms_and_keeps_owned_join_exact(self):
        payload = product_experience.build_reference_index(self.knowledge(), self.records(), self.manifest())
        self.assertEqual(payload["entry_count"], 3)
        by_id = {entry["species_id"]: entry for entry in payload["entries"]}
        self.assertEqual(by_id["PIKACHU"]["owned_record_ids"], ["record-normal"])
        self.assertEqual(by_id["PIKACHU_COSTUME"]["owned_record_ids"], [])
        self.assertEqual(by_id["RAICHU"]["owned_count"], 0)
        self.assertEqual(by_id["PIKACHU"]["route"], "reference.html?species=PIKACHU")

    def test_only_explicitly_fresh_external_metadata_is_promoted(self):
        external = {
            "snapshots": [
                {"path": "data/external/snapshots/fresh.json", "data_category": "events", "freshness": {"state": "fresh", "max_age_hours": 12}},
                {"path": "data/external/snapshots/stale.json", "data_category": "raids", "freshness": {"state": "stale", "max_age_hours": 12}},
                {"data_category": "moves", "freshness": {"state": "fresh", "max_age_hours": 12}},
            ]
        }
        selected = product_experience._current_snapshot_metadata(external)
        self.assertEqual([item["path"] for item in selected], ["data/external/snapshots/fresh.json"])

    def test_search_has_exact_records_reference_actions_moves_and_fresh_current(self):
        reference = product_experience.build_reference_index(self.knowledge(), self.records(), self.manifest())
        fresh = [{
            "provider": "fixture",
            "data_category": "events",
            "classification": "Official",
            "source_reference": "https://example.invalid/event",
            "dataset_timestamp": "2026-08-23T10:00:00Z",
            "path": "data/external/snapshots/event.json",
        }]
        mechanics = {"domains": [{"id": "cp", "label": "CP", "status": "supported", "normalized_facts": ["Combat Power"]}]}
        search = product_experience.build_search_index(reference, self.records(), mechanics, fresh, self.manifest())
        product_experience.add_move_search_items(search, self.knowledge())
        domains = {item["domain"] for item in search["items"]}
        self.assertTrue({"action", "owned-record", "owned-species", "reference", "family", "type", "move", "mechanic", "current"}.issubset(domains))
        exact = next(item for item in search["items"] if item["domain"] == "owned-record")
        self.assertIn("record=record-normal", exact["route"])
        current = [item for item in search["items"] if item["domain"] == "current"]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["freshness"], "fresh")

    def test_today_reuses_queue_resources_and_limits_top_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            recommendations = output / "data" / "recommendations"
            recommendations.mkdir(parents=True)
            queues = []
            for name in ("rescan", "pvp-candidates", "evolution-review", "resource-review"):
                path = f"data/recommendations/{name}.json"
                queues.append({"name": name, "path": path})
                (output / path).write_text(json.dumps({"records": [{
                    "record_id": f"record-{name}",
                    "name": "Pikachu",
                    "form": None,
                    "cp": 500,
                    "reasons": ["fixture_reason"],
                    "warnings": ["missing_ivs"] if name == "rescan" else [],
                    "inputs": {},
                }]}) + "\n", encoding="utf-8")
            (recommendations / "index.json").write_text(json.dumps({"queues": queues}) + "\n", encoding="utf-8")
            data = output / "data"
            (data / "data-health.json").write_text(json.dumps({"counts": {"incomplete_scans": 1}, "links": {"incomplete_scans": "./?quality=missing-any"}, "source": {}}) + "\n", encoding="utf-8")
            (data / "collection-diff.json").write_text(json.dumps({"added": [], "changed": []}) + "\n", encoding="utf-8")
            payload = product_experience.build_today_payload(output, self.manifest(), [])
            self.assertLessEqual(len(payload["top_actions"]), 5)
            rescan = payload["sections"]["my_collection"]["cards"][0]
            self.assertEqual(rescan["source_resource"], "data/recommendations/rescan.json")
            self.assertFalse(rescan["dismissible"])
            self.assertEqual(payload["sections"]["roster_gaps"]["status"], "unavailable")
            self.assertEqual(payload["sections"]["event_prep"]["status"], "limited")


if __name__ == "__main__":
    unittest.main()
