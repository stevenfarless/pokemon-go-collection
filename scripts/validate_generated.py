#!/usr/bin/env python3
"""Validate generated collection resources against their published JSON Schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


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
    pairs = (
        (data_dir / "pokemon.json", data_dir / "schema.json"),
        (data_dir / "collection-summary.json", data_dir / "collection-summary.schema.json"),
        (data_dir / "build-manifest.json", data_dir / "build-manifest.schema.json"),
        (data_dir / "data-health.json", data_dir / "data-health.schema.json"),
        (data_dir / "insights.json", data_dir / "insights.schema.json"),
    )
    for data_path, schema_path in pairs:
        validate_pair(data_path, schema_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    validate_generated(args.output.resolve())
    print(f"Validated generated JSON contracts in {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
