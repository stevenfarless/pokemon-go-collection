#!/usr/bin/env python3
"""Build machine- and human-readable release-readiness reports from evidence."""

from __future__ import annotations

import argparse
import json
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


def load_evidence(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("evidence root must be an object")
    return data


def normalize_report(data: dict) -> dict:
    gate_input = data.get("gates", {})
    if not isinstance(gate_input, dict):
        raise ValueError("gates must be an object")

    gates = []
    for gate_id, label in GATES:
        raw = gate_input.get(gate_id)
        if raw is None:
            raw = {
                "status": "blocked",
                "evidence": [],
                "notes": "No current evidence was provided for this mandatory gate.",
                "issues": [],
            }
        if not isinstance(raw, dict):
            raise ValueError(f"gate {gate_id} must be an object")

        status = raw.get("status")
        if status not in VALID_STATUSES:
            raise ValueError(f"gate {gate_id} has invalid status: {status!r}")

        evidence = raw.get("evidence", [])
        issues = raw.get("issues", [])
        notes = raw.get("notes", "")
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            raise ValueError(f"gate {gate_id} evidence must be a list of strings")
        if not isinstance(issues, list) or not all(isinstance(item, int) for item in issues):
            raise ValueError(f"gate {gate_id} issues must be a list of issue numbers")
        if not isinstance(notes, str):
            raise ValueError(f"gate {gate_id} notes must be a string")
        if status == "pass" and not evidence:
            raise ValueError(f"gate {gate_id} cannot pass without evidence")

        gates.append(
            {
                "id": gate_id,
                "label": label,
                "status": status,
                "evidence": evidence,
                "notes": notes,
                "issues": issues,
            }
        )

    release_candidate = all(gate["status"] == "pass" for gate in gates)
    return {
        "schema_version": 1,
        "reviewed_at": data.get("reviewed_at"),
        "commit_sha": data.get("commit_sha"),
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
        "",
        "| Gate | Status | Evidence / notes |",
        "| --- | --- | --- |",
    ]
    for gate in report["gates"]:
        details = list(gate["evidence"])
        if gate["notes"]:
            details.append(gate["notes"])
        if gate["issues"]:
            details.append("Issues: " + ", ".join(f"#{number}" for number in gate["issues"]))
        detail_text = "<br>".join(details) if details else "None"
        lines.append(f"| {gate['label']} | {gate['status'].upper()} | {detail_text} |")
    lines.extend(
        [
            "",
            "A release candidate requires PASS for every mandatory gate. Missing evidence is reported as BLOCKED.",
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
