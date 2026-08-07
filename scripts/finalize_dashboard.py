"""Finalize the canonical dashboard, companion pages, intelligence, and PWA resources."""

from __future__ import annotations

import hashlib
import json
import shutil
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
        json.dumps(payload, ensure_ascii=False, indent=None if compact else 2, separators=(",", ":") if compact else None) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def replace_once(source: str, old: str, new: str, description: str) -> str:
    if old not in source:
        raise ValueError(f"Generated HTML is missing the expected {description}")
    return source.replace(old, new, 1)


def publish_dashboard_assets(repository_root: Path, output_dir: Path, manifest: dict[str, Any]) -> dict[str, str]:
    site_dir = repository_root / "site"
    assets_dir = output_dir / "assets"

    def publish_css(source_name: str, output_name: str) -> str:
        content = build_collection._minify_css((site_dir / source_name).read_text(encoding="utf-8"))
        filename = f"{output_name}.{content_hash(content)}.css"
        (assets_dir / filename).write_text(content + "\n", encoding="utf-8", newline="\n")
        return f"assets/{filename}"

    def publish_js(source_name: str, output_name: str, replacements: tuple[tuple[str, str], ...] = ()) -> str:
        content = (site_dir / source_name).read_text(encoding="utf-8")
        for old, new in replacements:
            content = content.replace(old, new)
        filename = f"{output_name}.{content_hash(content)}.js"
        (assets_dir / filename).write_text(content, encoding="utf-8", newline="\n")
        return f"assets/{filename}"

    dashboard_css_path = publish_css("dashboard.css", "dashboard")
    companion_css_path = publish_css("companion.css", "companion")
    dashboard_js_path = publish_js(
        "dashboard.js",
        "dashboard",
        (( 'fetch("data/data-health.json")', f'fetch("data/data-health.json?v={manifest["build_id"]}")'),),
    )
    companion_js_path = publish_js(
        "companion.js",
        "companion",
        (( 'this.root.fetch("data/pokemon.json")', f'this.root.fetch("data/pokemon.json?v={manifest["build_id"]}")'),),
    )
    insights_js_path = publish_js(
        "insights.js",
        "insights",
        (( 'fetchFunction("data/insights.json")', f'fetchFunction("data/insights.json?v={manifest["build_id"]}")'),),
    )

    style_markup = (
        f'  <link rel="stylesheet" href="{dashboard_css_path}">\n'
        f'  <link rel="stylesheet" href="{companion_css_path}">\n'
        '  <link rel="manifest" href="manifest.webmanifest">\n'
        '  <meta name="theme-color" content="#111827">\n'
    )
    script_markup = (
        f'  <script defer src="{dashboard_js_path}"></script>\n'
        f'  <script defer src="{companion_js_path}"></script>\n'
    )
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
        f'<link rel="stylesheet" href="{manifest["assets"]["styles"]}">\n  <link rel="stylesheet" href="{dashboard_css_path}">\n  <link rel="stylesheet" href="{companion_css_path}">\n  <link rel="manifest" href="manifest.webmanifest">\n  <meta name="theme-color" content="#111827">',
        "Insights stylesheet reference",
    )
    insights_source = replace_once(insights_source, '<script defer src="assets/insights.js"></script>', f'<script defer src="{insights_js_path}"></script>\n  <script defer src="{companion_js_path}"></script>', "Insights script reference")
    (output_dir / "insights.html").write_text(insights_source, encoding="utf-8", newline="\n")

    return {
        "dashboard_styles": dashboard_css_path,
        "companion_styles": companion_css_path,
        "dashboard": dashboard_js_path,
        "companion": companion_js_path,
        "insights": insights_js_path,
    }


def publish_pwa(repository_root: Path, output_dir: Path, manifest: dict[str, Any]) -> None:
    site_dir = repository_root / "site"
    shutil.copyfile(site_dir / "manifest.webmanifest", output_dir / "manifest.webmanifest")
    shutil.copyfile(site_dir / "app-icon.svg", output_dir / "assets" / "app-icon.svg")
    precache = [
        "./",
        "index.html",
        "insights.html",
        "manifest.webmanifest",
        "assets/app-icon.svg",
        "data/pokemon.json",
        "data/collection-summary.json",
        "data/data-health.json",
        "data/insights.json",
    ]
    precache.extend(str(path) for path in manifest.get("assets", {}).values())
    precache = list(dict.fromkeys(precache))
    service_worker = (site_dir / "sw.js").read_text(encoding="utf-8")
    service_worker = service_worker.replace("__BUILD_ID__", str(manifest["build_id"]))
    service_worker = service_worker.replace("__PRECACHE__", json.dumps(precache, ensure_ascii=False))
    (output_dir / "sw.js").write_text(service_worker, encoding="utf-8", newline="\n")


