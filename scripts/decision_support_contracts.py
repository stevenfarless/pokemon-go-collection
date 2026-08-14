"""Schemas and cross-resource invariants for deterministic decision support and external data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"


def _schema(name: str, required: list[str], properties: dict[str, Any], *, additional: bool = True) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE_ID + name,
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": additional,
    }


def _record_ref() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["record_id", "pokemon_number", "name", "reasons", "warnings", "inputs"],
        "properties": {
            "record_id": {"type": "string", "pattern": "^pgc_[0-9a-f]{20}$"},
            "pokemon_number": {"type": "integer", "minimum": 1},
            "name": {"type": "string", "minLength": 1},
            "form": {"type": ["string", "null"]},
            "cp": {"type": ["integer", "null"], "minimum": 0},
            "reasons": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}, "uniqueItems": True},
            "warnings": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "inputs": {"type": "object"},
        },
        "additionalProperties": False,
    }


def schemas() -> dict[str, dict[str, Any]]:
    count = {"type": "integer", "minimum": 0}
    build_id = {"type": "string", "pattern": "^[0-9a-f]{12}$"}
    nonempty = {"type": "string", "minLength": 1}
    recommendation_index = _schema(
        "recommendation-index.schema.json",
        ["schema_version", "decision_support_version", "build_id", "current_meta_embedded", "queue_count", "queues"],
        {
            "schema_version": nonempty,
            "decision_support_version": nonempty,
            "build_id": build_id,
            "current_meta_embedded": {"const": False},
            "queue_count": count,
            "queues": {"type": "array", "items": {"type": "object"}},
        },
    )
    recommendation_queue = _schema(
        "recommendation-queue.schema.json",
        ["schema_version", "decision_support_version", "build_id", "queue", "definition", "record_count", "records", "safety"],
        {
            "schema_version": nonempty,
            "decision_support_version": nonempty,
            "build_id": build_id,
            "queue": nonempty,
            "definition": nonempty,
            "record_count": count,
            "records": {"type": "array", "items": _record_ref()},
            "safety": {
                "type": "object",
                "required": ["automatic_action", "irreversible_actions", "current_meta_embedded"],
                "properties": {
                    "automatic_action": {"const": False},
                    "irreversible_actions": {"const": "review-only"},
                    "current_meta_embedded": {"const": False},
                },
            },
        },
    )
    candidate_index = _schema(
        "candidate-index.schema.json",
        ["schema_version", "decision_support_version", "build_id", "feed_count", "feeds", "current_meta_embedded"],
        {
            "schema_version": nonempty,
            "decision_support_version": nonempty,
            "build_id": build_id,
            "knowledge_dataset_version": {"type": ["string", "null"]},
            "feed_count": count,
            "feeds": {"type": "array", "items": {"type": "object"}},
            "current_meta_embedded": {"const": False},
        },
    )
    candidate_feed = _schema(
        "candidate-feed.schema.json",
        ["schema_version", "decision_support_version", "build_id", "feed", "status", "definition", "candidate_count", "candidates", "current_meta_embedded"],
        {
            "schema_version": nonempty,
            "decision_support_version": nonempty,
            "build_id": build_id,
            "feed": nonempty,
            "status": {"type": "string", "enum": ["available", "unavailable"]},
            "definition": nonempty,
            "unavailable_reason": {"type": ["string", "null"]},
            "candidate_count": count,
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["record_id", "pokemon_number", "name", "feed", "eligibility", "warnings"],
                    "properties": {
                        "record_id": {"type": "string", "pattern": "^pgc_[0-9a-f]{20}$"},
                        "pokemon_number": {"type": "integer", "minimum": 1},
                        "name": nonempty,
                        "feed": nonempty,
                        "eligibility": {"type": "object"},
                        "warnings": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "current_meta_embedded": {"const": False},
        },
    )
    investment_index = _schema(
        "investment-index.schema.json",
        ["schema_version", "model_version", "build_id", "record_count", "records", "basis"],
        {
            "schema_version": nonempty,
            "model_version": nonempty,
            "build_id": build_id,
            "record_count": count,
            "records": {"const": "data/investments/records.json"},
            "basis": {"type": "array", "items": {"type": "string"}},
        },
    )
    investment_records = _schema(
        "investment-records.schema.json",
        ["schema_version", "model_version", "build_id", "record_count", "records", "limitations"],
        {
            "schema_version": nonempty,
            "model_version": nonempty,
            "build_id": build_id,
            "record_count": count,
            "records": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["record_id", "pokemon_number", "name", "observed", "derived", "warnings", "model"],
                    "properties": {
                        "record_id": {"type": "string", "pattern": "^pgc_[0-9a-f]{20}$"},
                        "pokemon_number": {"type": "integer", "minimum": 1},
                        "name": nonempty,
                        "observed": {"type": "object"},
                        "derived": {"type": "object"},
                        "warnings": {"type": "array", "items": {"type": "string"}},
                        "model": {"type": "object"},
                    },
                },
            },
            "limitations": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        },
    )
    reasoning_index = _schema(
        "reasoning-index.schema.json",
        ["schema_version", "engine_version", "build_id", "rules", "records", "record_count", "deterministic", "llm_required"],
        {
            "schema_version": nonempty,
            "engine_version": nonempty,
            "build_id": build_id,
            "rules": {"const": "data/reasoning/rules.json"},
            "records": {"const": "data/reasoning/records.json"},
            "record_count": count,
            "deterministic": {"const": True},
            "llm_required": {"const": False},
        },
    )
    reasoning_rules = _schema(
        "reasoning-rules.schema.json",
        ["schema_version", "engine_version", "rules", "forbidden_automatic_actions"],
        {
            "schema_version": nonempty,
            "engine_version": nonempty,
            "rules": {"type": "array", "minItems": 1, "items": {"type": "object"}},
            "forbidden_automatic_actions": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        },
    )
    reasoning_records = _schema(
        "reasoning-records.schema.json",
        ["schema_version", "engine_version", "build_id", "external_freshness", "record_count", "records", "safety"],
        {
            "schema_version": nonempty,
            "engine_version": nonempty,
            "build_id": build_id,
            "external_freshness": {"type": "string", "enum": ["fresh", "stale", "expired", "unavailable", "failed-update"]},
            "record_count": count,
            "records": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["record_id", "pokemon_number", "name", "recommendations", "irreversible_actions_blocked", "source_versions"],
                    "properties": {
                        "record_id": {"type": "string", "pattern": "^pgc_[0-9a-f]{20}$"},
                        "pokemon_number": {"type": "integer", "minimum": 1},
                        "name": nonempty,
                        "recommendations": {"type": "array", "items": {"type": "object"}},
                        "irreversible_actions_blocked": {"type": "array", "items": {"type": "string"}},
                        "source_versions": {"type": "object"},
                    },
                },
            },
            "safety": {"type": "object"},
        },
    )
    external_index = _schema(
        "external-index.schema.json",
        ["schema_version", "framework_version", "build_id", "overall_freshness", "snapshot_count", "classifications", "data_categories", "failure_policy", "architecture", "snapshots"],
        {
            "schema_version": nonempty,
            "framework_version": nonempty,
            "build_id": build_id,
            "overall_freshness": {"type": "string", "enum": ["fresh", "stale", "expired", "unavailable", "failed-update"]},
            "snapshot_count": count,
            "classifications": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "data_categories": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "failure_policy": {"type": "object"},
            "architecture": {"type": "object"},
            "snapshots": {"type": "array", "items": {"type": "object"}},
            "design_document": nonempty,
            "snapshot_contract": {"const": "data/external-snapshot.schema.json"},
        },
    )
    external_snapshot = _schema(
        "external-snapshot.schema.json",
        ["schema_version", "framework_version", "provider", "source_reference", "retrieved_at", "dataset_timestamp", "data_category", "classification", "data_version", "provider_schema_version", "license", "join_keys", "freshness_policy", "freshness", "facts"],
        {
            "schema_version": nonempty,
            "framework_version": nonempty,
            "provider": nonempty,
            "source_reference": nonempty,
            "retrieved_at": nonempty,
            "dataset_timestamp": nonempty,
            "data_category": {"type": "string", "enum": ["pvp", "raids", "moves", "events", "rocket", "max-battles", "mechanics"]},
            "classification": {"type": "string", "enum": ["Official", "Verified community data", "Simulation result", "Datamined", "Reported"]},
            "data_version": nonempty,
            "provider_schema_version": nonempty,
            "license": {"type": "object"},
            "join_keys": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "freshness_policy": {"type": "object"},
            "freshness": {"type": "object"},
            "facts": {"type": "array", "items": {"type": "object"}},
        },
    )
    return {
        "recommendation-index.schema.json": recommendation_index,
        "recommendation-queue.schema.json": recommendation_queue,
        "candidate-index.schema.json": candidate_index,
        "candidate-feed.schema.json": candidate_feed,
        "investment-index.schema.json": investment_index,
        "investment-records.schema.json": investment_records,
        "reasoning-index.schema.json": reasoning_index,
        "reasoning-rules.schema.json": reasoning_rules,
        "reasoning-records.schema.json": reasoning_records,
        "external-index.schema.json": external_index,
        "external-snapshot.schema.json": external_snapshot,
    }


def publish_decision_support_schemas(output_dir: Path) -> None:
    data_dir = output_dir / "data"
    for filename, schema in schemas().items():
        Draft202012Validator.check_schema(schema)
        (data_dir / filename).write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_decision_support(output_dir: Path) -> None:
    data = output_dir / "data"
    canonical = _load(data / "pokemon.json")["records"]
    canonical_ids = {_record["identity"]["record_id"] for _record in canonical}
    build_id = _load(data / "build-manifest.json")["build_id"]

    resources = [
        (data / "recommendations" / "index.json", data / "recommendation-index.schema.json"),
        (data / "candidates" / "index.json", data / "candidate-index.schema.json"),
        (data / "investments" / "index.json", data / "investment-index.schema.json"),
        (data / "investments" / "records.json", data / "investment-records.schema.json"),
        (data / "reasoning" / "index.json", data / "reasoning-index.schema.json"),
        (data / "reasoning" / "rules.json", data / "reasoning-rules.schema.json"),
        (data / "reasoning" / "records.json", data / "reasoning-records.schema.json"),
        (data / "external" / "index.json", data / "external-index.schema.json"),
    ]
    for instance_path, schema_path in resources:
        instance = _load(instance_path)
        schema = _load(schema_path)
        errors = list(Draft202012Validator(schema).iter_errors(instance))
        if errors:
            raise ValueError(f"{instance_path.name} fails {schema_path.name}: {errors[0].message}")
        if instance.get("build_id") not in (None, build_id):
            raise ValueError(f"{instance_path} belongs to a different build")

    rec_index = _load(data / "recommendations" / "index.json")
    for entry in rec_index["queues"]:
        payload = _load(output_dir / entry["path"])
        if payload["record_count"] != len(payload["records"]):
            raise ValueError(f"Recommendation queue count mismatch: {entry['name']}")
        if any(item["record_id"] not in canonical_ids for item in payload["records"]):
            raise ValueError(f"Recommendation queue references unknown record: {entry['name']}")
        if any(not item["reasons"] for item in payload["records"]):
            raise ValueError(f"Recommendation queue contains unexplained inclusion: {entry['name']}")

    candidate_index = _load(data / "candidates" / "index.json")
    for entry in candidate_index["feeds"]:
        payload = _load(output_dir / entry["path"])
        if payload["candidate_count"] != len(payload["candidates"]):
            raise ValueError(f"Candidate feed count mismatch: {entry['name']}")
        if any(item["record_id"] not in canonical_ids for item in payload["candidates"]):
            raise ValueError(f"Candidate feed references unknown record: {entry['name']}")
        if payload["current_meta_embedded"] is not False:
            raise ValueError(f"Candidate feed embeds current-meta claims: {entry['name']}")

    investment = _load(data / "investments" / "records.json")
    investment_ids = [item["record_id"] for item in investment["records"]]
    if len(investment_ids) != len(canonical_ids) or set(investment_ids) != canonical_ids:
        raise ValueError("Investment inputs must contain every canonical record exactly once")
    for item in investment["records"]:
        for build in item["derived"]["pvp_builds"]:
            if build.get("xl_candy_cost") is None and not build.get("xl_candy_cost_status"):
                raise ValueError("Missing XL Candy cost must be explicit")

    reasoning = _load(data / "reasoning" / "records.json")
    reasoning_ids = [item["record_id"] for item in reasoning["records"]]
    if len(reasoning_ids) != len(canonical_ids) or set(reasoning_ids) != canonical_ids:
        raise ValueError("Reasoning results must contain every canonical record exactly once")
    forbidden = {"transfer", "purify", "elite_tm", "evolve", "power_up_spend"}
    for item in reasoning["records"]:
        for recommendation in item["recommendations"]:
            if recommendation.get("action_class") in forbidden:
                raise ValueError("Reasoning engine emitted a forbidden irreversible action")

    external = _load(data / "external" / "index.json")
    if external["snapshot_count"] != len(external["snapshots"]):
        raise ValueError("External-data snapshot count mismatch")
    architecture = external["architecture"]
    if architecture.get("runtime_server_required") or architecture.get("paid_service_required") or architecture.get("provider_required_for_core_collection"):
        raise ValueError("External-data framework violates the permanent zero-cost GitHub-only architecture")
