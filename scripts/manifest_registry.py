"""Authoritative build/resource manifest helpers."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any

MANIFEST_VERSION = "2.0.0"
RESOURCE_REGISTRY_VERSION = "1.0.0"

_SCHEMA_MAP = {
    "data/pokemon.json": "data/schema.json",
    "data/collection-summary.json": "data/collection-summary.schema.json",
    "data/build-manifest.json": "data/build-manifest.schema.json",
    "data/llm-bootstrap.json": "data/llm-bootstrap.schema.json",
    "data/build-diagnostics.json": "data/build-diagnostics.schema.json",
    "data/source-columns.json": "data/source-columns.schema.json",
    "data/deduplication-report.json": "data/deduplication-report.schema.json",
    "data/scan-quality-report.json": "data/scan-quality-report.schema.json",
    "data/data-health.json": "data/data-health.schema.json",
    "data/insights.json": "data/insights.schema.json",
    "data/pokemon-index.json": "data/pokemon-index.schema.json",
    "data/knowledge/pokemon-go.json": "data/knowledge/pokemon-go.schema.json",
    "data/knowledge/species-index.json": "data/knowledge/species-index.schema.json",
    "data/species-index.json": "data/species-index.schema.json",
    "data/family-index.json": "data/family-index.schema.json",
    "data/views-index.json": "data/views-index.schema.json",
    "data/history-index.json": "data/history-index.schema.json",
    "data/collection-diff.json": "data/collection-diff.schema.json",
    "data/recommendations/index.json": "data/recommendation-index.schema.json",
    "data/candidates/index.json": "data/candidate-index.schema.json",
    "data/investments/index.json": "data/investment-index.schema.json",
    "data/investments/records.json": "data/investment-records.schema.json",
    "data/reasoning/index.json": "data/reasoning-index.schema.json",
    "data/reasoning/rules.json": "data/reasoning-rules.schema.json",
    "data/reasoning/records.json": "data/reasoning-records.schema.json",
    "data/external/index.json": "data/external-index.schema.json",
}

_STABLE_NAMES = {
    "data/pokemon.json": "pokemon",
    "data/collection-summary.json": "collection_summary",
    "data/build-manifest.json": "build_manifest",
    "data/llm-bootstrap.json": "llm_bootstrap",
    "data/build-diagnostics.json": "build_diagnostics",
    "data/deduplication-report.json": "deduplication_report",
    "data/scan-quality-report.json": "scan_quality_report",
    "data/data-health.json": "data_health",
    "data/insights.json": "insights",
    "data/pokemon-index.json": "pokemon_index",
    "data/latest-export.csv": "latest_export",
    "data/schema.json": "pokemon_schema",
    "data/collection-summary.schema.json": "collection_summary_schema",
    "data/build-manifest.schema.json": "build_manifest_schema",
    "data/llm-bootstrap.schema.json": "llm_bootstrap_schema",
    "data/build-diagnostics.schema.json": "build_diagnostics_schema",
    "data/source-columns.json": "source_columns",
    "data/source-columns.schema.json": "source_columns_schema",
    "data/deduplication-report.schema.json": "deduplication_report_schema",
    "data/scan-quality-report.schema.json": "scan_quality_report_schema",
    "data/filter-options.schema.json": "filter_options_schema",
    "data/data-health.schema.json": "data_health_schema",
    "data/insights.schema.json": "insights_schema",
    "data/pokemon-index.schema.json": "pokemon_index_schema",
    "data/pokemon-shard.schema.json": "pokemon_shard_schema",
    "data/knowledge/pokemon-go.json": "pokemon_go_knowledge",
    "data/knowledge/pokemon-go.schema.json": "pokemon_go_knowledge_schema",
    "data/knowledge/species-index.json": "pokemon_go_species_index",
    "data/knowledge/species-index.schema.json": "pokemon_go_species_index_schema",
    "data/knowledge/PVPOKE-LICENSE.txt": "pvpoke_license",
    "data/species-index.json": "owned_species_index",
    "data/family-index.json": "owned_family_index",
    "data/views-index.json": "views_index",
    "data/history-index.json": "history_index",
    "data/collection-diff.json": "collection_diff",
    "data/assistant-context.md": "assistant_context",
    "data/recommendations/index.json": "recommendations_index",
    "data/candidates/index.json": "candidates_index",
    "data/investments/index.json": "investments_index",
    "data/investments/records.json": "investment_records",
    "data/reasoning/index.json": "reasoning_index",
    "data/reasoning/rules.json": "reasoning_rules",
    "data/reasoning/records.json": "reasoning_records",
    "data/external/index.json": "external_data_index",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resource_name(relative_path: str) -> str:
    if relative_path in _STABLE_NAMES:
        return _STABLE_NAMES[relative_path]
    filename = Path(relative_path).name
    if filename.startswith("filter-options.") and filename.endswith(".json"):
        return "filter_options"
    if relative_path.startswith("data/pokemon/chunk-") and filename.endswith(".json"):
        return "pokemon_shard_" + filename.removeprefix("chunk-").removesuffix(".json")
    stem = relative_path.removeprefix("data/").removesuffix(".json").removesuffix(".csv")
    normalized = "".join(character if character.isalnum() else "_" for character in stem).strip("_")
    return f"data_{normalized}"


def _schema_for(relative_path: str) -> str | None:
    if relative_path in _SCHEMA_MAP:
        return _SCHEMA_MAP[relative_path]
    filename = Path(relative_path).name
    if filename.startswith("filter-options.") and filename.endswith(".json"):
        return "data/filter-options.schema.json"
    if relative_path.startswith("data/pokemon/chunk-") and filename.endswith(".json"):
        return "data/pokemon-shard.schema.json"
    if relative_path.startswith("data/pokemon/species/") and filename.endswith(".json"):
        return "data/collection-resource.schema.json"
    if relative_path.startswith("data/pokemon/families/") and filename.endswith(".json"):
        return "data/collection-resource.schema.json"
    if relative_path.startswith("data/views/") and filename.endswith(".json"):
        return "data/collection-view.schema.json"
    if relative_path.startswith("data/history/") and filename == "snapshot.json":
        return "data/history-snapshot.schema.json"
    if relative_path.startswith("data/recommendations/") and filename.endswith(".json"):
        return "data/recommendation-queue.schema.json"
    if relative_path.startswith("data/candidates/") and filename.endswith(".json"):
        return "data/candidate-feed.schema.json"
    if relative_path.startswith("data/external/snapshots/") and filename.endswith(".json"):
        return "data/external-snapshot.schema.json"
    return None


def _json_schema_version(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    value = payload.get("schema_version")
    return str(value) if value not in (None, "") else None


def build_resource_registry(output_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Describe every generated file under data/ using stable, fork-friendly relative paths."""
    data_dir = output_dir / "data"
    resources: dict[str, Any] = {}
    if not data_dir.is_dir():
        return resources

    files = sorted(
        (item for item in data_dir.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(output_dir).as_posix(),
    )
    for path in files:
        relative = path.relative_to(output_dir).as_posix()
        name = _resource_name(relative)
        if name in resources:
            raise ValueError(f"Resource registry name collision for {relative}: {name}")
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        entry: dict[str, Any] = {
            "resource_type": "schema" if path.name.endswith(".schema.json") or path.name == "schema.json" else "data",
            "path": relative,
            "status": "available",
            "media_type": media_type,
            "build_id": manifest["build_id"],
        }
        schema_path = _schema_for(relative)
        if schema_path:
            entry["schema"] = schema_path
        detected_version = _json_schema_version(path)
        if detected_version:
            entry["schema_version"] = detected_version

        if relative == "data/pokemon.json":
            entry["record_count"] = manifest["normalized_record_count"]
            entry["integrity"] = "self-referential-manifest; checksum intentionally omitted"
        elif relative == "data/build-manifest.json":
            entry["integrity"] = "self-reference; checksum intentionally omitted"
        else:
            entry["byte_size"] = path.stat().st_size
            entry["sha256"] = sha256_file(path)

        resources[name] = entry

    return resources


def registry_schema() -> dict[str, Any]:
    entry = {
        "type": "object",
        "required": ["resource_type", "path", "status", "media_type", "build_id"],
        "properties": {
            "resource_type": {"type": "string", "enum": ["data", "schema"]},
            "path": {"type": "string", "pattern": "^data/(?:[^/]+/)*[^/]+$"},
            "status": {"type": "string", "const": "available"},
            "media_type": {"type": "string", "minLength": 1},
            "build_id": {"type": "string", "pattern": "^[0-9a-f]{12}$"},
            "schema": {"type": "string", "pattern": "^data/(?:[^/]+/)*[^/]+\\.json$"},
            "schema_version": {"type": "string", "minLength": 1},
            "record_count": {"type": "integer", "minimum": 0},
            "byte_size": {"type": "integer", "minimum": 0},
            "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "integrity": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "minProperties": 1,
        "additionalProperties": entry,
    }


def patch_manifest_foundation_schema(
    schema: dict[str, Any],
    *,
    normalized_schema_version: str,
    identity_version: str,
    deduplication_schema_version: str,
    scan_quality_schema_version: str,
) -> None:
    """Add authoritative counts, integrity resources, and the versioned resource registry."""
    required = schema.setdefault("required", [])
    for key in (
        "manifest_version",
        "resource_registry_version",
        "source_record_count",
        "normalized_record_count",
        "duplicates_collapsed",
        "integrity",
        "resources",
    ):
        if key not in required:
            required.append(key)

    properties = schema.setdefault("properties", {})
    properties["manifest_version"] = {"type": "string", "const": MANIFEST_VERSION}
    properties["resource_registry_version"] = {
        "type": "string",
        "const": RESOURCE_REGISTRY_VERSION,
    }
    properties["schema_version"] = {
        "type": "string",
        "const": normalized_schema_version,
    }
    properties["source_record_count"] = {"type": "integer", "minimum": 1}
    properties["normalized_record_count"] = {"type": "integer", "minimum": 1}
    properties["duplicates_collapsed"] = {"type": "integer", "minimum": 0}
    properties["integrity"] = {
        "type": "object",
        "required": [
            "identity_version",
            "deduplication_schema_version",
            "deduplication_report",
            "scan_quality_schema_version",
            "scan_quality_report",
        ],
        "properties": {
            "identity_version": {"type": "string", "const": identity_version},
            "deduplication_schema_version": {
                "type": "string",
                "const": deduplication_schema_version,
            },
            "deduplication_report": {
                "type": "string",
                "const": "data/deduplication-report.json",
            },
            "scan_quality_schema_version": {
                "type": "string",
                "const": scan_quality_schema_version,
            },
            "scan_quality_report": {
                "type": "string",
                "const": "data/scan-quality-report.json",
            },
        },
        "additionalProperties": False,
    }
    properties["resources"] = registry_schema()
