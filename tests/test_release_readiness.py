import importlib.util
import json
from pathlib import Path

import pytest

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


def test_all_passing_gates_create_release_candidate(tmp_path):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(_passing_evidence()), encoding="utf-8")

    report = release_readiness.write_report(evidence_path, tmp_path / "out")

    assert report["release_candidate"] is True
    assert report["summary"] == {"pass": 14, "fail": 0, "blocked": 0}
    saved = json.loads((tmp_path / "out" / "release-readiness.json").read_text(encoding="utf-8"))
    assert saved["commit_sha"] == "abc123"
    assert "Overall status: **PASS**" in (tmp_path / "out" / "release-readiness.md").read_text(encoding="utf-8")


def test_missing_gate_is_blocked(tmp_path):
    evidence = _passing_evidence()
    evidence["gates"].pop("usability")
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    report = release_readiness.write_report(evidence_path, tmp_path / "out")

    assert report["release_candidate"] is False
    usability = next(gate for gate in report["gates"] if gate["id"] == "usability")
    assert usability["status"] == "blocked"
    assert report["summary"]["blocked"] == 1


def test_pass_requires_evidence():
    evidence = _passing_evidence()
    evidence["gates"]["security"]["evidence"] = []

    with pytest.raises(ValueError, match="cannot pass without evidence"):
        release_readiness.normalize_report(evidence)


def test_invalid_status_is_rejected():
    evidence = _passing_evidence()
    evidence["gates"]["security"]["status"] = "unknown"

    with pytest.raises(ValueError, match="invalid status"):
        release_readiness.normalize_report(evidence)
