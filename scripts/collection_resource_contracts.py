"""Schemas and cross-resource invariants for selective collection resources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_VERSION = "1.0.0"
BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema(name: str, required: list[str], properties: dict[str, Any], *, additional: bool = True) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE_ID + name,
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": additional,
    }


def schemas() -> dict[str, dict[str, Any]]:
    build_id = {"type": "string", "pattern": "^[0-9a-f]{12}$"}
    count = {"type": "integer", "minimum": 0}
    nonempty = {"type": "string", "minLength": 1}
    record_array = {"type": "array", "items": {"type": "object"}}
    record_resource = _schema(
        "collection-resource.schema.json",
        ["schema_version", "build_id", "record_count", "records"],
        {
            "schema_version": {"type": "string", "const": SCHEMA_VERSION},
            "build_id": build_id,
            "record_count": count,
            "records": record_array,
        },
    )
    return {
        "species-index.schema.json": _schema(
            "species-index.schema.json",
            ["schema_version", "build_id", "knowledge_dataset_version", "species_count", "record_count", "entries"],
            {
                "schema_version": {"type": "string", "const": SCHEMA_VERSION},
                "build_id": build_id,
                "knowledge_dataset_version": nonempty,
                "species_count": count,
                "record_count": count,
                "entries": {"type": "array", "items": {"type": "object"}},
            },
        ),
        "family-index.schema.json": _schema(
            "family-index.schema.json",
            ["schema_version", "build_id", "knowledge_dataset_version", "family_count", "record_count", "entries"],
            {
                "schema_version": {"type": "string", "const": SCHEMA_VERSION},
                "build_id": build_id,
                "knowledge_dataset_version": nonempty,
                "family_count": count,
                "record_count": count,
                "entries": {"type": "array", "items": {"type": "object"}},
            },
        ),
        "collection-resource.schema.json": record_resource,
        "views-index.schema.json": _schema(
            "views-index.schema.json",
            ["schema_version", "build_id", "entries", "safety"],
            {
                "schema_version": {"type": "string", "const": SCHEMA_VERSION},
                "build_id": build_id,
                "entries": {"type": "array", "items": {"type": "object"}},
                "safety": nonempty,
            },
        ),
        "collection-view.schema.json": _schema(
            "collection-view.schema.json",
            ["schema_version", "build_id", "name", "definition", "record_count", "record_ids", "records"],
            {
                "schema_version": {"type": "string", "const": SCHEMA_VERSION},
                "build_id": build_id,
                "name": nonempty,
                "definition": nonempty,
                "record_count": count,
                "record_ids": {"type": "array", "items": nonempty},
                "records": record_array,
            },
        ),
        "history-index.schema.json": _schema(
            "history-index.schema.json",
            ["schema_version", "retention_limit", "snapshot_count", "snapshots", "latest_diff"],
            {
                "schema_version": {"type": "string", "const": SCHEMA_VERSION},
                "retention_limit": {"type": "integer", "minimum": 1},
                "snapshot_count": count,
                "snapshots": {"type": "array", "items": {"type": "object"}},
                "latest_diff": {"type": "string", "const": "data/collection-diff.json"},
            },
        ),
        "history-snapshot.schema.json": _schema(
            "history-snapshot.schema.json",
            ["schema_version", "build_id", "source_file", "export_timestamp", "record_count", "records"],
            {
                "schema_version": {"type": "string", "const": SCHEMA_VERSION},
                "build_id": build_id,
                "source_file": nonempty,
                "export_timestamp": nonempty,
                "record_count": count,
                "records": record_array,
            },
        ),
        "collection-diff.schema.json": _schema(
            "collection-diff.schema.json",
            ["schema_version", "from_build_id", "to_build_id", "summary", "added", "removed", "changed", "ambiguous", "wording"],
            {
                "schema_version": {"type": "string", "const": SCHEMA_VERSION},
                "from_build_id": {"type": ["string", "null"]},
                "to_build_id": build_id,
                "summary": {"type": "object"},
                "added": record_array,
                "removed": record_array,
                "changed": {"type": "array", "items": {"type": "object"}},
                "ambiguous": {"type": "array", "items": {"type": "object"}},
                "wording": nonempty,
            },
        ),
    }


def publish_collection_resource_schemas(output_dir: Path) -> None:
    data_dir = output_dir / "data"
    for filename, schema in schemas().items():
        Draft202012Validator.check_schema(schema)
        (data_dir / filename).write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )


def _record_ids(records: list[dict[str, Any]]) -> list[str]:
    return [str(record.get("identity", {}).get("record_id") or "") for record in records]


def validate_collection_resources(output_dir: Path) -> None:
    data_dir = output_dir / "data"
    manifest = _load(data_dir / "build-manifest.json")
    canonical = _load(data_dir / "pokemon.json")["records"]
    known_ids = set(_record_ids(canonical))
    if "" in known_ids:
        raise ValueError("Canonical collection contains a record without record_id")

    species_index = _load(data_dir / "species-index.json")
    if species_index["build_id"] != manifest["build_id"]:
        raise ValueError("Species index belongs to a different build")
    if species_index["species_count"] != len(species_index["entries"]):
        raise ValueError("Species index count does not reconcile")
    species_ids: list[str] = []
    for entry in species_index["entries"]:
        resource = _load(output_dir / entry["path"])
        if resource["build_id"] != manifest["build_id"] or resource["owned_count"] != len(resource["records"]):
            raise ValueError(f"Species resource does not reconcile: {entry['path']}")
        if any(int(record["pokemon_number"]) != int(entry["dex"]) for record in resource["records"]):
            raise ValueError(f"Species resource contains another Pokédex number: {entry['path']}")
        species_ids.extend(_record_ids(resource["records"]))
    if len(species_ids) != len(canonical) or set(species_ids) != known_ids:
        raise ValueError("Species resources do not partition the canonical collection exactly once")

    family_index = _load(data_dir / "family-index.json")
    if family_index["family_count"] != len(family_index["entries"]):
        raise ValueError("Family index count does not reconcile")
    for entry in family_index["entries"]:
        resource = _load(output_dir / entry["path"])
        ids = _record_ids(resource["records"])
        if resource["owned_count"] != len(ids) or len(ids) != len(set(ids)):
            raise ValueError(f"Family resource count/identity mismatch: {entry['path']}")
        if any(record_id not in known_ids for record_id in ids):
            raise ValueError(f"Family resource references an unknown record: {entry['path']}")

    views_index = _load(data_dir / "views-index.json")
    if views_index["build_id"] != manifest["build_id"]:
        raise ValueError("Views index belongs to a different build")
    for entry in views_index["entries"]:
        if entry["status"] == "unavailable":
            if entry.get("path") is not None or entry.get("record_count") is not None:
                raise ValueError(f"Unavailable view must not pretend to have records: {entry['name']}")
            continue
        view = _load(output_dir / entry["path"])
        ids = _record_ids(view["records"])
        if view["record_ids"] != ids or view["record_count"] != len(ids):
            raise ValueError(f"View identity/count mismatch: {entry['name']}")
        if any(record_id not in known_ids for record_id in ids):
            raise ValueError(f"View references an unknown record: {entry['name']}")

    history_index = _load(data_dir / "history-index.json")
    if history_index["snapshot_count"] != len(history_index["snapshots"]):
        raise ValueError("History snapshot count does not reconcile")
    if history_index["snapshot_count"] > history_index["retention_limit"]:
        raise ValueError("History retention limit was exceeded")
    for entry in history_index["snapshots"]:
        snapshot = _load(output_dir / entry["path"])
        if snapshot["build_id"] != entry["build_id"] or snapshot["record_count"] != len(snapshot["records"]):
            raise ValueError(f"History snapshot does not reconcile: {entry['path']}")
    if history_index["snapshots"]:
        latest = history_index["snapshots"][-1]
        if latest["build_id"] != manifest["build_id"] or latest["record_count"] != len(canonical):
            raise ValueError("Latest history snapshot does not represent the canonical build")

    diff = _load(data_dir / "collection-diff.json")
    if diff["to_build_id"] != manifest["build_id"]:
        raise ValueError("Collection diff does not target the current build")
    for key in ("added", "removed", "changed", "ambiguous"):
        if diff["summary"][key] != len(diff[key]):
            raise ValueError(f"Collection diff summary does not reconcile for {key}")
