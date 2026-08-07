"""Canonical integrity layer for the production Pokémon GO collection build."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

try:
    from . import build_collection as base
    from . import build_release
    from .collection_integrity import (
        DEDUPLICATION_SCHEMA_VERSION,
        FOUNDATION_SCHEMA_VERSION,
        IDENTITY_VERSION,
        SCAN_QUALITY_SCHEMA_VERSION,
        patch_record_schema,
        process_collection,
    )
    from .manifest_registry import (
        MANIFEST_VERSION,
        RESOURCE_REGISTRY_VERSION,
        build_resource_registry,
        patch_manifest_foundation_schema,
    )
    from .semantic_validation import Diagnostic, validate_rows
except ImportError:  # Direct execution through scripts/build_dashboard.py
    import build_collection as base
    import build_release
    from collection_integrity import (
        DEDUPLICATION_SCHEMA_VERSION,
        FOUNDATION_SCHEMA_VERSION,
        IDENTITY_VERSION,
        SCAN_QUALITY_SCHEMA_VERSION,
        patch_record_schema,
        process_collection,
    )
    from manifest_registry import (
        MANIFEST_VERSION,
        RESOURCE_REGISTRY_VERSION,
        build_resource_registry,
        patch_manifest_foundation_schema,
    )
    from semantic_validation import Diagnostic, validate_rows


def _write_json(path: Path, payload: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _foundation_fields(
    manifest: dict[str, Any],
    deduplication: dict[str, Any],
) -> None:
    manifest.update(
        {
            "manifest_version": MANIFEST_VERSION,
            "resource_registry_version": RESOURCE_REGISTRY_VERSION,
            "schema_version": FOUNDATION_SCHEMA_VERSION,
            "source_record_count": deduplication["source_record_count"],
            "normalized_record_count": deduplication["normalized_record_count"],
            "duplicates_collapsed": deduplication["duplicates_collapsed"],
            "pokemon_count": deduplication["normalized_record_count"],
            "integrity": {
                "identity_version": IDENTITY_VERSION,
                "deduplication_schema_version": DEDUPLICATION_SCHEMA_VERSION,
                "deduplication_report": "data/deduplication-report.json",
                "scan_quality_schema_version": SCAN_QUALITY_SCHEMA_VERSION,
                "scan_quality_report": "data/scan-quality-report.json",
            },
        }
    )


def _patch_contracts(output_dir: Path) -> None:
    manifest_schema_path = output_dir / "data" / "build-manifest.schema.json"
    payload_schema_path = output_dir / "data" / "schema.json"

    manifest_schema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))
    patch_manifest_foundation_schema(
        manifest_schema,
        normalized_schema_version=FOUNDATION_SCHEMA_VERSION,
        identity_version=IDENTITY_VERSION,
        deduplication_schema_version=DEDUPLICATION_SCHEMA_VERSION,
        scan_quality_schema_version=SCAN_QUALITY_SCHEMA_VERSION,
    )
    _write_json(manifest_schema_path, manifest_schema)

    payload_schema = json.loads(payload_schema_path.read_text(encoding="utf-8"))
    patch_record_schema(payload_schema["$defs"]["record"])
    patch_manifest_foundation_schema(
        payload_schema["$defs"]["manifest"],
        normalized_schema_version=FOUNDATION_SCHEMA_VERSION,
        identity_version=IDENTITY_VERSION,
        deduplication_schema_version=DEDUPLICATION_SCHEMA_VERSION,
        scan_quality_schema_version=SCAN_QUALITY_SCHEMA_VERSION,
    )
    _write_json(payload_schema_path, payload_schema)

    source_columns_path = output_dir / "data" / "source-columns.json"
    if source_columns_path.is_file():
        source_columns = json.loads(source_columns_path.read_text(encoding="utf-8"))
        source_columns["normalized_schema_version"] = FOUNDATION_SCHEMA_VERSION
        _write_json(source_columns_path, source_columns)


def _sync_manifest(output_dir: Path, manifest: dict[str, Any]) -> None:
    payload_path = output_dir / "data" / "pokemon.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["manifest"] = manifest
    _write_json(payload_path, payload, compact=True)
    _write_json(output_dir / "data" / "build-manifest.json", manifest)


def build(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    """Build production data with semantic validation, reconciliation, identity, and diagnostics."""
    warnings_holder: dict[str, list[Diagnostic]] = {"warnings": []}
    integrity_holder: dict[str, dict[str, Any]] = {}

    def validated_integrity_reader(path: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            report = base.analyze_source_columns(fieldnames)
            missing = report["missing_required_columns"]
            if missing:
                raise ValueError("Newest export is missing required columns: " + ", ".join(missing))
            rows, warnings = validate_rows(fieldnames, reader)

        if not rows:
            raise ValueError("Newest export contains no Pokémon rows")

        raw_records = [
            base.legacy.normalize_row(row, row_number)
            for row_number, row in enumerate(rows, start=2)
        ]
        parsed = base.legacy.parse_export_filename(path)
        normalized, deduplication, scan_quality = process_collection(
            rows,
            raw_records,
            source_filename=path.name,
            reference_date=parsed.timestamp.date() if parsed else None,
            unknown_columns=report["unknown_columns"],
            semantic_warnings=[warning.to_dict() for warning in warnings],
        )

        warnings_holder["warnings"] = warnings
        integrity_holder["deduplication"] = deduplication
        integrity_holder["scan_quality"] = scan_quality
        report["warnings"] = [
            *report["warnings"],
            *(warning.format() for warning in warnings),
        ]
        report["normalized_schema_version"] = FOUNDATION_SCHEMA_VERSION
        return fieldnames, normalized, report

    original_reader = base.read_compatible_export
    original_version_assets = base.version_assets
    base.read_compatible_export = validated_integrity_reader
    base.version_assets = lambda output, site, build_id: build_release.optimized_version_assets(
        original_version_assets,
        output,
        site,
        build_id,
    )
    try:
        manifest = base.build(repository_root, output_dir)
    finally:
        base.read_compatible_export = original_reader
        base.version_assets = original_version_assets

    deduplication = integrity_holder.get("deduplication")
    scan_quality = integrity_holder.get("scan_quality")
    if deduplication is None or scan_quality is None:
        raise RuntimeError("Canonical integrity reports were not generated")

    build_release._publish_diagnostics(output_dir, manifest, warnings_holder["warnings"])
    _foundation_fields(manifest, deduplication)
    _write_json(output_dir / "data" / "deduplication-report.json", deduplication)
    _write_json(output_dir / "data" / "scan-quality-report.json", scan_quality)
    _patch_contracts(output_dir)
    _sync_manifest(output_dir, manifest)

    llms_path = output_dir / "llms.txt"
    llms = llms_path.read_text(encoding="utf-8")
    llms += (
        "\nCanonical collection integrity:\n"
        f"- Raw source rows: {manifest['source_record_count']}\n"
        f"- Canonical normalized records: {manifest['normalized_record_count']}\n"
        f"- Repeated scans conservatively collapsed: {manifest['duplicates_collapsed']}\n"
        "- Each normalized record has a build-scoped record_id and a best-effort cross-build fingerprint.\n"
        "- /data/deduplication-report.json explains automatic and possible duplicate groups.\n"
        "- /data/scan-quality-report.json provides record-level rescan/review diagnostics.\n"
    )
    llms_path.write_text(llms, encoding="utf-8", newline="\n")
    return manifest


def finalize_foundation(output_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Publish the final registry after Data Health, Insights, and PWA resources exist."""
    manifest["resources"] = build_resource_registry(output_dir, manifest)
    _sync_manifest(output_dir, manifest)

    llms_path = output_dir / "llms.txt"
    llms = llms_path.read_text(encoding="utf-8")
    llms += (
        "- /data/build-manifest.json is the authoritative resource index for this build.\n"
        f"- Published data resources in registry: {len(manifest['resources'])}\n"
    )
    llms_path.write_text(llms, encoding="utf-8", newline="\n")
    return manifest
