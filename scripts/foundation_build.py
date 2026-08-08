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
    from .knowledge_publish import publish_repository_knowledge
    from .knowledge_validation import augment_scan_quality, load_repository_knowledge
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
    from knowledge_publish import publish_repository_knowledge
    from knowledge_validation import augment_scan_quality, load_repository_knowledge
    from manifest_registry import (
        MANIFEST_VERSION,
        RESOURCE_REGISTRY_VERSION,
        build_resource_registry,
        patch_manifest_foundation_schema,
    )
    from semantic_validation import Diagnostic, validate_rows


_OFFLINE_CONNECTIVITY_PROBE = """<script data-offline-connectivity-probe>
(() => {
  const showOffline = () => {
    const banner = document.getElementById("offline-status");
    if (!banner) return;
    banner.hidden = false;
    const message = banner.querySelector("[data-offline-message]");
    if (message && !String(message.textContent || "").startsWith("Offline")) {
      const exportText = document.querySelector(".data-menu-card small")?.textContent?.replace(/^Exported\\s*/i, "") || "cached collection";
      message.textContent = `Offline · using ${exportText}`;
    }
  };

  const probe = async () => {
    if (!navigator.onLine) {
      showOffline();
      return;
    }
    try {
      const response = await fetch(location.href, {
        method: "HEAD",
        cache: "no-store",
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error("connectivity probe failed");
    } catch {
      showOffline();
    }
  };

  addEventListener("offline", showOffline);
  addEventListener("load", probe, { once: true });
})();
</script>
"""


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


def _inject_connectivity_probe(output_dir: Path) -> None:
    """Detect real network loss even when a service worker keeps navigator.onLine optimistic."""
    for filename in ("index.html", "404.html"):
        path = output_dir / filename
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        if "data-offline-connectivity-probe" in source:
            continue
        if "</body>" not in source:
            raise ValueError(f"{filename} is missing the closing body tag required by the offline probe")
        path.write_text(
            source.replace("</body>", _OFFLINE_CONNECTIVITY_PROBE + "</body>", 1),
            encoding="utf-8",
            newline="\n",
        )


def build(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    """Build production data with semantic validation, reconciliation, identity, and diagnostics."""
    warnings_holder: dict[str, list[Diagnostic]] = {"warnings": []}
    integrity_holder: dict[str, dict[str, Any]] = {}
    knowledge = load_repository_knowledge(repository_root)

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
        scan_quality = augment_scan_quality(scan_quality, normalized, knowledge)

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
    publish_repository_knowledge(repository_root, output_dir)
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
        f"- Species/form and CP/HP/level semantics use {knowledge.classification} dataset {knowledge.dataset_version}.\n"
        "- /data/knowledge/species-index.json is the compact machine index; /data/knowledge/pokemon-go.json is the complete pinned knowledge snapshot.\n"
    )
    llms_path.write_text(llms, encoding="utf-8", newline="\n")
    return manifest


def finalize_foundation(output_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Publish the final registry after Data Health, Insights, PWA, shard, and knowledge resources exist."""
    _inject_connectivity_probe(output_dir)
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
