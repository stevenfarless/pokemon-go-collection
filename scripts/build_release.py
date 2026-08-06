#!/usr/bin/env python3
"""Build the production site with semantic validation and startup optimization."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Callable

try:
    from . import build_collection as base
    from .semantic_validation import Diagnostic, validate_rows
except ImportError:  # Direct execution
    import build_collection as base
    from semantic_validation import Diagnostic, validate_rows

DIAGNOSTICS_POLICY_VERSION = "1.0.0"


def _json_write(path: Path, payload: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
        ) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _hash_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def _unique_strings(values: list[Any]) -> list[str]:
    return sorted(
        {str(value) for value in values if value not in (None, "")},
        key=lambda value: value.casefold(),
    )


def build_filter_options(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        "species": _unique_strings([record.get("name") for record in records]),
        "forms": _unique_strings([record.get("form") for record in records]),
        "genders": _unique_strings([record.get("gender") for record in records]),
        "fast_moves": _unique_strings([record.get("moves", {}).get("fast") for record in records]),
        "charged_moves": _unique_strings([
            move
            for record in records
            for move in (
                record.get("moves", {}).get("charged"),
                record.get("moves", {}).get("charged_second"),
            )
        ]),
        "evolutions": _unique_strings([
            league.get("evolution_name")
            for record in records
            for league in record.get("pvp", {}).values()
            if isinstance(league, dict)
        ]),
    }


def _replace_asset_reference(output_dir: Path, old_path: str, new_path: str) -> None:
    for filename in ("index.html", "404.html"):
        path = output_dir / filename
        source = path.read_text(encoding="utf-8")
        if old_path not in source:
            raise ValueError(f"Generated {filename} does not reference {old_path}")
        path.write_text(source.replace(old_path, new_path), encoding="utf-8", newline="\n")


def _inject_gender_options(output_dir: Path, genders: list[str]) -> None:
    options = '<option value="any">Any gender</option>' + "".join(
        f'<option value="{html.escape(value, quote=True)}">{html.escape(value)}</option>'
        for value in genders
    )
    pattern = re.compile(r'(<select id="gender-filter">).*?(</select>)', re.DOTALL)
    for filename in ("index.html", "404.html"):
        path = output_dir / filename
        source = path.read_text(encoding="utf-8")
        updated, count = pattern.subn(rf"\1{options}\2", source, count=1)
        if count != 1:
            raise ValueError(f"Generated {filename} is missing the gender filter")
        path.write_text(updated, encoding="utf-8", newline="\n")


def optimized_version_assets(
    original: Callable[[Path, Path, str], dict[str, str]],
    output_dir: Path,
    site_dir: Path,
    build_id: str,
) -> dict[str, str]:
    """Wrap the normal asset build with lazy options and yielded initialization."""
    assets = original(output_dir, site_dir, build_id)
    payload = json.loads((output_dir / "data" / "pokemon.json").read_text(encoding="utf-8"))
    options = build_filter_options(payload["records"])
    options_text = json.dumps(options, ensure_ascii=False, separators=(",", ":")) + "\n"
    options_name = f"filter-options.{_hash_text(options_text)}.json"
    options_path = f"data/{options_name}"
    (output_dir / options_path).write_text(options_text, encoding="utf-8", newline="\n")
    _inject_gender_options(output_dir, options["genders"])

    old_app_path = assets["app"]
    app_file = output_dir / old_app_path
    app_source = app_file.read_text(encoding="utf-8")
    if "    populateDynamicOptions();\n" not in app_source:
        raise ValueError("Application source no longer contains the expected eager option population")
    app_source = app_source.replace("    populateDynamicOptions();\n", "", 1)
    app_source = app_source.replace(
        "async function initialize() {\n",
        'async function initialize() {\n  performance.mark("collection-init-start");\n',
        1,
    )
    marker = "    applyFilters({ resetPage: false });"
    position = app_source.rfind(marker)
    if position < 0:
        raise ValueError("Application source no longer contains the expected initial filter pass")
    replacement = (
        "    await new Promise((resolve) => requestAnimationFrame(resolve));\n"
        f"{marker}\n"
        '    performance.mark("collection-init-end");\n'
        '    performance.measure("collection-initialize", "collection-init-start", "collection-init-end");'
    )
    app_source = app_source[:position] + replacement + app_source[position + len(marker):]
    app_name = f"app.{_hash_text(app_source)}.js"
    new_app_path = f"assets/{app_name}"
    (output_dir / new_app_path).write_text(app_source, encoding="utf-8", newline="\n")
    app_file.unlink()
    _replace_asset_reference(output_dir, old_app_path, new_app_path)
    assets["app"] = new_app_path

    old_accessibility_path = assets["accessibility"]
    accessibility_file = output_dir / old_accessibility_path
    accessibility_source = accessibility_file.read_text(encoding="utf-8")
    if "__FILTER_OPTIONS_PATH__" not in accessibility_source:
        raise ValueError("Accessibility source is missing the filter-options placeholder")
    accessibility_source = accessibility_source.replace("__FILTER_OPTIONS_PATH__", options_path)
    accessibility_name = f"accessibility.{_hash_text(accessibility_source)}.js"
    new_accessibility_path = f"assets/{accessibility_name}"
    (output_dir / new_accessibility_path).write_text(
        accessibility_source, encoding="utf-8", newline="\n"
    )
    accessibility_file.unlink()
    _replace_asset_reference(output_dir, old_accessibility_path, new_accessibility_path)
    assets["accessibility"] = new_accessibility_path
    assets["filter_options"] = options_path
    return assets


def _patch_manifest_schema(schema: dict[str, Any]) -> None:
    required = schema.setdefault("required", [])
    if "diagnostics" not in required:
        required.append("diagnostics")
    if "performance" not in required:
        required.append("performance")
    properties = schema.setdefault("properties", {})
    properties["diagnostics"] = {
        "type": "object",
        "required": ["policy_version", "warning_count", "error_count", "report"],
        "properties": {
            "policy_version": {"type": "string", "const": DIAGNOSTICS_POLICY_VERSION},
            "warning_count": {"type": "integer", "minimum": 0},
            "error_count": {"type": "integer", "const": 0},
            "report": {"type": "string", "const": "data/build-diagnostics.json"},
        },
        "additionalProperties": False,
    }
    properties["performance"] = {
        "type": "object",
        "required": ["record_count", "filter_options", "datalist_strategy", "initialization_yield"],
        "properties": {
            "record_count": {"type": "integer", "minimum": 1},
            "filter_options": {"type": "string", "pattern": "^data/filter-options\\.[0-9a-f]{12}\\.json$"},
            "datalist_strategy": {"type": "string", "const": "load on first filter drawer open"},
            "initialization_yield": {"type": "string", "const": "requestAnimationFrame before initial filter/sort"},
        },
        "additionalProperties": False,
    }
    assets = properties.get("assets", {})
    asset_properties = assets.setdefault("properties", {})
    asset_properties["filter_options"] = {
        "type": "string", "pattern": "^data/filter-options\\.[0-9a-f]{12}\\.json$"
    }
    assets["additionalProperties"] = False


def _publish_diagnostics(
    output_dir: Path,
    manifest: dict[str, Any],
    warnings: list[Diagnostic],
) -> None:
    report = {
        "policy_version": DIAGNOSTICS_POLICY_VERSION,
        "summary": {
            "warning_count": len(warnings),
            "error_count": 0,
        },
        "policy": {
            "fatal": "Missing or malformed Name, Pokemon Number, or CP stops the build.",
            "warning": "Malformed optional values are published as null/false/normal only with an exact row-level warning.",
            "blank": "Blank optional values are treated as intentionally missing and do not produce warnings.",
        },
        "warnings": [warning.to_dict() for warning in warnings],
        "errors": [],
    }
    _json_write(output_dir / "data" / "build-diagnostics.json", report)

    manifest["diagnostics"] = {
        "policy_version": DIAGNOSTICS_POLICY_VERSION,
        "warning_count": len(warnings),
        "error_count": 0,
        "report": "data/build-diagnostics.json",
    }
    manifest["performance"] = {
        "record_count": manifest["pokemon_count"],
        "filter_options": manifest["assets"]["filter_options"],
        "datalist_strategy": "load on first filter drawer open",
        "initialization_yield": "requestAnimationFrame before initial filter/sort",
    }

    manifest_path = output_dir / "data" / "build-manifest.json"
    payload_path = output_dir / "data" / "pokemon.json"
    manifest_schema_path = output_dir / "data" / "build-manifest.schema.json"
    payload_schema_path = output_dir / "data" / "schema.json"

    manifest_schema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))
    _patch_manifest_schema(manifest_schema)
    _json_write(manifest_schema_path, manifest_schema)

    payload_schema = json.loads(payload_schema_path.read_text(encoding="utf-8"))
    _patch_manifest_schema(payload_schema["$defs"]["manifest"])
    _json_write(payload_schema_path, payload_schema)

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["manifest"] = manifest
    _json_write(payload_path, payload, compact=True)
    _json_write(manifest_path, manifest)

    llms_path = output_dir / "llms.txt"
    llms = llms_path.read_text(encoding="utf-8")
    llms += (
        "\nSemantic validation:\n"
        f"- Warning count: {len(warnings)}\n"
        "- Error count: 0\n"
        "- Exact row-level diagnostics: /data/build-diagnostics.json\n"
        "- Filter options are precomputed and loaded only when the filter drawer is first opened.\n"
    )
    llms_path.write_text(llms, encoding="utf-8", newline="\n")


def build(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    warnings_holder: dict[str, list[Diagnostic]] = {"warnings": []}

    def validated_reader(path: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            report = base.analyze_source_columns(fieldnames)
            missing = report["missing_required_columns"]
            if missing:
                raise ValueError("Newest export is missing required columns: " + ", ".join(missing))
            rows, warnings = validate_rows(fieldnames, reader)
        if not rows:
            raise ValueError("Newest export contains no Pokémon rows")
        warnings_holder["warnings"] = warnings
        report["warnings"] = [*report["warnings"], *(warning.format() for warning in warnings)]
        records = [base.legacy.normalize_row(row, row_number) for row_number, row in enumerate(rows, start=2)]
        return fieldnames, records, report

    original_reader = base.read_compatible_export
    original_version_assets = base.version_assets
    base.read_compatible_export = validated_reader
    base.version_assets = lambda output, site, build_id: optimized_version_assets(
        original_version_assets, output, site, build_id
    )
    try:
        manifest = base.build(repository_root, output_dir)
    finally:
        base.read_compatible_export = original_reader
        base.version_assets = original_version_assets

    _publish_diagnostics(output_dir, manifest, warnings_holder["warnings"])
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "dist").resolve()
    manifest = build(root, output)
    print(
        f"Built {manifest['pokemon_count']} Pokémon with "
        f"{manifest['diagnostics']['warning_count']} warning(s) into {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
