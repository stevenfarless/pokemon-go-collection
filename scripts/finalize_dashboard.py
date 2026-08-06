"""Finalize the canonical dashboard, companion page, and intelligence resources."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from . import build_collection
    from .collection_intelligence import (
        DATA_HEALTH_SCHEMA_VERSION,
        INSIGHTS_SCHEMA_VERSION,
        build_data_health,
        build_insights,
        data_health_schema,
        insights_schema,
    )
except ImportError:
    import build_collection
    from collection_intelligence import (
        DATA_HEALTH_SCHEMA_VERSION,
        INSIGHTS_SCHEMA_VERSION,
        build_data_health,
        build_insights,
        data_health_schema,
        insights_schema,
    )

CANONICAL_COMMAND = "python scripts/build_dashboard.py"
CANONICAL_GENERATOR = "scripts/build_dashboard.py"


def write_json(path: Path, payload: Any, *, compact: bool = False) -> None:
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


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def replace_once(source: str, old: str, new: str, description: str) -> str:
    if old not in source:
        raise ValueError(f"Generated HTML is missing the expected {description}")
    return source.replace(old, new, 1)


def publish_dashboard_assets(
    repository_root: Path,
    output_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, str]:
    site_dir = repository_root / "site"
    assets_dir = output_dir / "assets"

    dashboard_css = build_collection._minify_css(
        (site_dir / "dashboard.css").read_text(encoding="utf-8")
    )
    dashboard_css_name = f"dashboard.{content_hash(dashboard_css)}.css"
    dashboard_css_path = f"assets/{dashboard_css_name}"
    (assets_dir / dashboard_css_name).write_text(
        dashboard_css + "\n", encoding="utf-8", newline="\n"
    )

    dashboard_js = (site_dir / "dashboard.js").read_text(encoding="utf-8")
    dashboard_js = dashboard_js.replace(
        'fetch("data/data-health.json")',
        f'fetch("data/data-health.json?v={manifest["build_id"]}")',
    )
    dashboard_js_name = f"dashboard.{content_hash(dashboard_js)}.js"
    dashboard_js_path = f"assets/{dashboard_js_name}"
    (assets_dir / dashboard_js_name).write_text(
        dashboard_js, encoding="utf-8", newline="\n"
    )

    insights_js = (site_dir / "insights.js").read_text(encoding="utf-8")
    insights_js = insights_js.replace(
        'fetchFunction("data/insights.json")',
        f'fetchFunction("data/insights.json?v={manifest["build_id"]}")',
    )
    insights_js_name = f"insights.{content_hash(insights_js)}.js"
    insights_js_path = f"assets/{insights_js_name}"
    (assets_dir / insights_js_name).write_text(
        insights_js, encoding="utf-8", newline="\n"
    )

    style_markup = f'  <link rel="stylesheet" href="{dashboard_css_path}">\n'
    script_markup = f'  <script defer src="{dashboard_js_path}"></script>\n'
    for filename in ("index.html", "404.html"):
        path = output_dir / filename
        source = path.read_text(encoding="utf-8")
        source = replace_once(source, "</head>", style_markup + "</head>", "head closing tag")
        source = replace_once(source, "</body>", script_markup + "</body>", "body closing tag")
        path.write_text(source, encoding="utf-8", newline="\n")

    insights_source = (site_dir / "insights.html").read_text(encoding="utf-8")
    insights_source = replace_once(
        insights_source,
        '<link rel="stylesheet" href="assets/styles.css">',
        (
            f'<link rel="stylesheet" href="{manifest["assets"]["styles"]}">\n'
            f'  <link rel="stylesheet" href="{dashboard_css_path}">'
        ),
        "Insights stylesheet reference",
    )
    insights_source = replace_once(
        insights_source,
        '<script defer src="assets/insights.js"></script>',
        f'<script defer src="{insights_js_path}"></script>',
        "Insights script reference",
    )
    (output_dir / "insights.html").write_text(
        insights_source, encoding="utf-8", newline="\n"
    )

    return {
        "dashboard_styles": dashboard_css_path,
        "dashboard": dashboard_js_path,
        "insights": insights_js_path,
    }


def patch_manifest_schema(schema: dict[str, Any]) -> None:
    required = schema.setdefault("required", [])
    for key in ("canonical_pipeline", "data_health", "insights"):
        if key not in required:
            required.append(key)
    properties = schema.setdefault("properties", {})
    properties["generator"] = {"type": "string", "const": CANONICAL_GENERATOR}

    assets = properties.setdefault("assets", {"type": "object"})
    asset_required = assets.setdefault("required", [])
    asset_properties = assets.setdefault("properties", {})
    patterns = {
        "dashboard_styles": "^assets/dashboard\\.[0-9a-f]{12}\\.css$",
        "dashboard": "^assets/dashboard\\.[0-9a-f]{12}\\.js$",
        "insights": "^assets/insights\\.[0-9a-f]{12}\\.js$",
    }
    for key, pattern in patterns.items():
        if key not in asset_required:
            asset_required.append(key)
        asset_properties[key] = {"type": "string", "pattern": pattern}
    assets["additionalProperties"] = False

    properties["canonical_pipeline"] = {
        "type": "object",
        "required": ["command", "html_templates", "style_sources", "script_sources"],
        "properties": {
            "command": {"const": CANONICAL_COMMAND},
            "html_templates": {
                "type": "array",
                "const": ["site/index.html", "site/insights.html"],
            },
            "style_sources": {
                "type": "array",
                "const": ["site/styles.css", "site/stability.css", "site/dashboard.css"],
            },
            "script_sources": {
                "type": "array",
                "const": [
                    "site/app.js", "site/hardening.js", "site/accessibility.js",
                    "site/dashboard.js", "site/insights.js",
                ],
            },
        },
        "additionalProperties": False,
    }
    properties["data_health"] = {
        "type": "object",
        "required": ["schema_version", "data", "schema", "stale_scan_days", "recent_catch_days"],
        "properties": {
            "schema_version": {"const": DATA_HEALTH_SCHEMA_VERSION},
            "data": {"const": "data/data-health.json"},
            "schema": {"const": "data/data-health.schema.json"},
            "stale_scan_days": {"type": "integer", "minimum": 1},
            "recent_catch_days": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    }
    properties["insights"] = {
        "type": "object",
        "required": ["schema_version", "page", "data", "schema"],
        "properties": {
            "schema_version": {"const": INSIGHTS_SCHEMA_VERSION},
            "page": {"const": "insights.html"},
            "data": {"const": "data/insights.json"},
            "schema": {"const": "data/insights.schema.json"},
        },
        "additionalProperties": False,
    }


def publish_intelligence(
    output_dir: Path,
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload_path = output_dir / "data" / "pokemon.json"
    summary_path = output_dir / "data" / "collection-summary.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    records = payload["records"]

    health = build_data_health(records, manifest)
    insights = build_insights(records, summary, manifest, health)
    write_json(output_dir / "data" / "data-health.json", health)
    write_json(output_dir / "data" / "data-health.schema.json", data_health_schema())
    write_json(output_dir / "data" / "insights.json", insights)
    write_json(output_dir / "data" / "insights.schema.json", insights_schema())
    return health, insights


def finalize(
    repository_root: Path,
    output_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    new_assets = publish_dashboard_assets(repository_root, output_dir, manifest)
    manifest["assets"].update(new_assets)
    manifest["generator"] = CANONICAL_GENERATOR
    manifest["canonical_pipeline"] = {
        "command": CANONICAL_COMMAND,
        "html_templates": ["site/index.html", "site/insights.html"],
        "style_sources": ["site/styles.css", "site/stability.css", "site/dashboard.css"],
        "script_sources": [
            "site/app.js", "site/hardening.js", "site/accessibility.js",
            "site/dashboard.js", "site/insights.js",
        ],
    }

    health, _ = publish_intelligence(output_dir, manifest)
    manifest["data_health"] = {
        "schema_version": DATA_HEALTH_SCHEMA_VERSION,
        "data": "data/data-health.json",
        "schema": "data/data-health.schema.json",
        "stale_scan_days": health["thresholds"]["stale_scan_days"],
        "recent_catch_days": health["thresholds"]["recent_catch_days"],
    }
    manifest["insights"] = {
        "schema_version": INSIGHTS_SCHEMA_VERSION,
        "page": "insights.html",
        "data": "data/insights.json",
        "schema": "data/insights.schema.json",
    }

    manifest_schema_path = output_dir / "data" / "build-manifest.schema.json"
    payload_schema_path = output_dir / "data" / "schema.json"
    manifest_schema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))
    patch_manifest_schema(manifest_schema)
    write_json(manifest_schema_path, manifest_schema)
    payload_schema = json.loads(payload_schema_path.read_text(encoding="utf-8"))
    patch_manifest_schema(payload_schema["$defs"]["manifest"])
    write_json(payload_schema_path, payload_schema)

    payload_path = output_dir / "data" / "pokemon.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["manifest"] = manifest
    write_json(payload_path, payload, compact=True)
    write_json(output_dir / "data" / "build-manifest.json", manifest)

    llms_path = output_dir / "llms.txt"
    llms = llms_path.read_text(encoding="utf-8")
    llms += (
        "\nCanonical dashboard and intelligence resources:\n"
        f"- Production command: {CANONICAL_COMMAND}\n"
        "- /insights.html for collection-wide summaries and drill-down links\n"
        "- /data/insights.json and /data/insights.schema.json\n"
        "- /data/data-health.json and /data/data-health.schema.json\n"
        "- Search supports optional field qualifiers documented in the dashboard Help popover.\n"
        "- Desktop column preferences remain browser-local and are not part of the collection payload.\n"
    )
    llms_path.write_text(llms, encoding="utf-8", newline="\n")
    return manifest
