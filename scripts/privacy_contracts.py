"""Public schema contracts for privacy and static-web security audit resources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

try:
    from .security_contracts import publish_security_schema
except ImportError:
    from security_contracts import publish_security_schema

BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"


def privacy_audit_schema() -> dict[str, Any]:
    nonempty = {"type": "string", "minLength": 1}
    string_array = {"type": "array", "items": {"type": "string"}}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE_ID + "privacy-audit.schema.json",
        "title": "Privacy Audit",
        "type": "object",
        "required": [
            "schema_version",
            "profile",
            "deployment_allowed",
            "friend_code_public",
            "public_title",
            "detected_sensitive_source_columns",
            "redacted_columns",
            "redacted_resource_count",
            "redacted_resources",
            "published_export_sha256",
            "source_hash_semantics",
            "canonical_identity_policy",
            "browser_local_namespaces_public",
            "publication_boundary",
        ],
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "profile": {
                "type": "string",
                "enum": ["full-public", "redacted", "private-local-preview"],
            },
            "deployment_allowed": {"type": "boolean"},
            "friend_code_public": {"type": "boolean"},
            "public_title": nonempty,
            "detected_sensitive_source_columns": string_array,
            "redacted_columns": string_array,
            "redacted_resource_count": {"type": "integer", "minimum": 0},
            "redacted_resources": string_array,
            "published_export_sha256": {
                "oneOf": [
                    {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    {"type": "null"},
                ]
            },
            "source_hash_semantics": nonempty,
            "canonical_identity_policy": nonempty,
            "browser_local_namespaces_public": {"type": "boolean", "const": False},
            "publication_boundary": {
                "type": "array",
                "minItems": 1,
                "items": nonempty,
            },
        },
        "additionalProperties": False,
    }


def publish_privacy_schema(output_dir: Path) -> None:
    schema = privacy_audit_schema()
    Draft202012Validator.check_schema(schema)
    path = output_dir / "data" / "privacy-audit.schema.json"
    path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    publish_security_schema(output_dir)


__all__ = ["privacy_audit_schema", "publish_privacy_schema"]
