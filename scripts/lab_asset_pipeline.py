"""Version product lab assets before platform contract finalization."""

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
    "battle_labs_styles": ("site/battle-labs.css", "battle-labs", "css"),
    "battle_labs": ("site/battle-labs.js", "battle-labs", "js"),
    "opportunity_special_labs_styles": ("site/opportunity-special-labs.css", "opportunity-special-labs", "css"),
    "opportunity_special_labs": ("site/opportunity-special-labs.js", "opportunity-special-labs", "js"),
    "trade_resource_labs_styles": ("site/trade-resource-labs.css", "trade-resource-labs", "css"),
    "trade_resource_labs": ("site/trade-resource-labs.js", "trade-resource-labs", "js"),
    "trade_matcher_filters": ("site/trade-matcher-filters.js", "trade-matcher-filters", "js"),
    "item_bag_planner": ("site/item-bag-planner.js", "item-bag-planner", "js"),
    "share_packets": ("site/share-packets.js", "share-packets", "js"),
    "storage_search_labs_styles": ("site/storage-search-labs.css", "storage-search-labs", "css"),
    "storage_search_labs": ("site/storage-search-labs.js", "storage-search-labs", "js"),
    "storage_search_backup": ("site/storage-search-backup.js", "storage-search-backup", "js"),
    "event_calendar_styles": ("site/event-calendar.css", "event-calendar", "css"),
    "event_calendar": ("site/event-calendar.js", "event-calendar", "js"),
    "event_calendar_backup": ("site/event-calendar-backup.js", "event-calendar-backup", "js"),
    "glossary_experience": ("site/glossary-experience.js", "glossary-experience", "js"),
}

LAB_ASSET_PATTERNS = {
    "player_labs_styles": r"^assets/player-labs\.[0-9a-f]{12}\.css$",
    "player_labs": r"^assets/player-labs\.[0-9a-f]{12}\.js$",
    "advanced_labs_styles": r"^assets/advanced-labs\.[0-9a-f]{12}\.css$",
    "advanced_labs": r"^assets/advanced-labs\.[0-9a-f]{12}\.js$",
    "battle_labs_styles": r"^assets/battle-labs\.[0-9a-f]{12}\.css$",
    "battle_labs": r"^assets/battle-labs\.[0-9a-f]{12}\.js$",
    "opportunity_special_labs_styles": r"^assets/opportunity-special-labs\.[0-9a-f]{12}\.css$",
    "opportunity_special_labs": r"^assets/opportunity-special-labs\.[0-9a-f]{12}\.js$",
    "trade_resource_labs_styles": r"^assets/trade-resource-labs\.[0-9a-f]{12}\.css$",
    "trade_resource_labs": r"^assets/trade-resource-labs\.[0-9a-f]{12}\.js$",
    "trade_matcher_filters": r"^assets/trade-matcher-filters\.[0-9a-f]{12}\.js$",
    "item_bag_planner": r"^assets/item-bag-planner\.[0-9a-f]{12}\.js$",
    "share_packets": r"^assets/share-packets\.[0-9a-f]{12}\.js$",
    "storage_search_labs_styles": r"^assets/storage-search-labs\.[0-9a-f]{12}\.css$",
    "storage_search_labs": r"^assets/storage-search-labs\.[0-9a-f]{12}\.js$",
    "storage_search_backup": r"^assets/storage-search-backup\.[0-9a-f]{12}\.js$",
    "event_calendar_styles": r"^assets/event-calendar\.[0-9a-f]{12}\.css$",
    "event_calendar": r"^assets/event-calendar\.[0-9a-f]{12}\.js$",
    "event_calendar_backup": r"^assets/event-calendar-backup\.[0-9a-f]{12}\.js$",
    "glossary_experience": r"^assets/glossary-experience\.[0-9a-f]{12}\.js$",
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
    glossary_markup = '  <script defer src="assets/glossary-experience.js" data-glossary-experience></script>\n'
    share_markup = '  <script defer src="assets/share-packets.js" data-share-packets></script>\n'
    for path in sorted(output_dir.glob("*.html")):
        source = path.read_text(encoding="utf-8")
        updated = source
        if "data-glossary-experience" not in updated:
            if "</body>" not in updated:
                raise ValueError(f"{path.name} is missing the closing body tag required by the glossary experience")
            updated = updated.replace("</body>", glossary_markup + "</body>", 1)
        if "data-share-packets" not in updated:
            if "</body>" not in updated:
                raise ValueError(f"{path.name} is missing the closing body tag required by Share Packets")
            updated = updated.replace("</body>", share_markup + "</body>", 1)
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
