"""Public JSON schemas and coordinated-build invariants."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

try:
    from .collection_shards import validate_collection_shards
except ImportError:
    from collection_shards import validate_collection_shards

BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"


def _schema(name: str, required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE_ID + name + ".schema.json",
        "title": name.replace("-", " ").title(),
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": True,
    }


def _array(item_type: str = "string") -> dict[str, Any]:
    return {"type": "array", "items": {"type": item_type}}


def schemas() -> dict[str, dict[str, Any]]:
    count = {"type": "integer", "minimum": 0}
    nonempty = {"type": "string", "minLength": 1}
    return {
        "source-columns.schema.json": _schema(
            "source-columns",
            ["export_schema_version", "normalized_schema_version", "required_columns", "source_columns", "warnings"],
            {
                "export_schema_version": nonempty,
                "normalized_schema_version": nonempty,
                "required_columns": _array(),
                "source_columns": _array(),
                "warnings": _array(),
            },
        ),
        "build-diagnostics.schema.json": _schema(
            "build-diagnostics",
            ["policy_version", "summary", "warnings", "errors"],
            {
                "policy_version": nonempty,
                "summary": {
                    "type": "object",
                    "required": ["warning_count", "error_count"],
                    "properties": {"warning_count": count, "error_count": count},
                },
                "warnings": {"type": "array", "items": {"type": "object"}},
                "errors": {"type": "array", "items": {"type": "object"}},
            },
        ),
        "filter-options.schema.json": _schema(
            "filter-options",
            ["species", "forms", "genders", "fast_moves", "charged_moves", "evolutions"],
            {
                key: _array()
                for key in ("species", "forms", "genders", "fast_moves", "charged_moves", "evolutions")
            },
        ),
        "deduplication-report.schema.json": _schema(
            "deduplication-report",
            [
                "schema_version", "source_file", "source_record_count", "normalized_record_count",
                "duplicates_collapsed", "automatic_group_count", "possible_group_count",
                "policy", "automatic_groups", "possible_groups",
            ],
            {
                "schema_version": nonempty,
                "source_file": nonempty,
                "source_record_count": count,
                "normalized_record_count": count,
                "duplicates_collapsed": count,
                "automatic_group_count": count,
                "possible_group_count": count,
                "policy": {"type": "object"},
                "automatic_groups": {"type": "array", "items": {"type": "object"}},
                "possible_groups": {"type": "array", "items": {"type": "object"}},
            },
        ),
        "scan-quality-report.schema.json": _schema(
            "scan-quality-report",
            ["schema_version", "source_file", "record_count", "stale_scan_days", "summary", "coverage", "findings"],
            {
                "schema_version": nonempty,
                "source_file": nonempty,
                "record_count": count,
                "stale_scan_days": count,
                "summary": {
                    "type": "object",
                    "required": ["finding_count", "severity_counts", "action_counts", "reason_counts"],
                    "properties": {
                        "finding_count": count,
                        "severity_counts": {"type": "object"},
                        "action_counts": {"type": "object"},
                        "reason_counts": {"type": "object"},
                    },
                },
                "coverage": {"type": "object"},
                "findings": {"type": "array", "items": {"type": "object"}},
            },
        ),
    }


def publish_public_schemas(output_dir: Path) -> None:
    data_dir = output_dir / "data"
    for filename, schema in schemas().items():
        Draft202012Validator.check_schema(schema)
        (data_dir / filename).write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same(label: str, *values: Any) -> None:
    if any(value != values[0] for value in values[1:]):
        raise ValueError(f"Cross-resource invariant failed for {label}: {values!r}")


def _validate_declared_resources(output_dir: Path, manifest: dict[str, Any]) -> None:
    data_dir = output_dir / "data"
    resources = manifest.get("resources") or {}
    if not resources:
        raise ValueError("build-manifest.json has no resource registry")

    declared_paths = [entry["path"] for entry in resources.values()]
    if len(declared_paths) != len(set(declared_paths)):
        raise ValueError("Resource registry contains duplicate paths")
    declared = set(declared_paths)
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in data_dir.rglob("*")
        if path.is_file()
    }
    if declared != actual:
        raise ValueError(
            f"Resource registry mismatch: missing={sorted(declared - actual)}, "
            f"stale_or_undeclared={sorted(actual - declared)}"
        )

    for name, entry in resources.items():
        path = output_dir / entry["path"]
        if entry.get("build_id") != manifest["build_id"]:
            raise ValueError(f"Resource {name!r} belongs to a different build")
        if not path.is_file():
            raise ValueError(f"Declared resource is missing: {entry['path']}")
        if "byte_size" in entry and entry["byte_size"] != path.stat().st_size:
            raise ValueError(f"Resource size mismatch: {entry['path']}")
        if "sha256" in entry and entry["sha256"] != _sha256(path):
            raise ValueError(f"Resource checksum mismatch: {entry['path']}")
        if entry.get("resource_type") == "schema":
            Draft202012Validator.check_schema(_load(path))
            continue
        if entry.get("media_type") == "application/json":
            schema_path = entry.get("schema")
            if not schema_path or schema_path not in declared:
                raise ValueError(f"Public JSON resource has no declared schema: {entry['path']}")
            schema = _load(output_dir / schema_path)
            Draft202012Validator.check_schema(schema)
            errors = list(Draft202012Validator(schema).iter_errors(_load(path)))
            if errors:
                raise ValueError(
                    f"{entry['path']} fails {schema_path} at {errors[0].json_path}: "
                    f"{errors[0].message}"
                )


def validate_public_resources(output_dir: Path) -> None:
    data_dir = output_dir / "data"
    manifest = _load(data_dir / "build-manifest.json")
    _validate_declared_resources(output_dir, manifest)

    payload = _load(data_dir / "pokemon.json")
    summary = _load(data_dir / "collection-summary.json")
    diagnostics = _load(data_dir / "build-diagnostics.json")
    dedup = _load(data_dir / "deduplication-report.json")
    quality = _load(data_dir / "scan-quality-report.json")
    source_columns = _load(data_dir / "source-columns.json")
    records = payload["records"]
    record_count = len(records)

    _same("embedded build ID", manifest["build_id"], payload["manifest"]["build_id"])
    _same(
        "normalized count",
        record_count,
        manifest["pokemon_count"],
        manifest["normalized_record_count"],
        summary["pokemon_count"],
        quality["record_count"],
    )
    _same("source schema", manifest["export_schema_version"], source_columns["export_schema_version"])
    _same("normalized schema", manifest["schema_version"], source_columns["normalized_schema_version"])
    _same(
        "warning count",
        manifest["diagnostics"]["warning_count"],
        diagnostics["summary"]["warning_count"],
        len(diagnostics["warnings"]),
    )
    _same(
        "error count",
        manifest["diagnostics"]["error_count"],
        diagnostics["summary"]["error_count"],
        len(diagnostics["errors"]),
    )
    _same("raw count", manifest["source_record_count"], dedup["source_record_count"])
    _same("dedup normalized count", record_count, dedup["normalized_record_count"])
    if dedup["source_record_count"] - dedup["normalized_record_count"] != dedup["duplicates_collapsed"]:
        raise ValueError("Deduplication counts do not reconcile")
    _same("automatic duplicate groups", dedup["automatic_group_count"], len(dedup["automatic_groups"]))
    _same("possible duplicate groups", dedup["possible_group_count"], len(dedup["possible_groups"]))
    _same("quality findings", quality["summary"]["finding_count"], len(quality["findings"]))

    record_ids = [record.get("identity", {}).get("record_id") for record in records]
    if any(not record_id for record_id in record_ids) or len(record_ids) != len(set(record_ids)):
        raise ValueError("Canonical record IDs must be present and unique")
    known_ids = set(record_ids)
    for finding in quality["findings"]:
        record_id = finding.get("record_id")
        if record_id is not None and record_id not in known_ids:
            raise ValueError("Scan-quality report references an unknown record ID")
    for group in dedup["automatic_groups"]:
        if group.get("canonical_record_id") not in known_ids:
            raise ValueError("Deduplication report references an unknown canonical record ID")
    for group in dedup["possible_groups"]:
        if any(record_id not in known_ids for record_id in group.get("record_ids", [])):
            raise ValueError("Possible-duplicate group references an unknown record ID")

    health_path = data_dir / "data-health.json"
    if health_path.is_file():
        health = _load(health_path)
        _same(
            "Data Health count",
            record_count,
            health["source"]["record_count"],
            health["counts"]["records"],
        )
        _same(
            "Data Health schema",
            manifest["schema_version"],
            health["build"]["normalized_schema_version"],
        )
    insights_path = data_dir / "insights.json"
    if insights_path.is_file():
        insights = _load(insights_path)
        _same(
            "Insights count",
            record_count,
            insights["source"]["record_count"],
            insights["overview"]["pokemon_count"],
        )

    filter_resources = [
        entry
        for entry in manifest["resources"].values()
        if entry.get("resource_type") == "data"
        and entry["path"].startswith("data/filter-options.")
        and entry["path"].endswith(".json")
    ]
    if len(filter_resources) != 1:
        raise ValueError("Exactly one current filter-options resource is required")
    options = _load(output_dir / filter_resources[0]["path"])
    expected_species = sorted(
        {record["name"] for record in records if record.get("name")},
        key=str.casefold,
    )
    if options["species"] != expected_species:
        raise ValueError("Filter-options species list does not match canonical records")

    shard_index_path = data_dir / "pokemon-index.json"
    if shard_index_path.is_file():
        validate_collection_shards(output_dir, payload=payload, index=_load(shard_index_path))
