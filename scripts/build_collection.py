#!/usr/bin/env python3
"""Build a versioned, schema-validated collection from the newest archived export."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

try:
    from . import build_site as legacy
    from .schema_contracts import (
        CORE_COLUMNS,
        EXPORT_SCHEMA_VERSION,
        NORMALIZED_SCHEMA_VERSION,
        analyze_source_columns,
        manifest_schema,
        pokemon_payload_schema,
        source_columns_document,
        summary_schema,
    )
except ImportError:  # Direct execution: python scripts/build_collection.py
    import build_site as legacy
    from schema_contracts import (
        CORE_COLUMNS,
        EXPORT_SCHEMA_VERSION,
        NORMALIZED_SCHEMA_VERSION,
        analyze_source_columns,
        manifest_schema,
        pokemon_payload_schema,
        source_columns_document,
        summary_schema,
    )


def discover_exports(repository_root: Path) -> list[legacy.ExportFile]:
    """Return timestamped exports located strictly under exports/."""
    archive_root = repository_root / "exports"
    exports: list[legacy.ExportFile] = []
    if not archive_root.is_dir():
        return exports

    for path in archive_root.rglob("*.csv"):
        relative_directories = path.relative_to(archive_root).parts[:-1]
        if any(part.startswith(".") for part in relative_directories):
            continue
        parsed = legacy.parse_export_filename(path)
        if parsed is not None:
            exports.append(parsed)

    return sorted(exports, key=lambda item: (item.timestamp, item.path.as_posix()))


def read_compatible_export(export_path: Path) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    """Read an export while treating non-core Poke Genie columns as optional."""
    with export_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        report = analyze_source_columns(fieldnames)
        missing_required = report["missing_required_columns"]
        if missing_required:
            raise ValueError("Newest export is missing required columns: " + ", ".join(missing_required))
        records = [legacy.normalize_row(row, index) for index, row in enumerate(reader, start=2)]

    if not records:
        raise ValueError("Newest export contains no Pokémon rows")
    return fieldnames, records, report


def _write_json(path: Path, payload: Any, *, compact: bool = False) -> None:
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


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def _minify_css(content: str) -> str:
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    content = re.sub(r"\s+", " ", content)
    content = re.sub(r"\s*([{}:;,>])\s*", r"\1", content)
    return content.strip()


def _replace_once(source: str, old: str, new: str, *, description: str) -> str:
    if old not in source:
        raise ValueError(f"Generated HTML is missing the expected {description}")
    return source.replace(old, new, 1)


def version_assets(output_dir: Path, site_dir: Path, build_id: str) -> dict[str, str]:
    """Inline critical CSS and emit content-hashed CSS/JavaScript assets."""
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    combined_css = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (site_dir / "styles.css", site_dir / "stability.css")
    )
    minified_css = _minify_css(combined_css)
    css_name = f"styles.{_content_hash(minified_css)}.css"
    (assets_dir / css_name).write_text(minified_css + "\n", encoding="utf-8", newline="\n")

    app_source = (site_dir / "app.js").read_text(encoding="utf-8")
    app_source = app_source.replace(
        'fetch("data/pokemon.json")',
        f'fetch("data/pokemon.json?v={build_id}")',
    ).replace(
        'fetch("data/collection-summary.json")',
        f'fetch("data/collection-summary.json?v={build_id}")',
    )
    app_name = f"app.{_content_hash(app_source)}.js"
    (assets_dir / app_name).write_text(app_source, encoding="utf-8", newline="\n")

    hardening_source = (site_dir / "hardening.js").read_text(encoding="utf-8")
    hardening_name = f"hardening.{_content_hash(hardening_source)}.js"
    (assets_dir / hardening_name).write_text(hardening_source, encoding="utf-8", newline="\n")

    accessibility_source = (site_dir / "accessibility.js").read_text(encoding="utf-8")
    accessibility_name = f"accessibility.{_content_hash(accessibility_source)}.js"
    (assets_dir / accessibility_name).write_text(accessibility_source, encoding="utf-8", newline="\n")

    for old_name in ("app.js", "styles.css", "hardening.js", "accessibility.js", "stability.css"):
        old_path = assets_dir / old_name
        if old_path.exists():
            old_path.unlink()

    css_path = f"assets/{css_name}"
    app_path = f"assets/{app_name}"
    hardening_path = f"assets/{hardening_name}"
    accessibility_path = f"assets/{accessibility_name}"
    css_markup = (
        f'<style data-critical-css>{minified_css}</style>\n'
        f'  <link rel="preload" href="{css_path}" as="style" '
        'onload="this.onload=null;this.rel=\'stylesheet\'">\n'
        f'  <noscript><link rel="stylesheet" href="{css_path}"></noscript>'
    )
    script_markup = (
        f'<script defer src="{app_path}"></script>\n'
        f'  <script defer src="{hardening_path}"></script>\n'
        f'  <script defer src="{accessibility_path}"></script>'
    )

    for filename in ("index.html", "404.html"):
        path = output_dir / filename
        source = path.read_text(encoding="utf-8")
        source = _replace_once(
            source,
            '<link rel="stylesheet" href="assets/styles.css">',
            css_markup,
            description="stylesheet reference",
        )
        source = _replace_once(
            source,
            '<script defer src="assets/app.js"></script>',
            script_markup,
            description="application script reference",
        )
        path.write_text(source, encoding="utf-8", newline="\n")

    return {
        "styles": css_path,
        "app": app_path,
        "hardening": hardening_path,
        "accessibility": accessibility_path,
    }


def update_documentation(output_dir: Path, manifest: dict[str, Any]) -> None:
    llms_path = output_dir / "llms.txt"
    summary_path = output_dir / "summary.md"
    if summary_path.exists():
        summary = summary_path.read_text(encoding="utf-8")
        summary = summary.replace(
            "- `data/schema.json`: field meanings and source-column information",
            "- `data/schema.json`: JSON Schema for `data/pokemon.json`\n- `data/source-columns.json`: source-column compatibility metadata",
        )
        summary_path.write_text(summary, encoding="utf-8", newline="\n")

    llms_path.write_text(
        f"""# Pokémon GO Collection

