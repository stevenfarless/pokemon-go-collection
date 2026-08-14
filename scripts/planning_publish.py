"""Publish the client-side planning/search tools into the canonical static build."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from . import build_collection
    from . import finalize_dashboard
except ImportError:
    import build_collection
    import finalize_dashboard


PLANNING_HTML_TEMPLATES = ["site/index.html", "site/insights.html", "site/tools.html"]
PLANNING_STYLE_SOURCES = [
    "site/styles.css",
    "site/stability.css",
    "site/dashboard.css",
    "site/companion.css",
    "site/planning.css",
]
PLANNING_SCRIPT_SOURCES = [
    "site/app.js",
    "site/hardening.js",
    "site/accessibility.js",
    "site/dashboard.js",
    "site/advanced-search.js",
    "site/companion.js",
    "site/planning.js",
    "site/planning-extras.js",
    "site/insights.js",
]


def _publish_css(source: Path, assets_dir: Path, output_name: str) -> str:
    content = build_collection._minify_css(source.read_text(encoding="utf-8"))
    filename = f"{output_name}.{finalize_dashboard.content_hash(content)}.css"
    (assets_dir / filename).write_text(content + "\n", encoding="utf-8", newline="\n")
    return f"assets/{filename}"


def _publish_js(source: Path, assets_dir: Path, output_name: str, replacements: tuple[tuple[str, str], ...] = ()) -> str:
    content = source.read_text(encoding="utf-8")
    for old, new in replacements:
        content = content.replace(old, new)
    filename = f"{output_name}.{finalize_dashboard.content_hash(content)}.js"
    (assets_dir / filename).write_text(content, encoding="utf-8", newline="\n")
    return f"assets/{filename}"


def _patch_manifest_schema(schema: dict[str, Any]) -> None:
    properties = schema.setdefault("properties", {})
    assets = properties.setdefault("assets", {"type": "object"})
    required = assets.setdefault("required", [])
    asset_properties = assets.setdefault("properties", {})
    patterns = {
        "planning_styles": r"^assets/planning\.[0-9a-f]{12}\.css$",
        "advanced_search": r"^assets/advanced-search\.[0-9a-f]{12}\.js$",
        "planning": r"^assets/planning\.[0-9a-f]{12}\.js$",
        "planning_extras": r"^assets/planning-extras\.[0-9a-f]{12}\.js$",
    }
    for key, pattern in patterns.items():
        if key not in required:
            required.append(key)
        asset_properties[key] = {"type": "string", "pattern": pattern}
    assets["additionalProperties"] = False

    canonical = properties.get("canonical_pipeline")
    if isinstance(canonical, dict):
        canonical_properties = canonical.setdefault("properties", {})
        canonical_properties["html_templates"] = {"type": "array", "const": PLANNING_HTML_TEMPLATES}
        canonical_properties["style_sources"] = {"type": "array", "const": PLANNING_STYLE_SOURCES}
        canonical_properties["script_sources"] = {"type": "array", "const": PLANNING_SCRIPT_SOURCES}


def _write_manifest_contracts(output_dir: Path, manifest: dict[str, Any]) -> None:
    manifest_schema_path = output_dir / "data" / "build-manifest.schema.json"
    payload_schema_path = output_dir / "data" / "schema.json"
    manifest_schema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))
    payload_schema = json.loads(payload_schema_path.read_text(encoding="utf-8"))
    _patch_manifest_schema(manifest_schema)
    _patch_manifest_schema(payload_schema["$defs"]["manifest"])
    finalize_dashboard.write_json(manifest_schema_path, manifest_schema)
    finalize_dashboard.write_json(payload_schema_path, payload_schema)

    pokemon_path = output_dir / "data" / "pokemon.json"
    pokemon = json.loads(pokemon_path.read_text(encoding="utf-8"))
    pokemon["manifest"] = manifest
    finalize_dashboard.write_json(pokemon_path, pokemon, compact=True)
    finalize_dashboard.write_json(output_dir / "data" / "build-manifest.json", manifest)


def publish_planning(repository_root: Path, output_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Add #72/#74/#75/#76/#77 static assets, page, manifest metadata, and PWA coverage."""
    site_dir = repository_root / "site"
    assets_dir = output_dir / "assets"
    build_id = str(manifest["build_id"])

    planning_css = _publish_css(site_dir / "planning.css", assets_dir, "planning")
    advanced_search = _publish_js(
        site_dir / "advanced-search.js",
        assets_dir,
        "advanced-search",
        ((
            'root.fetch("data/knowledge/species-index.json")',
            f'root.fetch("data/knowledge/species-index.json?v={build_id}")',
        ),),
    )
    planning_js = _publish_js(
        site_dir / "planning.js",
        assets_dir,
        "planning",
        (
            ('fetchJson(root, "data/pokemon.json")', f'fetchJson(root, "data/pokemon.json?v={build_id}")'),
            ('fetchJson(root, "data/investments/records.json")', f'fetchJson(root, "data/investments/records.json?v={build_id}")'),
            ('fetchJson(root, "data/candidates/index.json")', f'fetchJson(root, "data/candidates/index.json?v={build_id}")'),
            ('fetchJson(root, "data/knowledge/pokemon-go.json")', f'fetchJson(root, "data/knowledge/pokemon-go.json?v={build_id}")'),
            ('fetchJson(root, "data/external/index.json")', f'fetchJson(root, "data/external/index.json?v={build_id}")'),
            ('fetchJson(root, "data/history-index.json")', f'fetchJson(root, "data/history-index.json?v={build_id}")'),
        ),
    )
    planning_extras = _publish_js(
        site_dir / "planning-extras.js",
        assets_dir,
        "planning-extras",
        (
            ('fetchJson(root, "data/pokemon.json")', f'fetchJson(root, "data/pokemon.json?v={build_id}")'),
            ('fetchJson(root, "data/investments/records.json")', f'fetchJson(root, "data/investments/records.json?v={build_id}")'),
            ('fetchJson(root, "data/candidates/index.json")', f'fetchJson(root, "data/candidates/index.json?v={build_id}")'),
            ('fetchJson(root, "data/knowledge/pokemon-go.json")', f'fetchJson(root, "data/knowledge/pokemon-go.json?v={build_id}")'),
        ),
    )

    manifest["assets"]["planning_styles"] = planning_css
    manifest["assets"]["advanced_search"] = advanced_search
    manifest["assets"]["planning"] = planning_js
    manifest["assets"]["planning_extras"] = planning_extras
    manifest["canonical_pipeline"]["html_templates"] = PLANNING_HTML_TEMPLATES
    manifest["canonical_pipeline"]["style_sources"] = PLANNING_STYLE_SOURCES
    manifest["canonical_pipeline"]["script_sources"] = PLANNING_SCRIPT_SOURCES

    companion_script = manifest["assets"]["companion"]
    for filename in ("index.html", "404.html"):
        path = output_dir / filename
        source = path.read_text(encoding="utf-8")
        source = finalize_dashboard.replace_once(
            source,
            f'  <script defer src="{companion_script}"></script>',
            f'  <script defer src="{advanced_search}"></script>\n  <script defer src="{companion_script}"></script>',
            "companion script for advanced-search insertion",
        )
        if '<a href="tools.html">Tools</a>' not in source:
            source = finalize_dashboard.replace_once(
                source,
                '<a href="insights.html">Insights</a>',
                '<a href="insights.html">Insights</a>\n          <a href="tools.html">Tools</a>',
                "Insights navigation link",
            )
        path.write_text(source, encoding="utf-8", newline="\n")

    tools = (site_dir / "tools.html").read_text(encoding="utf-8")
    tools = finalize_dashboard.replace_once(
        tools,
        '<link rel="stylesheet" href="assets/styles.css">',
        f'<link rel="stylesheet" href="{manifest["assets"]["styles"]}">',
        "planning base stylesheet",
    )
    tools = finalize_dashboard.replace_once(
        tools,
        '<link rel="stylesheet" href="assets/planning.css">',
        f'<link rel="stylesheet" href="{planning_css}">',
        "planning stylesheet",
    )
    tools = finalize_dashboard.replace_once(
        tools,
        '<script defer src="assets/planning.js"></script>',
        f'<script defer src="{planning_js}"></script>\n  <script defer src="{planning_extras}"></script>',
        "planning scripts",
    )
    (output_dir / "tools.html").write_text(tools, encoding="utf-8", newline="\n")

    _write_manifest_contracts(output_dir, manifest)
    # finalize() already created the PWA; regenerate it so tools.html and the new assets
    # are included in the versioned offline cache without introducing a second SW model.
    finalize_dashboard.publish_pwa(repository_root, output_dir, manifest)

    llms_path = output_dir / "llms.txt"
    llms = llms_path.read_text(encoding="utf-8")
    llms += (
        "\nPlanning and advanced-search resources:\n"
        "- /tools.html provides owned-only team building, deterministic investment scenarios, browser-local goals, and safety-first trade review.\n"
        "- Advanced collection search extends the existing field grammar with local typo tolerance and inspectable natural-language shortcuts.\n"
        "- Type/family/Mega search uses /data/knowledge/species-index.json; no competing handwritten species database is embedded in the search engine.\n"
        "- Team and planning tools consume /data/candidates/, /data/investments/, /data/reasoning/, history, and external freshness contracts rather than recomputing hidden collection semantics.\n"
        "- Current meta/boss/event claims remain blocked when /data/external/index.json is stale or unavailable.\n"
        "- Team warnings expose missing second moves and current legacy/recommended-move uncertainty; owned alternatives retain exact record IDs.\n"
        "- What-if scenarios can be accumulated side by side, including Shadow/Purified cost-only comparisons that never recommend purification.\n"
        "- Goals and user-entered resource budgets are browser-local and are not collection facts; per-goal exclusions are stored separately and applied to drill-down views.\n"
    )
    llms_path.write_text(llms, encoding="utf-8", newline="\n")
    return manifest