def patch_manifest_schema(schema: dict[str, Any]) -> None:
    required = schema.setdefault("required", [])
    for key in ("canonical_pipeline", "data_health", "insights", "pwa"):
        if key not in required:
            required.append(key)
    properties = schema.setdefault("properties", {})
    properties["generator"] = {"type": "string", "const": CANONICAL_GENERATOR}

    assets = properties.setdefault("assets", {"type": "object"})
    asset_required = assets.setdefault("required", [])
    asset_properties = assets.setdefault("properties", {})
    patterns = {
        "dashboard_styles": "^assets/dashboard\\.[0-9a-f]{12}\\.css$",
        "companion_styles": "^assets/companion\\.[0-9a-f]{12}\\.css$",
        "dashboard": "^assets/dashboard\\.[0-9a-f]{12}\\.js$",
        "companion": "^assets/companion\\.[0-9a-f]{12}\\.js$",
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
            "html_templates": {"type": "array", "const": ["site/index.html", "site/insights.html"]},
            "style_sources": {"type": "array", "const": ["site/styles.css", "site/stability.css", "site/dashboard.css", "site/companion.css"]},
            "script_sources": {"type": "array", "const": ["site/app.js", "site/hardening.js", "site/accessibility.js", "site/dashboard.js", "site/companion.js", "site/insights.js"]},
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
    properties["pwa"] = {
        "type": "object",
        "required": ["manifest", "service_worker", "icon", "cache_strategy"],
        "properties": {
            "manifest": {"const": "manifest.webmanifest"},
            "service_worker": {"const": "sw.js"},
            "icon": {"const": "assets/app-icon.svg"},
            "cache_strategy": {"const": "versioned-network-first-data"},
        },
        "additionalProperties": False,
    }


def publish_intelligence(output_dir: Path, manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads((output_dir / "data" / "pokemon.json").read_text(encoding="utf-8"))
    summary = json.loads((output_dir / "data" / "collection-summary.json").read_text(encoding="utf-8"))
    records = payload["records"]
    health = build_data_health(records, manifest)
    insights = build_insights(records, summary, manifest, health)
    write_json(output_dir / "data" / "data-health.json", health)
    write_json(output_dir / "data" / "data-health.schema.json", data_health_schema())
    write_json(output_dir / "data" / "insights.json", insights)
    write_json(output_dir / "data" / "insights.schema.json", insights_schema())
    return health, insights


def finalize(repository_root: Path, output_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    new_assets = publish_dashboard_assets(repository_root, output_dir, manifest)
    manifest["assets"].update(new_assets)
    manifest["generator"] = CANONICAL_GENERATOR
    manifest["canonical_pipeline"] = {
        "command": CANONICAL_COMMAND,
        "html_templates": ["site/index.html", "site/insights.html"],
        "style_sources": ["site/styles.css", "site/stability.css", "site/dashboard.css", "site/companion.css"],
        "script_sources": ["site/app.js", "site/hardening.js", "site/accessibility.js", "site/dashboard.js", "site/companion.js", "site/insights.js"],
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
    manifest["pwa"] = {
        "manifest": "manifest.webmanifest",
        "service_worker": "sw.js",
        "icon": "assets/app-icon.svg",
        "cache_strategy": "versioned-network-first-data",
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
    publish_pwa(repository_root, output_dir, manifest)

    llms_path = output_dir / "llms.txt"
    llms = llms_path.read_text(encoding="utf-8")
    llms += (
        "\nCanonical dashboard and companion resources:\n"
        f"- Production command: {CANONICAL_COMMAND}\n"
        "- /insights.html for collection-wide summaries and drill-down links\n"
        "- /data/insights.json and /data/insights.schema.json\n"
        "- /data/data-health.json and /data/data-health.schema.json\n"
        "- Narrow viewports use mobile result cards with a full normalized-record detail dialog.\n"
        "- Saved views and comparison state are browser-local; saved views support JSON backup and restore.\n"
        "- GO Search translates only documented compatible filters and lists approximate or omitted conditions.\n"
        "- /manifest.webmanifest and /sw.js provide an installable, versioned offline experience.\n"
        "- Desktop column preferences remain browser-local and are not part of the collection payload.\n"
    )
    llms_path.write_text(llms, encoding="utf-8", newline="\n")
    return manifest
