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
    "data/pokemon.json": ("data/schema.json", None),
    "data/collection-summary.json": ("data/collection-summary.schema.json", None),
    "data/build-manifest.json": ("data/build-manifest.schema.json", None),
    "data/data-health.json": ("data/data-health.schema.json", None),
    "data/insights.json": ("data/insights.schema.json", None),
}

_STABLE_NAMES = {
    "data/pokemon.json": "pokemon",
    "data/collection-summary.json": "collection_summary",
    "data/build-manifest.json": "build_manifest",
    "data/build-diagnostics.json": "build_diagnostics",
    "data/deduplication-report.json": "deduplication_report",
    "data/scan-quality-report.json": "scan_quality_report",
    "data/data-health.json": "data_health",
    "data/insights.json": "insights",
    "data/latest-export.csv": "latest_export",
    "data/schema.json": "pokemon_schema",
    "data/collection-summary.schema.json": "collection_summary_schema",
    "data/build-manifest.schema.json": "build_manifest_schema",
    "data/source-columns.json": "source_columns",
    "data/data-health.schema.json": "data_health_schema",
    "data/insights.schema.json": "insights_schema",
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
    stem = filename.removesuffix(".json").removesuffix(".csv")
    normalized = "".join(character if character.isalnum() else "_" for character in stem).strip("_")
    return f"data_{normalized}"


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

    for path in sorted(item for item in data_dir.iterdir() if item.is_file()):
        relative = path.relative_to(output_dir).as_posix()
        name = _resource_name(relative)
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        entry: dict[str, Any] = {
            "resource_type": "schema" if path.name.endswith(".schema.json") or path.name == "schema.json" else "data",
            "path": relative,
            "status": "available",
            "media_type": media_type,
            "build_id": manifest["build_id"],
        }
        schema_path, schema_version = _SCHEMA_MAP.get(relative, (None, None))
        if schema_path:
            entry["schema"] = schema_path
        detected_version = _json_schema_version(path)
        if detected_version:
            entry["schema_version"] = detected_version
        elif schema_version:
            entry["schema_version"] = schema_version

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
            "path": {"type": "string", "pattern": "^data/[^/]+$"},
            "status": {"type": "string", "const": "available"},
            "media_type": {"type": "string", "minLength": 1},
            "build_id": {"type": "string", "pattern": "^[0-9a-f]{12}$"},
            "schema": {"type": "string", "pattern": "^data/[^/]+\\.json$"},
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
