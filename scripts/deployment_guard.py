#!/usr/bin/env python3
"""Validate a staged Pages build before promotion or rollback."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

try:
    from .validate_generated import validate_generated
except ImportError:
    from validate_generated import validate_generated


_REQUIRED_PAGES = ("index.html", "404.html", "insights.html", "manifest.webmanifest", "sw.js")
_STATIC_ASSETS = {"assets/app-icon.svg"}
_REQUIRED_INTEGRITY_REPORTS = (
    "data/deduplication-report.json",
    "data/scan-quality-report.json",
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _selected_source_filename(manifest: dict[str, Any]) -> str:
    explicit = str(manifest.get("source_filename") or "").strip()
    if explicit:
        return Path(explicit).name
    source_file = str(manifest.get("source_file") or "").strip()
    return Path(source_file).name if source_file else ""


def validate_privacy_status(output_dir: Path) -> dict[str, Any]:
    """Reject builds explicitly marked for local/private preview before public promotion."""
    if (output_dir / ".private-local-preview").exists():
        raise ValueError("Privacy profile private-local-preview is local-only and cannot be promoted to public Pages")
    audit_path = output_dir / "data" / "privacy-audit.json"
    if not audit_path.is_file():
        # Backward-compatible rollback artifacts created before privacy profiles existed.
        return {"profile": "legacy-full-public", "deployment_allowed": True, "friend_code_public": None}
    audit = _load_json(audit_path)
    if int(audit.get("schema_version", 0)) != 1:
        raise ValueError("Privacy audit schema version is unsupported")
    profile = str(audit.get("profile") or "")
    if profile not in {"full-public", "redacted", "private-local-preview"}:
        raise ValueError(f"Privacy audit has an unknown profile: {profile or 'missing'}")
    if audit.get("browser_local_namespaces_public") is not False:
        raise ValueError("Privacy audit does not prove browser-local namespaces are excluded from publication")
    if audit.get("deployment_allowed") is not True:
        raise ValueError(f"Privacy profile {profile} is not approved for public Pages deployment")
    return {
        "profile": profile,
        "deployment_allowed": True,
        "friend_code_public": audit.get("friend_code_public"),
    }


def validate_integrity_reports(output_dir: Path, manifest: dict[str, Any]) -> dict[str, int]:
    for relative in _REQUIRED_INTEGRITY_REPORTS:
        path = output_dir / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Staged build is missing required maintenance report: {relative}")

    dedup = _load_json(output_dir / "data" / "deduplication-report.json")
    quality = _load_json(output_dir / "data" / "scan-quality-report.json")

    source_count = int(manifest.get("source_record_count", 0))
    canonical_count = int(manifest.get("normalized_record_count", manifest.get("pokemon_count", 0)))
    collapsed = int(manifest.get("duplicates_collapsed", 0))
    selected_filename = _selected_source_filename(manifest)

    if source_count <= 0 or canonical_count <= 0:
        raise ValueError("Manifest record counts must be positive")
    if canonical_count > source_count:
        raise ValueError("Canonical record count exceeds source record count")
    if source_count - canonical_count != collapsed:
        raise ValueError("Manifest duplicate count does not reconcile with source/canonical counts")
    if not selected_filename:
        raise ValueError("Manifest does not identify the selected source export")

    dedup_source = Path(str(dedup.get("source_file") or "")).name
    quality_source = Path(str(quality.get("source_file") or "")).name
    if dedup_source != selected_filename:
        raise ValueError("Deduplication report source file disagrees with manifest")
    if int(dedup.get("source_record_count", -1)) != source_count:
        raise ValueError("Deduplication report source count disagrees with manifest")
    if int(dedup.get("normalized_record_count", -1)) != canonical_count:
        raise ValueError("Deduplication report canonical count disagrees with manifest")
    if int(dedup.get("duplicates_collapsed", -1)) != collapsed:
        raise ValueError("Deduplication report duplicate count disagrees with manifest")
    if quality_source != selected_filename:
        raise ValueError("Scan-quality report source file disagrees with manifest")
    if int(quality.get("record_count", -1)) != canonical_count:
        raise ValueError("Scan-quality report record count disagrees with manifest")

    findings = quality.get("findings")
    summary = quality.get("summary")
    if not isinstance(findings, list) or not isinstance(summary, dict):
        raise ValueError("Scan-quality report is missing findings or summary")
    if int(summary.get("finding_count", -1)) != len(findings):
        raise ValueError("Scan-quality finding count does not match findings array")

    severity_counts = summary.get("severity_counts", {})
    if not isinstance(severity_counts, dict):
        raise ValueError("Scan-quality severity counts are malformed")
    errors = int(severity_counts.get("error", 0))
    warnings = int(severity_counts.get("warning", 0))
    infos = int(severity_counts.get("info", 0))
    if errors > 0:
        raise ValueError(f"Scan-quality report contains {errors} deployment-blocking error finding(s)")

    return {
        "source_records": source_count,
        "canonical_records": canonical_count,
        "duplicates_collapsed": collapsed,
        "quality_errors": errors,
        "quality_warnings": warnings,
        "quality_info": infos,
        "quality_findings": len(findings),
    }


def _append_actions_summary(metadata: dict[str, Any]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [
        "### Automatic collection maintenance",
        f"- Source export: `{metadata.get('source_file')}`",
        f"- Build ID: `{metadata.get('build_id')}`",
        f"- Privacy profile: `{metadata.get('privacy_profile')}`",
        f"- Source rows: {metadata.get('source_records', 0)}",
        f"- Canonical Pokémon: {metadata.get('canonical_records', 0)}",
        f"- Duplicate scans collapsed: {metadata.get('duplicates_collapsed', 0)}",
        f"- Scan-quality warnings: {metadata.get('quality_warnings', 0)}",
        f"- Scan-quality informational findings: {metadata.get('quality_info', 0)}",
        "- Promotion status: validated",
        "",
    ]
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def inspect_staged_build(output_dir: Path, *, expected_build_id: str | None = None) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if not output_dir.is_dir():
        raise ValueError(f"Staged build directory does not exist: {output_dir}")

    validate_generated(output_dir)

    for relative in _REQUIRED_PAGES:
        path = output_dir / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Staged build is missing required Pages resource: {relative}")

    manifest_path = output_dir / "data" / "build-manifest.json"
    manifest = _load_json(manifest_path)
    build_id = str(manifest.get("build_id") or "")
    if not build_id:
        raise ValueError("Staged manifest has no build_id")
    if expected_build_id is not None and build_id != expected_build_id:
        raise ValueError(f"Rollback build ID mismatch: expected {expected_build_id}, staged artifact contains {build_id}")

    privacy = validate_privacy_status(output_dir)
    integrity = validate_integrity_reports(output_dir, manifest)

    declared_assets = {str(value) for value in manifest.get("assets", {}).values() if str(value).startswith("assets/")}
    allowed_assets = declared_assets | _STATIC_ASSETS
    assets_dir = output_dir / "assets"
    if not assets_dir.is_dir():
        raise ValueError("Staged build is missing the assets directory")
    actual_assets = {path.relative_to(output_dir).as_posix() for path in assets_dir.iterdir() if path.is_file()}
    unexpected_assets = sorted(actual_assets - allowed_assets)
    missing_assets = sorted(declared_assets - actual_assets)
    if missing_assets:
        raise ValueError(f"Staged build is missing declared assets: {missing_assets}")
    if unexpected_assets:
        raise ValueError("Staged build contains undeclared/stale assets that could create a mixed deployment: " + ", ".join(unexpected_assets))

    for relative in declared_assets:
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"Manifest asset path is unsafe: {relative}")

    metadata = {
        "build_id": build_id,
        "source_file": manifest.get("source_file"),
        "source_sha256": manifest.get("source_sha256"),
        "generated_at_utc": manifest.get("generated_at_utc"),
        "pokemon_count": integrity["canonical_records"],
        "resource_count": len(manifest.get("resources", {})),
        "asset_count": len(declared_assets),
        "privacy_profile": privacy["profile"],
        "friend_code_public": privacy["friend_code_public"],
        **integrity,
    }
    _append_actions_summary(metadata)
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a staged collection before Pages promotion")
    parser.add_argument("--output", type=Path, default=Path("staging"))
    parser.add_argument("--expected-build-id", default=None)
    parser.add_argument("--metadata-output", type=Path, default=None)
    args = parser.parse_args()

    metadata = inspect_staged_build(args.output, expected_build_id=args.expected_build_id)
    if args.metadata_output is not None:
        args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_output.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(
        "Promotion guard passed: "
        f"build={metadata['build_id']} source={metadata['source_file']} "
        f"records={metadata['pokemon_count']} duplicates={metadata['duplicates_collapsed']} "
        f"privacy={metadata['privacy_profile']} warnings={metadata['quality_warnings']} resources={metadata['resource_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
