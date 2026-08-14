from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.deployment_guard import validate_integrity_reports


class UploadMaintenanceTests(unittest.TestCase):
    def _fixture(self, *, source=10, canonical=8, collapsed=2, errors=0, warnings=3):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        data = root / "data"
        data.mkdir()
        manifest = {
            "source_file": "shared-text-2026-08-14 06_00_00.000.csv",
            "source_record_count": source,
            "normalized_record_count": canonical,
            "duplicates_collapsed": collapsed,
        }
        dedup = {
            "source_file": manifest["source_file"],
            "source_record_count": source,
            "normalized_record_count": canonical,
            "duplicates_collapsed": collapsed,
        }
        findings = [
            {"severity": "warning", "reason_code": "test"}
            for _ in range(warnings)
        ] + [
            {"severity": "error", "reason_code": "test"}
            for _ in range(errors)
        ]
        quality = {
            "source_file": manifest["source_file"],
            "record_count": canonical,
            "summary": {
                "finding_count": len(findings),
                "severity_counts": {"warning": warnings, "error": errors},
            },
            "findings": findings,
        }
        (data / "deduplication-report.json").write_text(json.dumps(dedup), encoding="utf-8")
        (data / "scan-quality-report.json").write_text(json.dumps(quality), encoding="utf-8")
        return temp, root, manifest

    def test_valid_maintenance_reports_reconcile(self):
        temp, root, manifest = self._fixture()
        self.addCleanup(temp.cleanup)
        result = validate_integrity_reports(root, manifest)
        self.assertEqual(result["source_records"], 10)
        self.assertEqual(result["canonical_records"], 8)
        self.assertEqual(result["duplicates_collapsed"], 2)
        self.assertEqual(result["quality_warnings"], 3)

    def test_duplicate_count_must_reconcile(self):
        temp, root, manifest = self._fixture(collapsed=1)
        self.addCleanup(temp.cleanup)
        with self.assertRaisesRegex(ValueError, "duplicate count"):
            validate_integrity_reports(root, manifest)

    def test_report_source_must_match_selected_export(self):
        temp, root, manifest = self._fixture()
        self.addCleanup(temp.cleanup)
        path = root / "data" / "deduplication-report.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["source_file"] = "shared-text-2020-01-01 00_00_00.000.csv"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source file"):
            validate_integrity_reports(root, manifest)

    def test_quality_errors_block_promotion(self):
        temp, root, manifest = self._fixture(errors=1)
        self.addCleanup(temp.cleanup)
        with self.assertRaisesRegex(ValueError, "deployment-blocking"):
            validate_integrity_reports(root, manifest)

    def test_missing_maintenance_report_blocks_promotion(self):
        temp, root, manifest = self._fixture()
        self.addCleanup(temp.cleanup)
        (root / "data" / "scan-quality-report.json").unlink()
        with self.assertRaisesRegex(ValueError, "missing required maintenance report"):
            validate_integrity_reports(root, manifest)

    def test_finding_count_must_match_array(self):
        temp, root, manifest = self._fixture()
        self.addCleanup(temp.cleanup)
        path = root / "data" / "scan-quality-report.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["summary"]["finding_count"] += 1
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "finding count"):
            validate_integrity_reports(root, manifest)


if __name__ == "__main__":
    unittest.main()
