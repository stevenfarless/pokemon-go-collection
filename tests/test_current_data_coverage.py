import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts import current_data_coverage, external_game_data


class CurrentDataCoverageTests(unittest.TestCase):
    def setUp(self):
        current_data_coverage.install()
        self.now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)

    def snapshot(self, category="gbl", timestamp="2026-08-23T10:00:00Z", max_age_hours=12):
        return external_game_data.normalize_snapshot(
            {
                "provider": "fixture",
                "source_reference": "https://example.invalid/source",
                "dataset_timestamp": timestamp,
                "data_category": category,
                "classification": "Official",
                "data_version": "fixture-1",
                "schema_version": "1.0.0",
                "license": {
                    "name": "Fixture",
                    "redistribution_permitted": True,
                },
                "join_keys": ["species_id"],
                "freshness_policy": {"max_age_hours": max_age_hours},
                "facts": [],
            },
            now=self.now,
        )

    def test_required_rotating_categories_are_explicitly_covered(self):
        required = {"moves", "gbl", "rocket", "max-battles", "research", "eggs", "ditto"}
        coverage = current_data_coverage.coverage_payload()
        self.assertTrue(required.issubset(coverage))
        for category in required:
            entry = coverage[category]
            self.assertIn(entry["status"], {"available-path", "unavailable"})
            if entry["status"] == "available-path":
                self.assertTrue(entry.get("production_acquisition_path"))
            else:
                self.assertTrue(entry.get("unavailable_reason"))

    def test_rocket_coverage_reflects_adopted_reviewed_provider(self):
        coverage = current_data_coverage.coverage_payload()["rocket"]
        self.assertEqual(coverage["status"], "available-path")
        self.assertIn("external/providers", coverage["production_acquisition_path"])
        self.assertIn("freshness", coverage["production_acquisition_path"])

    def test_stale_snapshot_cannot_drive_current_claim(self):
        stale = self.snapshot(timestamp="2026-08-20T10:00:00Z", max_age_hours=12)
        selected, status = current_data_coverage.select_current_snapshot([stale], "gbl", now=self.now)
        self.assertIsNone(selected)
        self.assertFalse(status["current_claim_allowed"])
        self.assertEqual(status["state"], "stale")

    def test_newest_fresh_snapshot_is_selected(self):
        older = self.snapshot(timestamp="2026-08-23T08:00:00Z")
        newer = self.snapshot(timestamp="2026-08-23T11:00:00Z")
        selected, status = current_data_coverage.select_current_snapshot([older, newer], "gbl", now=self.now)
        self.assertEqual(selected["dataset_timestamp"], "2026-08-23T11:00:00Z")
        self.assertTrue(status["current_claim_allowed"])
        self.assertEqual(status["state"], "fresh")

    def test_unavailable_category_explains_missing_production_path(self):
        selected, status = current_data_coverage.select_current_snapshot([], "ditto", now=self.now)
        self.assertIsNone(selected)
        self.assertFalse(status["current_claim_allowed"])
        self.assertIn("source", status["reason"])

    def test_external_index_metadata_exposes_fail_closed_consumer_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            index_path = output / "data" / "external" / "index.json"
            index_path.parent.mkdir(parents=True)
            index_path.write_text(
                json.dumps({"schema_version": "1.0.0", "data_categories": list(external_game_data.DATA_CATEGORIES)}),
                encoding="utf-8",
            )
            payload = current_data_coverage.publish_metadata(output)
            self.assertEqual(payload["coverage_contract_version"], current_data_coverage.COVERAGE_CONTRACT_VERSION)
            self.assertEqual(payload["consumer_contract"]["current_claim_requires"], "fresh normalized snapshot")
            self.assertIn("gbl", payload["category_coverage"])


if __name__ == "__main__":
    unittest.main()
