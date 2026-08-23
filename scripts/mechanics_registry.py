"""Publish the reviewed Pokémon GO mechanics coverage registry."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from . import manifest_registry
except ImportError:
    import manifest_registry

REGISTRY_VERSION = "1.0.0"
STATUSES = ("supported", "partial", "unsupported")
BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"


def schema() -> dict[str, Any]:
    nonempty = {"type": "string", "minLength": 1}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE_ID + "mechanics-registry.schema.json",
        "type": "object",
        "required": ["schema_version", "build_id", "reviewed_at", "authority_policy", "coverage", "sources", "domains"],
        "properties": {
            "schema_version": {"type": "string", "const": REGISTRY_VERSION},
            "build_id": {"type": "string", "pattern": "^[0-9a-f]{12}$"},
            "reviewed_at": nonempty,
            "authority_policy": nonempty,
            "coverage": {
                "type": "object",
                "required": ["supported", "partial", "unsupported", "total", "review_age_days", "state"],
                "properties": {
                    "supported": {"type": "integer", "minimum": 0},
                    "partial": {"type": "integer", "minimum": 0},
                    "unsupported": {"type": "integer", "minimum": 0},
                    "total": {"type": "integer", "minimum": 1},
                    "review_age_days": {"type": "integer", "minimum": 0},
                    "state": {"type": "string", "enum": ["current", "review-due"]},
                },
                "additionalProperties": False,
            },
            "sources": {"type": "array", "items": {"type": "object"}},
            "domains": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["id", "label", "status", "source_ids", "applicable_at", "affected_modules", "normalized_facts"],
                    "properties": {
                        "id": nonempty,
                        "label": nonempty,
                        "status": {"type": "string", "enum": list(STATUSES)},
                        "source_ids": {"type": "array", "items": {"type": "string"}},
                        "applicable_at": nonempty,
                        "affected_modules": {"type": "array", "items": {"type": "string"}},
                        "normalized_facts": {"type": "array", "items": {"type": "string"}},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    }


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Mechanics registry must be an object")
    return payload


def _validate_source(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != REGISTRY_VERSION:
        raise ValueError("Unsupported mechanics registry schema version")
    sources = payload.get("sources")
    domains = payload.get("domains")
    if not isinstance(sources, list) or not isinstance(domains, list) or not domains:
        raise ValueError("Mechanics registry requires sources and domains")
    source_ids = {str(item.get("id")) for item in sources if isinstance(item, Mapping) and item.get("id")}
    if len(source_ids) != len(sources):
        raise ValueError("Mechanics source IDs must be present and unique")
    domain_ids: set[str] = set()
    for domain in domains:
        if not isinstance(domain, Mapping):
            raise ValueError("Mechanics domains must be objects")
        domain_id = str(domain.get("id") or "")
        if not domain_id or domain_id in domain_ids:
            raise ValueError("Mechanics domain IDs must be present and unique")
        domain_ids.add(domain_id)
        if domain.get("status") not in STATUSES:
            raise ValueError(f"Unsupported mechanics status for {domain_id}")
        unknown = set(domain.get("source_ids") or []) - source_ids
        if unknown:
            raise ValueError(f"Mechanics domain {domain_id} references unknown sources: {sorted(unknown)}")


def publish(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    source = _load(repository_root / "knowledge" / "mechanics-registry.json")
    _validate_source(source)
    reviewed = date.fromisoformat(str(source["reviewed_at"]))
    generated = str(manifest.get("generated_at_utc") or "")[:10]
    generated_date = date.fromisoformat(generated) if generated else date.today()
    age = max(0, (generated_date - reviewed).days)
    counts = {status: sum(1 for domain in source["domains"] if domain["status"] == status) for status in STATUSES}
    payload = dict(source)
    payload["build_id"] = manifest["build_id"]
    payload["coverage"] = {
        **counts,
        "total": len(source["domains"]),
        "review_age_days": age,
        "state": "review-due" if age > 180 else "current",
    }
    data_dir = output_dir / "data"
    schema_payload = schema()
    Draft202012Validator.check_schema(schema_payload)
    (data_dir / "mechanics-registry.schema.json").write_text(json.dumps(schema_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    mechanics_dir = data_dir / "mechanics"
    mechanics_dir.mkdir(parents=True, exist_ok=True)
    (mechanics_dir / "index.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    report = ["# Pokémon GO mechanics coverage", "", f"Reviewed: {payload['reviewed_at']}", f"Coverage state: {payload['coverage']['state']}", ""]
    for domain in payload["domains"]:
        report.append(f"- **{domain['label']}**: `{domain['status']}`")
    (output_dir / "mechanics-coverage.md").write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
    manifest_registry._SCHEMA_MAP["data/mechanics/index.json"] = "data/mechanics-registry.schema.json"
    manifest_registry._STABLE_NAMES["data/mechanics/index.json"] = "mechanics_registry"
    manifest_registry._STABLE_NAMES["data/mechanics-registry.schema.json"] = "mechanics_registry_schema"
    return payload


__all__ = ["REGISTRY_VERSION", "STATUSES", "schema", "publish"]
