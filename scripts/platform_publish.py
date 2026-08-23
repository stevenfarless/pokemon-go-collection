"""Publish browser-platform safety, PWA lifecycle, and diagnostics resources."""

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
PLATFORM_STYLE_SOURCE = "site/platform.css"
PLATFORM_SCRIPT_SOURCES = [
    "site/storage-health.js",
    "site/security.js",
    "site/pwa-lifecycle.js",
    "site/diagnostics.js",
]
ASSET_PATTERNS = {
    "platform_styles": r"^assets/platform\.[0-9a-f]{12}\.css$",
    "storage_health": r"^assets/storage-health\.[0-9a-f]{12}\.js$",
    "security": r"^assets/security\.[0-9a-f]{12}\.js$",
    "pwa_lifecycle": r"^assets/pwa-lifecycle\.[0-9a-f]{12}\.js$",
    "diagnostics": r"^assets/diagnostics\.[0-9a-f]{12}\.js$",
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
        canonical_properties["style_sources"] = {"type": "array", "const": manifest["canonical_pipeline"]["style_sources"]}
        canonical_properties["script_sources"] = {"type": "array", "const": manifest["canonical_pipeline"]["script_sources"]}


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


def _inject_platform(output_dir: Path, asset_paths: dict[str, str]) -> None:
    csp_markup = f'  <meta http-equiv="Content-Security-Policy" content="{CSP}">\n'
    style_markup = f'  <link rel="stylesheet" href="{asset_paths["platform_styles"]}" data-platform-style>\n'
    script_markup = "".join(
        f'  <script defer src="{asset_paths[key]}" data-platform-script="{key}"></script>\n'
        for key in ("storage_health", "security", "pwa_lifecycle", "diagnostics")
    )
    for path in sorted(output_dir.glob("*.html")):
        source = path.read_text(encoding="utf-8")
        if "Content-Security-Policy" not in source:
            if "<head>" not in source:
                raise ValueError(f"{path.name} has no head element for CSP")
            source = source.replace("<head>", "<head>\n" + csp_markup, 1)
        if "data-platform-style" not in source:
            source = source.replace("</head>", style_markup + "</head>", 1)
        if "data-platform-script" not in source:
            source = source.replace("</body>", script_markup + "</body>", 1)
        path.write_text(source, encoding="utf-8", newline="\n")


def _rewrite_service_worker(repository_root: Path, output_dir: Path, manifest: dict[str, Any]) -> None:
    precache = [
        "./", "index.html", "insights.html", "tools.html", "manifest.webmanifest", "assets/app-icon.svg",
        "data/build-manifest.json", "data/collection-summary.json", "data/data-health.json", "data/insights.json",
    ]
    precache.extend(str(value) for value in manifest.get("assets", {}).values() if str(value).startswith("assets/"))
    precache = list(dict.fromkeys(precache))
    source = (repository_root / "site" / "sw.js").read_text(encoding="utf-8")
    source = source.replace("__BUILD_ID__", str(manifest["build_id"]))
    source = source.replace("__PRECACHE__", json.dumps(precache, ensure_ascii=False))
    (output_dir / "sw.js").write_text(source, encoding="utf-8", newline="\n")


def publish_platform(repository_root: Path, output_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    site_dir = repository_root / "site"
    assets_dir = output_dir / "assets"
    assets = {
        "platform_styles": _publish_css(site_dir / "platform.css", assets_dir, "platform"),
        "storage_health": _publish_js(site_dir / "storage-health.js", assets_dir, "storage-health"),
        "security": _publish_js(site_dir / "security.js", assets_dir, "security"),
        "pwa_lifecycle": _publish_js(site_dir / "pwa-lifecycle.js", assets_dir, "pwa-lifecycle"),
        "diagnostics": _publish_js(site_dir / "diagnostics.js", assets_dir, "diagnostics"),
    }
    manifest["assets"].update(assets)
    styles = manifest["canonical_pipeline"].setdefault("style_sources", [])
    if PLATFORM_STYLE_SOURCE not in styles:
        styles.append(PLATFORM_STYLE_SOURCE)
    scripts = manifest["canonical_pipeline"].setdefault("script_sources", [])
    for source in PLATFORM_SCRIPT_SOURCES:
        if source not in scripts:
            scripts.append(source)

    _inject_platform(output_dir, assets)
    finalize_dashboard.write_json(output_dir / "data" / "security-policy.json", {
        "schema_version": 1,
        "content_security_policy": CSP,
        "hosting": "GitHub Pages meta CSP",
        "limitations": [
            "GitHub Pages does not provide repository-controlled response headers.",
            "The generated dashboard currently contains a small trusted inline connectivity probe and inline critical/preload styles, so script/style unsafe-inline remains temporarily required.",
            "frame-ancestors is not enforced from a meta CSP and therefore is intentionally omitted.",
        ],
        "trusted_types": "evaluated-progressive-defense-not-enforced",
        "unsafe_url_schemes": "blocked by CollectionSecurity for DOM anchors",
    })
    _sync_contracts(output_dir, manifest)
    _rewrite_service_worker(repository_root, output_dir, manifest)

    llms = output_dir / "llms.txt"
    llms.write_text(llms.read_text(encoding="utf-8") + (
        "\nBrowser platform safety:\n"
        "- /data/security-policy.json documents the Pages-compatible CSP and remaining inline-policy limitation.\n"
        "- Browser-local Storage Health validates seven durable namespaces, retains last-known-good snapshots, probes write capability, and never uploads local state.\n"
        "- PWA updates are staged and user-applied; reload is never forced while local edit areas are dirty.\n"
        "- Diagnostics expose build, resource, PWA, freshness, capabilities, and storage status without exporting collection records or note contents.\n"
    ), encoding="utf-8", newline="\n")
    return manifest
