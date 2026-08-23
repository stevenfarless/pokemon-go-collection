"""Publish browser-platform safety, design, localization, product, PWA lifecycle, and diagnostics resources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from . import build_collection, finalize_dashboard
except ImportError:
    import build_collection
    import finalize_dashboard

CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self'; worker-src 'self'; manifest-src 'self'; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-src 'none'"
)
THEME_BOOTSTRAP = (
    '<script data-theme-bootstrap>'
    'try{const v=localStorage.getItem("pokemon-go-collection:appearance:v1");'
    'if(v==="light"||v==="dark")document.documentElement.dataset.theme=v}catch{}'
    '</script>\n'
)
PLATFORM_STYLE_SOURCES = ["site/design-system.css", "site/platform.css", "site/product-experience.css"]
PLATFORM_SCRIPT_SOURCES = [
    "site/design-system.js",
    "site/i18n.js",
    "site/storage-health.js",
    "site/security.js",
    "site/pwa-lifecycle.js",
    "site/diagnostics.js",
    "site/product-experience.js",
]
ASSET_PATTERNS = {
    "design_system_styles": r"^assets/design-system\.[0-9a-f]{12}\.css$",
    "platform_styles": r"^assets/platform\.[0-9a-f]{12}\.css$",
    "product_experience_styles": r"^assets/product-experience\.[0-9a-f]{12}\.css$",
    "design_system": r"^assets/design-system\.[0-9a-f]{12}\.js$",
    "i18n": r"^assets/i18n\.[0-9a-f]{12}\.js$",
    "storage_health": r"^assets/storage-health\.[0-9a-f]{12}\.js$",
    "security": r"^assets/security\.[0-9a-f]{12}\.js$",
    "pwa_lifecycle": r"^assets/pwa-lifecycle\.[0-9a-f]{12}\.js$",
    "diagnostics": r"^assets/diagnostics\.[0-9a-f]{12}\.js$",
    "product_experience": r"^assets/product-experience\.[0-9a-f]{12}\.js$",
}


def _publish_css(source: Path, assets_dir: Path, output_name: str) -> str:
    content = build_collection._minify_css(source.read_text(encoding="utf-8"))
    filename = f"{output_name}.{finalize_dashboard.content_hash(content)}.css"
    (assets_dir / filename).write_text(content + "\n", encoding="utf-8", newline="\n")
    return f"assets/{filename}"


def _publish_js(source: Path, assets_dir: Path, output_name: str) -> str:
    content = source.read_text(encoding="utf-8")
    filename = f"{output_name}.{finalize_dashboard.content_hash(content)}.js"
    (assets_dir / filename).write_text(content, encoding="utf-8", newline="\n")
    return f"assets/{filename}"


def _patch_schema(schema: dict[str, Any], manifest: dict[str, Any]) -> None:
    properties = schema.setdefault("properties", {})
    assets = properties.setdefault("assets", {"type": "object"})
    required = assets.setdefault("required", [])
    asset_properties = assets.setdefault("properties", {})
    for key, pattern in ASSET_PATTERNS.items():
        if key not in required:
            required.append(key)
        asset_properties[key] = {"type": "string", "pattern": pattern}
    assets["additionalProperties"] = False

    canonical = properties.get("canonical_pipeline")
    if isinstance(canonical, dict):
        canonical_properties = canonical.setdefault("properties", {})
        canonical_properties["style_sources"] = {
            "type": "array",
            "const": manifest["canonical_pipeline"]["style_sources"],
        }
        canonical_properties["script_sources"] = {
            "type": "array",
            "const": manifest["canonical_pipeline"]["script_sources"],
        }


def _sync_contracts(output_dir: Path, manifest: dict[str, Any]) -> None:
    manifest_schema_path = output_dir / "data" / "build-manifest.schema.json"
    payload_schema_path = output_dir / "data" / "schema.json"
    manifest_schema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))
    payload_schema = json.loads(payload_schema_path.read_text(encoding="utf-8"))
    _patch_schema(manifest_schema, manifest)
    _patch_schema(payload_schema["$defs"]["manifest"], manifest)
    finalize_dashboard.write_json(manifest_schema_path, manifest_schema)
    finalize_dashboard.write_json(payload_schema_path, payload_schema)
    pokemon_path = output_dir / "data" / "pokemon.json"
    pokemon = json.loads(pokemon_path.read_text(encoding="utf-8"))
    pokemon["manifest"] = manifest
    finalize_dashboard.write_json(pokemon_path, pokemon, compact=True)
    finalize_dashboard.write_json(output_dir / "data" / "build-manifest.json", manifest)


def _markup(asset_paths: dict[str, str]) -> tuple[str, str]:
    styles = "".join(
        f'  <link rel="stylesheet" href="{asset_paths[key]}" data-platform-style="{key}">\n'
        for key in ("design_system_styles", "platform_styles", "product_experience_styles")
    )
    scripts = "".join(
        f'  <script defer src="{asset_paths[key]}" data-platform-script="{key}"></script>\n'
        for key in (
            "design_system",
            "i18n",
            "storage_health",
            "security",
            "pwa_lifecycle",
            "diagnostics",
            "product_experience",
        )
    )
    return styles, scripts


def _inject_platform(output_dir: Path, asset_paths: dict[str, str]) -> None:
    csp_markup = f'  <meta http-equiv="Content-Security-Policy" content="{CSP}">\n'
    style_markup, script_markup = _markup(asset_paths)
    for path in sorted(output_dir.glob("*.html")):
        source = path.read_text(encoding="utf-8")
        if "Content-Security-Policy" not in source:
            if "<head>" not in source:
                raise ValueError(f"{path.name} has no head element for CSP")
            source = source.replace("<head>", "<head>\n" + csp_markup + THEME_BOOTSTRAP, 1)
        elif "data-theme-bootstrap" not in source:
            source = source.replace("</head>", THEME_BOOTSTRAP + "</head>", 1)
        if "data-platform-style" not in source:
            source = source.replace("</head>", style_markup + "</head>", 1)
        if "data-platform-script" not in source:
            source = source.replace("</body>", script_markup + "</body>", 1)
        path.write_text(source, encoding="utf-8", newline="\n")


def _write_style_guide(output_dir: Path, asset_paths: dict[str, str]) -> None:
    style_markup, script_markup = _markup(asset_paths)
    html = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="{CSP}">
  {THEME_BOOTSTRAP.strip()}
  <title>Design system</title>
{style_markup}  <style>body{{margin:0;padding:1.25rem;background:var(--ds-bg);color:var(--ds-text);font-family:system-ui,sans-serif}}main{{width:min(64rem,100%);margin:auto;display:grid;gap:1rem}}.examples{{display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:.75rem}}</style>
</head>
<body>
<main>
  <header class="ds-card"><h1 data-i18n="styleGuide.title">Design system</h1><p data-i18n="styleGuide.description">Shared semantic tokens and interaction patterns.</p><p><a href="today.html">Today</a> · <a href="index.html">Collection</a> · <a href="reference.html">Reference</a> · <a href="insights.html">Insights</a> · <a href="tools.html">Tools</a></p></header>
  <section class="ds-card"><h2>Statuses and evidence</h2><div class="ds-toolbar"><span class="ds-status" data-state="success">Healthy</span><span class="ds-status" data-state="warning">Review</span><span class="ds-status" data-state="danger">Blocked</span><span class="ds-source-chip">Official · reviewed</span></div></section>
  <section class="examples"><article class="ds-card"><h2>Card</h2><p>Semantic surface, border, text and spacing tokens.</p></article><article class="ds-notice" data-kind="warning"><strong>Warning</strong><p>State is expressed with words and structure, not color alone.</p></article><div class="ds-empty">Useful empty state</div></section>
  <section class="ds-card"><h2>Segmented control</h2><div class="ds-segmented" role="group" aria-label="Example density"><button aria-pressed="true">Essential</button><button aria-pressed="false">Detailed</button><button aria-pressed="false">Expert</button></div></section>
  <section class="ds-card"><h2>Destructive confirmation</h2><button class="ds-danger-confirm" type="button">Review before irreversible action</button></section>
</main>
{script_markup}</body>
</html>
'''
    (output_dir / "style-guide.html").write_text(html, encoding="utf-8", newline="\n")


def _rewrite_service_worker(repository_root: Path, output_dir: Path, manifest: dict[str, Any]) -> None:
    precache = [
        "./",
        "index.html",
        "insights.html",
        "tools.html",
        "today.html",
        "reference.html",
        "style-guide.html",
        "manifest.webmanifest",
        "assets/app-icon.svg",
        "data/build-manifest.json",
        "data/collection-summary.json",
        "data/data-health.json",
        "data/insights.json",
        "data/external/index.json",
        "data/mechanics/index.json",
        "data/today.json",
        "data/reference/index.json",
        "data/global-search-index.json",
    ]
    precache.extend(
        str(value)
        for value in manifest.get("assets", {}).values()
        if str(value).startswith("assets/")
    )
    precache = list(dict.fromkeys(precache))
    source = (repository_root / "site" / "sw.js").read_text(encoding="utf-8")
    source = source.replace("__BUILD_ID__", str(manifest["build_id"]))
    source = source.replace("__PRECACHE__", json.dumps(precache, ensure_ascii=False))
    (output_dir / "sw.js").write_text(source, encoding="utf-8", newline="\n")


def publish_platform(repository_root: Path, output_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    site_dir = repository_root / "site"
    assets_dir = output_dir / "assets"
    assets = {
        "design_system_styles": _publish_css(site_dir / "design-system.css", assets_dir, "design-system"),
        "platform_styles": _publish_css(site_dir / "platform.css", assets_dir, "platform"),
        "product_experience_styles": _publish_css(site_dir / "product-experience.css", assets_dir, "product-experience"),
        "design_system": _publish_js(site_dir / "design-system.js", assets_dir, "design-system"),
        "i18n": _publish_js(site_dir / "i18n.js", assets_dir, "i18n"),
        "storage_health": _publish_js(site_dir / "storage-health.js", assets_dir, "storage-health"),
        "security": _publish_js(site_dir / "security.js", assets_dir, "security"),
        "pwa_lifecycle": _publish_js(site_dir / "pwa-lifecycle.js", assets_dir, "pwa-lifecycle"),
        "diagnostics": _publish_js(site_dir / "diagnostics.js", assets_dir, "diagnostics"),
        "product_experience": _publish_js(site_dir / "product-experience.js", assets_dir, "product-experience"),
    }
    manifest["assets"].update(assets)
    styles = manifest["canonical_pipeline"].setdefault("style_sources", [])
    for source in PLATFORM_STYLE_SOURCES:
        if source not in styles:
            styles.append(source)
    scripts = manifest["canonical_pipeline"].setdefault("script_sources", [])
    for source in PLATFORM_SCRIPT_SOURCES:
        if source not in scripts:
            scripts.append(source)

    _inject_platform(output_dir, assets)
    _write_style_guide(output_dir, assets)
    finalize_dashboard.write_json(
        output_dir / "data" / "security-policy.json",
        {
            "schema_version": 1,
            "content_security_policy": CSP,
            "hosting": "GitHub Pages meta CSP",
            "limitations": [
                "GitHub Pages does not provide repository-controlled response headers.",
                "The generated dashboard currently contains a small trusted inline connectivity probe, theme bootstrap, and inline critical/preload styles, so script/style unsafe-inline remains temporarily required.",
                "frame-ancestors is not enforced from a meta CSP and therefore is intentionally omitted.",
            ],
            "trusted_types": "evaluated-progressive-defense-not-enforced",
            "unsafe_url_schemes": "blocked by CollectionSecurity for DOM anchors",
        },
    )
    _sync_contracts(output_dir, manifest)
    _rewrite_service_worker(repository_root, output_dir, manifest)

    llms = output_dir / "llms.txt"
    llms.write_text(
        llms.read_text(encoding="utf-8")
        + (
            "\nBrowser platform safety and presentation:\n"
            "- /data/security-policy.json documents the Pages-compatible CSP and remaining inline-policy limitation.\n"
            "- Browser-local Storage Health validates seven durable namespaces, retains last-known-good snapshots, probes write capability, and never uploads local state.\n"
            "- PWA updates are staged and user-applied; reload is never forced while local edit areas are dirty.\n"
            "- Diagnostics expose build, resource, PWA, freshness, capabilities, and storage status without exporting collection records or note contents.\n"
            "- Semantic design tokens support system/light/dark appearance, forced colors, reduced motion, and shared component patterns.\n"
            "- Locale/timezone presentation uses stable message keys and Intl; canonical machine identifiers remain locale-neutral.\n"
            "- /today.html and /data/today.json prioritize shared decision-support, history, health, and fresh-current resources without duplicating their rules.\n"
            "- /reference.html and /data/reference/index.json join every supported species/form to the canonical versioned knowledge snapshot and exact owned record IDs.\n"
            "- /data/global-search-index.json powers deterministic cross-domain search; current results are allowed only while the referenced external snapshot remains fresh.\n"
            "- Essential, Detailed, and Expert are browser-local presentation levels only; critical warnings and underlying results do not change.\n"
        ),
        encoding="utf-8",
        newline="\n",
    )
    return manifest
