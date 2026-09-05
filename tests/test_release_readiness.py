import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_release_readiness.py"
SPEC = importlib.util.spec_from_file_location("build_release_readiness", MODULE_PATH)
release_readiness = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(release_readiness)


def _passing_evidence():
    return {
        "reviewed_at": "2026-09-05T00:00:00Z",
        "commit_sha": "0123456789abcdef0123456789abcdef01234567",
        "gates": {
            gate_id: {
                "status": "pass",
                "evidence": [f"artifact/{gate_id}.txt"],
                "reviewed_by": "workflow:test",
                "notes": "",
                "issues": [],
            }
            for gate_id, _label in release_readiness.GATES
        },
    }


class ReleaseReadinessTests(unittest.TestCase):
    def test_all_passing_gates_create_release_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence_path = root / "evidence.json"
            evidence_path.write_text(json.dumps(_passing_evidence()), encoding="utf-8")

            report = release_readiness.write_report(evidence_path, root / "out")

            self.assertTrue(report["release_candidate"])
            self.assertTrue(report["audit_pass"])
            self.assertEqual(report["audit_mode"], "full")
            self.assertTrue(report["metadata_valid"])
            self.assertEqual(report["metadata_issues"], [])
            self.assertEqual(report["summary"], {"pass": 14, "fail": 0, "blocked": 0})
            self.assertEqual(report["out_of_scope"], 0)
            saved = json.loads((root / "out" / "release-readiness.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["schema_version"], 2)
            self.assertEqual(saved["commit_sha"], "0123456789abcdef0123456789abcdef01234567")
            self.assertEqual(saved["gates"][0]["reviewed_by"], "workflow:test")
            markdown = (root / "out" / "release-readiness.md").read_text(encoding="utf-8")
            self.assertIn("Overall status: **PASS**", markdown)
            self.assertIn("Audit mode: full", markdown)
            self.assertIn("Reviewed by: workflow:test", markdown)

    def test_targeted_audit_reports_only_selected_gate_summary(self):
        evidence = _passing_evidence()
        evidence["audit_scope"] = {
            "mode": "targeted",
            "gates": ["external_data", "pokemon_go_mechanics"],
            "reason": "Major Pokémon GO mechanics change",
        }
        evidence["gates"]["security"]["status"] = "blocked"
        evidence["gates"]["security"]["evidence"] = []
        evidence["gates"]["security"]["reviewed_by"] = ""

        report = release_readiness.normalize_report(evidence)

        self.assertTrue(report["audit_pass"])
        self.assertFalse(report["release_candidate"])
        self.assertEqual(report["audit_mode"], "targeted")
        self.assertEqual(report["summary"], {"pass": 2, "fail": 0, "blocked": 0})
        self.assertEqual(report["out_of_scope"], 12)
        external = next(gate for gate in report["gates"] if gate["id"] == "external_data")
        security = next(gate for gate in report["gates"] if gate["id"] == "security")
        self.assertTrue(external["in_scope"])
        self.assertFalse(security["in_scope"])
        markdown = release_readiness.render_markdown(report)
        self.assertIn("Overall status: **TARGETED PASS**", markdown)
        self.assertIn("Release-candidate status: unavailable from a targeted audit", markdown)

    def test_targeted_audit_blocks_on_selected_gate(self):
        evidence = _passing_evidence()
        evidence["audit_scope"] = {
            "mode": "targeted",
            "gates": ["external_data"],
            "reason": "External source contract changed",
        }
        evidence["gates"]["external_data"]["status"] = "blocked"
        evidence["gates"]["external_data"]["evidence"] = []
        evidence["gates"]["external_data"]["reviewed_by"] = ""

        report = release_readiness.normalize_report(evidence)

        self.assertFalse(report["audit_pass"])
        self.assertFalse(report["release_candidate"])
        self.assertEqual(report["summary"], {"pass": 0, "fail": 0, "blocked": 1})
        self.assertIn("Overall status: **TARGETED BLOCKED**", release_readiness.render_markdown(report))

    def test_targeted_audit_requires_gate_and_reason(self):
        evidence = _passing_evidence()
        evidence["audit_scope"] = {"mode": "targeted", "gates": [], "reason": "change"}
        with self.assertRaisesRegex(ValueError, "requires at least one gate"):
            release_readiness.normalize_report(evidence)

        evidence["audit_scope"] = {"mode": "targeted", "gates": ["security"], "reason": "  "}
        with self.assertRaisesRegex(ValueError, "requires a reason"):
            release_readiness.normalize_report(evidence)

    def test_targeted_audit_rejects_unknown_or_duplicate_gates(self):
        evidence = _passing_evidence()
        evidence["audit_scope"] = {"mode": "targeted", "gates": ["security", "security"], "reason": "change"}
        with self.assertRaisesRegex(ValueError, "cannot contain duplicates"):
            release_readiness.normalize_report(evidence)

        evidence["audit_scope"] = {"mode": "targeted", "gates": ["unknown"], "reason": "change"}
        with self.assertRaisesRegex(ValueError, "unknown gates"):
            release_readiness.normalize_report(evidence)

    def test_full_audit_rejects_subset_scope(self):
        evidence = _passing_evidence()
        evidence["audit_scope"] = {"mode": "full", "gates": ["security"], "reason": ""}

        with self.assertRaisesRegex(ValueError, "cannot select a subset"):
            release_readiness.normalize_report(evidence)

    def test_missing_gate_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence = _passing_evidence()
            evidence["gates"].pop("usability")
            evidence_path = root / "evidence.json"
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

            report = release_readiness.write_report(evidence_path, root / "out")

            self.assertFalse(report["release_candidate"])
            usability = next(gate for gate in report["gates"] if gate["id"] == "usability")
            self.assertEqual(usability["status"], "blocked")
            self.assertEqual(report["summary"]["blocked"], 1)

    def test_missing_review_metadata_blocks_candidate(self):
        evidence = _passing_evidence()
        evidence["reviewed_at"] = None
        evidence["commit_sha"] = None

        report = release_readiness.normalize_report(evidence)

        self.assertFalse(report["release_candidate"])
        self.assertFalse(report["metadata_valid"])
        self.assertIn("reviewed_at is missing", report["metadata_issues"])
        self.assertIn("commit_sha must be a full 40-character Git commit SHA", report["metadata_issues"])
        markdown = release_readiness.render_markdown(report)
        self.assertIn("Metadata blockers:", markdown)

    def test_invalid_review_metadata_blocks_candidate(self):
        evidence = _passing_evidence()
        evidence["reviewed_at"] = "2026-09-05T00:00:00"
        evidence["commit_sha"] = "abc123"

        report = release_readiness.normalize_report(evidence)

        self.assertFalse(report["metadata_valid"])
        self.assertIn("reviewed_at must include a timezone", report["metadata_issues"])
        self.assertIn("commit_sha must be a full 40-character Git commit SHA", report["metadata_issues"])

    def test_pass_requires_evidence(self):
        evidence = _passing_evidence()
        evidence["gates"]["security"]["evidence"] = []

        with self.assertRaisesRegex(ValueError, "cannot pass without evidence"):
            release_readiness.normalize_report(evidence)

    def test_pass_requires_reviewer_attribution(self):
        evidence = _passing_evidence()
        evidence["gates"]["security"]["reviewed_by"] = "   "

        with self.assertRaisesRegex(ValueError, "cannot pass without reviewed_by"):
            release_readiness.normalize_report(evidence)

    def test_reviewed_by_must_be_string(self):
        evidence = _passing_evidence()
        evidence["gates"]["security"]["reviewed_by"] = 123

        with self.assertRaisesRegex(ValueError, "reviewed_by must be a string"):
            release_readiness.normalize_report(evidence)

    def test_blank_evidence_entry_is_rejected(self):
        evidence = _passing_evidence()
        evidence["gates"]["security"]["evidence"] = ["   "]

        with self.assertRaisesRegex(ValueError, "evidence cannot contain blank entries"):
            release_readiness.normalize_report(evidence)

    def test_invalid_status_is_rejected(self):
        evidence = _passing_evidence()
        evidence["gates"]["security"]["status"] = "unknown"

        with self.assertRaisesRegex(ValueError, "invalid status"):
            release_readiness.normalize_report(evidence)


if __name__ == "__main__":
    unittest.main()
