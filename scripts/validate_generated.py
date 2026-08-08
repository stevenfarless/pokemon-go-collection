#!/usr/bin/env python3
"""Validate generated collection resources against published schemas and build invariants."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

try:
    from .knowledge_contracts import validate_published_knowledge
    from .public_contracts import validate_public_resources
except ImportError:
    from knowledge_contracts import validate_published_knowledge
    from public_contracts import validate_public_resources


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_pair(data_path: Path, schema_path: Path) -> None:
    schema = load_json(schema_path)
    instance = load_json(data_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(instance),
        key=lambda item: list(item.path),
    )
    if errors:
        details = []
        for error in errors[:20]:
            location = "/".join(str(part) for part in error.absolute_path) or "<root>"
            details.append(f"{data_path.name}:{location}: {error.message}")
        extra = len(errors) - len(details)
        if extra > 0:
            details.append(f"... and {extra} more validation errors")
        raise ValueError("\n".join(details))


def validate_generated(output_dir: Path) -> None:
    data_dir = output_dir / "data"
    required_pairs = (
        (data_dir / "pokemon.json", data_dir / "schema.json"),
        (data_dir / "collection-summary.json", data_dir / "collection-summary.schema.json"),
        (data_dir / "build-manifest.json", data_dir / "build-manifest.schema.json"),
    )
    optional_pairs = (
        (data_dir / "data-health.json", data_dir / "data-health.schema.json"),
        (data_dir / "insights.json", data_dir / "insights.schema.json"),
    )
    for data_path, schema_path in required_pairs:
        validate_pair(data_path, schema_path)
    for data_path, schema_path in optional_pairs:
        if data_path.exists() or schema_path.exists():
            if not data_path.exists() or not schema_path.exists():
                raise ValueError(
                    f"Companion contract must publish both {data_path.name} and {schema_path.name}"
                )
            validate_pair(data_path, schema_path)

    # The low-level collection builder is still unit-tested independently and predates
    # the authoritative resource registry. The canonical dashboard build always
    # publishes `resources`, so coordinated invariants become mandatory there.
    manifest = load_json(data_dir / "build-manifest.json")
    if manifest.get("resources"):
        validate_public_resources(output_dir)
        validate_published_knowledge(output_dir)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    validate_generated(args.output.resolve())
    print(f"Validated generated JSON contracts and cross-resource invariants in {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
