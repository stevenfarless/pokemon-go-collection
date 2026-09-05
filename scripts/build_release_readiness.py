#!/usr/bin/env python3
"""Build machine- and human-readable release-readiness reports from evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

GATES = (
    ("correctness", "Correctness and destructive decisions"),
    ("security", "Security and supply chain"),
    ("browser_support", "Browser support"),
    ("accessibility", "Accessibility"),
    ("visual_responsive", "Visual and responsive behavior"),
    ("test_depth", "Test depth"),
    ("performance_scale", "Performance and scale"),
    ("local_data_safety", "Local data safety"),
    ("privacy_publication", "Privacy and publication"),
    ("external_data", "External data"),
    ("pokemon_go_mechanics", "Pokémon GO mechanics"),
    ("usability", "Usability"),
    ("machine_outputs", "Machine/LLM outputs"),
    ("known_limitations", "Known limitations"),
)
VALID_STATUSES = {"pass", "fail", "blocked"}
FULL_COMMIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def load_evidence(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("evidence root must be an object")
    return data


def validate_metadata(data: dict) -> tuple[bool, list[str]]:
    issues = []
    reviewed_at = data.get("reviewed_at")
    commit_sha = data.get("commit_sha")

    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        issues.append("reviewed_at is missing")
    else:
        try:
            parsed = dt.datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                issues.append("reviewed_at must include a timezone")
        except ValueError:
            issues.append("reviewed_at is not a valid ISO-8601 timestamp")

    if not isinstance(commit_sha, str) or not FULL_COMMIT_SHA.fullmatch(commit_sha):
        issues.append("commit_sha must be a full 40-character Git commit SHA")

    return not issues, issues


def normalize_report(data: dict) -> dict:
    gate_input = data.get("gates", {})
    if not isinstance(gate_input, dict):
        raise ValueError("gates must be an object")

    metadata_valid, metadata_issues = validate_metadata(data)
    gates = []
    for gate_id, label in GATES:
        raw = gate_input.get(gate_id)
        if raw is None:
            raw = {
                "status": "blocked",
                "evidence": [],
                "reviewed_by": "",
                "notes": "No current evidence was provided for this mandatory gate.",
                "issues": [],
            }
        if not isinstance(raw, dict):
            raise ValueError(f"gate {gate_id} must be an object")

        status = raw.get("status")
        if status not in VALID_STATUSES:
            raise ValueError(f"gate {gate_id} has invalid status: {status!r}")

        evidence = raw.get("evidence", [])
        reviewed_by = raw.get("reviewed_by", "")
        issues = raw.get("issues", [])
        notes = raw.get("notes", "")
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            raise ValueError(f"gate {gate_id} evidence must be a list of strings")
        if any(not item.strip() for item in evidence):
            raise ValueError(f"gate {gate_id} evidence cannot contain blank entries")
        if not isinstance(reviewed_by, str):
            raise ValueError(f"gate {gate_id} reviewed_by must be a string")
        if not isinstance(issues, list) or not all(isinstance(item, int) for item in issues):
            raise ValueError(f"gate {gate_id} issues must be a list of issue numbers")
        if not isinstance(notes, str):
            raise ValueError(f"gate {gate_id} notes must be a string")
        if status == "pass" and not evidence:
            raise ValueError(f"gate {gate_id} cannot pass without evidence")
        if status == "pass" and not reviewed_by.strip():
            raise ValueError(f"gate {gate_id} cannot pass without reviewed_by")

        gates.append(
            {
                "id": gate_id,
                "label": label,
                "status": status,
                "evidence": evidence,
                "reviewed_by": reviewed_by,
                "notes": notes,
                "issues": issues,
            }
        )

    release_candidate = metadata_valid and all(gate["status"] == "pass" for gate in gates)
    return {
        "schema_version": 1,
        "reviewed_at": data.get("reviewed_at"),
        "commit_sha": data.get("commit_sha"),
        "metadata_valid": metadata_valid,
        "metadata_issues": metadata_issues,
        "release_candidate": release_candidate,
        "summary": {
            status: sum(1 for gate in gates if gate["status"] == status)
            for status in ("pass", "fail", "blocked")
        },
        "gates": gates,
    }


def render_markdown(report: dict) -> str:
    status = "PASS" if report["release_candidate"] else "BLOCKED"
    lines = [
        "# Release-readiness report",
        "",
        f"Overall status: **{status}**",
        "",
        f"Commit: `{report.get('commit_sha') or 'unknown'}`",
        f"Reviewed: {report.get('reviewed_at') or 'unknown'}",
    ]
    if report["metadata_issues"]:
        lines.extend(
            [
                "",
                "Metadata blockers:",
                *[f"- {issue}" for issue in report["metadata_issues"]],
            ]
        )
    lines.extend(
        [
            "",
            "| Gate | Status | Evidence / notes |",
            "| --- | --- | --- |",
        ]
    )
    for gate in report["gates"]:
        details = list(gate["evidence"])
        if gate["reviewed_by"]:
            details.append(f"Reviewed by: {gate['reviewed_by']}")
        if gate["notes"]:
            details.append(gate["notes"])
        if gate["issues"]:
            details.append("Issues: " + ", ".join(f"#{number}" for number in gate["issues"]))
        detail_text = "<br>".join(details) if details else "None"
        lines.append(f"| {gate['label']} | {gate['status'].upper()} | {detail_text} |")
    lines.extend(
        [
            "",
            "A release candidate requires valid review metadata and PASS for every mandatory gate. Missing evidence is reported as BLOCKED.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(evidence_path: Path, output_dir: Path) -> dict:
    report = normalize_report(load_evidence(evidence_path))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "release-readiness.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "release-readiness.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("release-readiness-report"))
    args = parser.parse_args()

    report = write_report(args.evidence, args.output_dir)
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
