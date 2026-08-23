"""Version player/advanced lab assets before platform contract finalization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from . import build_collection, finalize_dashboard, platform_publish
except ImportError:
    import build_collection
    import finalize_dashboard
    import platform_publish


LAB_ASSETS = {
    "player_labs_styles": ("site/player-labs.css", "player-labs", "css"),
    "player_labs": ("site/player-labs.js", "player-labs", "js"),
    "advanced_labs_styles": ("site/advanced-labs.css", "advanced-labs", "css"),
    "advanced_labs": ("site/advanced-labs.js", "advanced-labs", "js"),
}

LAB_ASSET_PATTERNS = {
    "player_labs_styles": r"^assets/player-labs\.[0-9a-f]{12}\.css$",
    "player_labs": r"^assets/player-labs\.[0-9a-f]{12}\.js$",
    "advanced_labs_styles": r"^assets/advanced-labs\.[0-9a-f]{12}\.css$",
    "advanced_labs": r"^assets/advanced-labs\.[0-9a-f]{12}\.js$",
}


def _publish(source: Path, assets_dir: Path, output_name: str, kind: str) -> str:
    content = source.read_text(encoding="utf-8")
    if kind == "css":
        content = build_collection._minify_css(content)
    filename = f"{output_name}.{finalize_dashboard.content_hash(content)}.{kind}"
    target = assets_dir / filename
    target.write_text(content + ("\n" if kind == "css" else ""), encoding="utf-8", newline="\n")
    return f"assets/{filename}"


def _rewrite_html(output_dir: Path, replacements: dict[str, str]) -> None:
    for path in sorted(output_dir.glob("*.html")):
        source = path.read_text(encoding="utf-8")
        updated = source
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != source:
            path.write_text(updated, encoding="utf-8", newline="\n")


def prepare(repository_root: Path, output_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Hash lab assets, rewrite generated pages, and register them with platform contracts."""
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    published: dict[str, str] = {}
    replacements: dict[str, str] = {}

    for key, (source_path, output_name, kind) in LAB_ASSETS.items():
        source = repository_root / source_path
        if not source.is_file():
            raise ValueError(f"Missing lab asset source: {source_path}")
        published_path = _publish(source, assets_dir, output_name, kind)
        published[key] = published_path
        replacements[f"assets/{output_name}.{kind}"] = published_path

    _rewrite_html(output_dir, replacements)

    for old in replacements:
        stale = output_dir / old
        if stale.is_file():
            stale.unlink()

    manifest.setdefault("assets", {}).update(published)
    styles = manifest.setdefault("canonical_pipeline", {}).setdefault("style_sources", [])
    scripts = manifest.setdefault("canonical_pipeline", {}).setdefault("script_sources", [])
    for source_path, _, kind in LAB_ASSETS.values():
        target = styles if kind == "css" else scripts
        if source_path not in target:
            target.append(source_path)

    platform_publish.ASSET_PATTERNS.update(LAB_ASSET_PATTERNS)
    return manifest


__all__ = ["LAB_ASSETS", "LAB_ASSET_PATTERNS", "prepare"]
