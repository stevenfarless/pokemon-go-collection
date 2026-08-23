"""Public schema contract for the generated static-web security policy."""

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


def security_policy_schema() -> dict[str, Any]:
    nonempty = {"type": "string", "minLength": 1}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE_ID + "security-policy.schema.json",
        "title": "Static Web Security Policy",
        "type": "object",
        "required": [
            "schema_version",
            "content_security_policy",
            "hosting",
            "limitations",
            "trusted_types",
            "unsafe_url_schemes",
        ],
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "content_security_policy": nonempty,
            "hosting": {"type": "string", "const": "GitHub Pages meta CSP"},
            "limitations": {"type": "array", "minItems": 1, "items": nonempty},
            "trusted_types": {
                "type": "string",
                "const": "evaluated-progressive-defense-not-enforced",
            },
            "unsafe_url_schemes": nonempty,
        },
        "additionalProperties": False,
    }


def publish_security_schema(output_dir: Path) -> None:
    schema = security_policy_schema()
    Draft202012Validator.check_schema(schema)
    path = output_dir / "data" / "security-policy.schema.json"
    path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    # The registry is constructed later in the same build process. Register the
    # policy/schema pair here so every public JSON resource keeps the strict
    # declared-schema invariant without special-casing validation.
    manifest_registry._SCHEMA_MAP["data/security-policy.json"] = "data/security-policy.schema.json"
    manifest_registry._STABLE_NAMES["data/security-policy.json"] = "security_policy"
    manifest_registry._STABLE_NAMES["data/security-policy.schema.json"] = "security_policy_schema"


__all__ = ["security_policy_schema", "publish_security_schema"]
