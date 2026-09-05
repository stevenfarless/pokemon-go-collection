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
        "commit_sha": "abc123",
        "gates": {
            gate_id: {"status": "pass", "evidence": [f"artifact/{gate_id}.txt"], "notes": "", "issues": []}
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
            self.assertEqual(report["summary"], {"pass": 14, "fail": 0, "blocked": 0})
            saved = json.loads((root / "out" / "release-readiness.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["commit_sha"], "abc123")
            markdown = (root / "out" / "release-readiness.md").read_text(encoding="utf-8")
            self.assertIn("Overall status: **PASS**", markdown)

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

    def test_pass_requires_evidence(self):
        evidence = _passing_evidence()
        evidence["gates"]["security"]["evidence"] = []

        with self.assertRaisesRegex(ValueError, "cannot pass without evidence"):
            release_readiness.normalize_report(evidence)

    def test_invalid_status_is_rejected(self):
        evidence = _passing_evidence()
        evidence["gates"]["security"]["status"] = "unknown"

        with self.assertRaisesRegex(ValueError, "invalid status"):
            release_readiness.normalize_report(evidence)


if __name__ == "__main__":
    unittest.main()