This static site presents the newest Poke Genie CSV export in a human-readable dashboard and structured machine-readable files.

Current source: {manifest['source_file']}
Export timestamp from filename: {manifest['export_timestamp']}
Pokémon count: {manifest['pokemon_count']}
Normalized schema version: {manifest['schema_version']}
Poke Genie export schema: {manifest['export_schema_version']}
Build identifier: {manifest['build_id']}
Schema warnings: {len(manifest['schema_warnings'])}

Preferred resources:
- /summary.md for a compact collection overview
- /data/collection-summary.json for aggregate statistics
- /data/pokemon.json for every normalized Pokémon record
- /data/schema.json for the JSON Schema that validates pokemon.json
- /data/collection-summary.schema.json for the summary contract
- /data/build-manifest.schema.json for the manifest contract
- /data/source-columns.json for required, optional, missing, and unknown CSV columns
- /data/build-manifest.json to verify freshness, source integrity, schema versions, and assets
- /data/latest-export.csv for the original newest CSV

Only Name, Pokemon Number, and CP are required source columns. Missing optional columns are represented as null, false, or normal values and are disclosed in the manifest. Unknown future columns are reported without stopping a build.

The repository preserves older exports. Published resources always use the single newest filename matching shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv under exports/.
""",
        encoding="utf-8",
        newline="\n",
    )


def update_generated_contracts(
    output_dir: Path,
    manifest: dict[str, Any],
    report: dict[str, Any],
) -> None:
    """Publish schemas and keep manifest copies synchronized."""
    _write_json(output_dir / "data" / "schema.json", pokemon_payload_schema())
    _write_json(output_dir / "data" / "collection-summary.schema.json", summary_schema())
    _write_json(output_dir / "data" / "build-manifest.schema.json", manifest_schema())
    _write_json(output_dir / "data" / "source-columns.json", source_columns_document(report))
    _write_json(output_dir / "data" / "build-manifest.json", manifest)

    payload_path = output_dir / "data" / "pokemon.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["manifest"] = manifest
    _write_json(payload_path, payload, compact=True)
    update_documentation(output_dir, manifest)


def build(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    """Build through the existing normalizer with compatibility and versioning layers."""
    report_holder: dict[str, dict[str, Any]] = {}

    def compatible_reader(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
        fieldnames, records, report = read_compatible_export(path)
        report_holder["report"] = report
        return fieldnames, records

    original_discovery: Callable[[Path], list[legacy.ExportFile]] = legacy.discover_exports
    original_reader = legacy.read_export
    legacy.discover_exports = discover_exports
    legacy.read_export = compatible_reader
    try:
        manifest = legacy.build(repository_root, output_dir)
    finally:
        legacy.discover_exports = original_discovery
        legacy.read_export = original_reader

    report = report_holder.get("report")
    if report is None:
        raise RuntimeError("Source-column report was not generated")

    build_id = hashlib.sha256(
        f"{manifest['source_sha256']}:{NORMALIZED_SCHEMA_VERSION}:{manifest['generated_at_utc']}".encode("utf-8")
    ).hexdigest()[:12]
    assets = version_assets(output_dir, repository_root / "site", build_id)

    manifest.update({
        "generator": "scripts/build_collection.py",
        "build_id": build_id,
        "schema_version": NORMALIZED_SCHEMA_VERSION,
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "required_columns": list(CORE_COLUMNS),
        "missing_required_columns": report["missing_required_columns"],
        "source_columns": report["source_columns"],
        "missing_optional_columns": report["missing_optional_columns"],
        "unknown_columns": report["unknown_columns"],
        "schema_warnings": report["warnings"],
        "optional_column_groups": report["optional_column_groups"],
        "assets": assets,
        "cache_policy": {
            "host": "GitHub Pages",
            "headers_controlled_by": "GitHub Pages",
            "asset_strategy": "content-hashed filenames",
            "data_version_parameter": build_id,
            "service_worker": False,
        },
    })

    update_generated_contracts(output_dir, manifest, report)
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
        f"Built {manifest['pokemon_count']} Pokémon from "
        f"{manifest['source_file']} into {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
