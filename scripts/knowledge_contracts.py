"""Validate public Pokémon GO knowledge resources and their collection linkage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_pair(data_path: Path, schema_path: Path) -> Any:
    if not data_path.is_file() or not schema_path.is_file():
        raise ValueError(
            f"Knowledge publication requires both {data_path.relative_to(data_path.parents[2])} "
            f"and {schema_path.relative_to(schema_path.parents[2])}"
        )
    schema = _load(schema_path)
    payload = _load(data_path)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise ValueError(f"{data_path.name} fails knowledge schema: {errors[0].message}")
    return payload


def validate_published_knowledge(output_dir: Path) -> None:
    knowledge_dir = output_dir / "data" / "knowledge"
    full = _validate_pair(
        knowledge_dir / "pokemon-go.json",
        knowledge_dir / "pokemon-go.schema.json",
    )
    index = _validate_pair(
        knowledge_dir / "species-index.json",
        knowledge_dir / "species-index.schema.json",
    )

    if full["dataset_version"] != index["dataset_version"]:
        raise ValueError("Full knowledge snapshot and compact species index use different dataset versions")
    if full["source"]["commit"] != index["source_commit"]:
        raise ValueError("Full knowledge snapshot and compact species index use different source commits")
    if index["entry_count"] != len(full["entries"]) or index["entry_count"] != len(index["entries"]):
        raise ValueError("Knowledge entry counts do not reconcile")
    if index["dex_count"] != len({entry["dex"] for entry in full["entries"]}):
        raise ValueError("Knowledge Pokédex count does not reconcile")

    full_keys = [
        (entry["dex"], entry["species_id"], entry["form_key"])
        for entry in full["entries"]
    ]
    index_keys = [
        (entry["dex"], entry["species_id"], entry["form_key"])
        for entry in index["entries"]
    ]
    if full_keys != index_keys:
        raise ValueError("Compact species index does not preserve the full knowledge entry order/identity")
    if len(full_keys) != len(set(full_keys)):
        raise ValueError("Knowledge snapshot contains duplicate dex/species/form identities")
    if any(str(entry["species_id"]).endswith("_shadow") for entry in full["entries"]):
        raise ValueError("Knowledge snapshot must not duplicate owned Shadow status as a species form")

    quality_path = output_dir / "data" / "scan-quality-report.json"
    if quality_path.is_file():
        quality = _load(quality_path)
        knowledge = quality.get("knowledge") or {}
        if knowledge.get("dataset_version") != full["dataset_version"]:
            raise ValueError("Scan-quality semantics use a different knowledge dataset version")
        if knowledge.get("source_commit") != full["source"]["commit"]:
            raise ValueError("Scan-quality semantics use a different knowledge source commit")
