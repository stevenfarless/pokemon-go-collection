"""JSON schemas for Today, Reference, and global-search resources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

try:
    from . import manifest_registry
except ImportError:
    import manifest_registry

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


def _nullable_string() -> dict[str, Any]:
    return {"type": ["string", "null"]}


def _card_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "id",
            "kind",
            "title",
            "summary",
            "why",
            "warnings",
            "priority",
            "route",
            "dismissible",
            "safety_critical",
            "evidence_layer",
        ],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "kind": {"type": "string", "minLength": 1},
            "title": {"type": "string", "minLength": 1},
            "summary": {"type": "string"},
            "why": {"type": "array", "items": {"type": "string"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "priority": {"type": "integer", "minimum": 0},
            "deadline": _nullable_string(),
            "cost": {},
            "reversibility": {"type": "string", "minLength": 1},
            "route": {"type": "string", "minLength": 1},
            "source_resource": _nullable_string(),
            "source_reference": _nullable_string(),
            "provider": _nullable_string(),
            "dataset_timestamp": _nullable_string(),
            "freshness": {"type": ["object", "null"]},
            "dismissible": {"type": "boolean"},
            "safety_critical": {"type": "boolean"},
            "evidence_layer": {"type": "string", "minLength": 1},
        },
        "additionalProperties": True,
    }


def schemas() -> dict[str, dict[str, Any]]:
    nonempty = {"type": "string", "minLength": 1}
    count = {"type": "integer", "minimum": 0}
    card = _card_schema()
    return {
        "today.schema.json": _schema(
            "today",
            ["schema_version", "product_version", "build_id", "top_actions", "sections", "safety"],
            {
                "schema_version": {"const": "1.0.0"},
                "product_version": {"const": "1.0.0"},
                "build_id": {"type": "string", "pattern": "^[0-9a-f]{12}$"},
                "generated_at": _nullable_string(),
                "export_timestamp": _nullable_string(),
                "top_actions": {"type": "array", "maxItems": 5, "items": card},
                "sections": {
                    "type": "object",
                    "required": ["now", "my_collection", "build_opportunities", "event_prep", "roster_gaps", "data_health"],
                    "properties": {
                        key: {"type": "object"}
                        for key in ("now", "my_collection", "build_opportunities", "event_prep", "roster_gaps", "data_health")
                    },
                    "additionalProperties": True,
                },
                "safety": {
                    "type": "object",
                    "required": ["current_claim_requires", "stale_current_data", "dismissal_policy", "business_logic"],
                    "properties": {
                        "current_claim_requires": nonempty,
                        "stale_current_data": nonempty,
                        "dismissal_policy": nonempty,
                        "business_logic": nonempty,
                    },
                    "additionalProperties": False,
                },
            },
        ),
        "reference-index.schema.json": _schema(
            "reference-index",
            [
                "schema_version",
                "product_version",
                "build_id",
                "knowledge_dataset_version",
                "classification",
                "route_pattern",
                "knowledge_resource",
                "entry_count",
                "owned_entry_count",
                "entries",
                "current_data_contract",
            ],
            {
                "schema_version": {"const": "1.0.0"},
                "product_version": {"const": "1.0.0"},
                "build_id": {"type": "string", "pattern": "^[0-9a-f]{12}$"},
                "knowledge_dataset_version": nonempty,
                "classification": nonempty,
                "route_pattern": {"const": "reference.html?species={canonical_species_id}"},
                "knowledge_resource": {"const": "data/knowledge/pokemon-go.json"},
                "entry_count": count,
                "owned_entry_count": count,
                "entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "dex",
                            "species_id",
                            "display_name",
                            "form_key",
                            "types",
                            "released",
                            "owned_count",
                            "owned_record_ids",
                            "route",
                        ],
                        "properties": {
                            "dex": {"type": "integer", "minimum": 1},
                            "species_id": nonempty,
                            "display_name": nonempty,
                            "base_name": _nullable_string(),
                            "form_label": _nullable_string(),
                            "form_key": nonempty,
                            "form_aliases": {"type": "array", "items": {"type": "string"}},
                            "types": {"type": "array", "items": {"type": "string"}},
                            "family_id": _nullable_string(),
                            "released": {"type": "boolean"},
                            "transformation_kind": _nullable_string(),
                            "owned_count": count,
                            "owned_record_ids": {"type": "array", "items": {"type": "string", "minLength": 1}},
                            "route": {"type": "string", "pattern": "^reference\\.html\\?species="},
                        },
                        "additionalProperties": True,
                    },
                },
                "current_data_contract": {
                    "type": "object",
                    "required": ["index", "required_freshness", "rule"],
                    "properties": {
                        "index": {"const": "data/external/index.json"},
                        "required_freshness": {"const": "fresh"},
                        "rule": nonempty,
                    },
                    "additionalProperties": False,
                },
            },
        ),
        "global-search-index.schema.json": _schema(
            "global-search-index",
            [
                "schema_version",
                "product_version",
                "build_id",
                "knowledge_resource",
                "item_count",
                "domain_counts",
                "domain_order",
                "current_data_policy",
                "items",
            ],
            {
                "schema_version": {"const": "1.0.0"},
                "product_version": {"const": "1.0.0"},
                "build_id": {"type": "string", "pattern": "^[0-9a-f]{12}$"},
                "knowledge_resource": {"const": "data/knowledge/pokemon-go.json"},
                "item_count": count,
                "domain_counts": {
                    "type": "object",
                    "additionalProperties": count,
                },
                "domain_order": {"type": "array", "items": {"type": "string", "minLength": 1}},
                "current_data_policy": nonempty,
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "domain", "title", "subtitle", "route", "terms"],
                        "properties": {
                            "id": nonempty,
                            "domain": {
                                "type": "string",
                                "enum": [
                                    "action",
                                    "owned-record",
                                    "owned-species",
                                    "reference",
                                    "family",
                                    "type",
                                    "move",
                                    "mechanic",
                                    "current",
                                    "saved-view",
                                ],
                            },
                            "title": {"type": "string"},
                            "subtitle": {"type": "string"},
                            "route": nonempty,
                            "terms": {"type": "array", "items": {"type": "string"}},
                            "freshness": {"type": "string", "enum": ["fresh"]},
                            "source_reference": _nullable_string(),
                            "dataset_timestamp": _nullable_string(),
                        },
                        "additionalProperties": True,
                    },
                },
            },
        ),
    }


def publish_product_schemas(output_dir: Path) -> None:
    """Write schemas and install their manifest-registry mappings before finalization."""
    mappings = {
        "data/today.json": "data/today.schema.json",
        "data/reference/index.json": "data/reference-index.schema.json",
        "data/global-search-index.json": "data/global-search-index.schema.json",
    }
    manifest_registry._SCHEMA_MAP.update(mappings)
    manifest_registry._STABLE_NAMES.update(
        {
            "data/today.json": "today_action_center",
            "data/reference/index.json": "reference_index",
            "data/global-search-index.json": "global_search_index",
            "data/today.schema.json": "today_action_center_schema",
            "data/reference-index.schema.json": "reference_index_schema",
            "data/global-search-index.schema.json": "global_search_index_schema",
        }
    )
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename, schema in schemas().items():
        Draft202012Validator.check_schema(schema)
        (data_dir / filename).write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )


__all__ = ["publish_product_schemas", "schemas"]
