"""Integrate the #151 Event Calendar with existing generated product surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _patch_search(output_dir: Path) -> None:
    path = output_dir / "data" / "global-search-index.json"
    if not path.is_file():
        return
    payload = _load(path)
    items = list(payload.get("items") or [])
    if not any(item.get("id") == "action:event-calendar" for item in items):
        items.append(
            {
                "id": "action:event-calendar",
                "domain": "action",
                "title": "Event Calendar",
                "subtitle": "Collection-aware Pokémon GO deadlines and preparation windows",
                "route": "event-calendar.html",
                "terms": ["events", "deadlines", "calendar", "event prep", "community day", "raid hour", "spotlight hour"],
            }
        )
        payload["items"] = items
        payload["item_count"] = len(items)
        counts: dict[str, int] = {}
        for item in items:
            domain = str(item.get("domain") or "unknown")
            counts[domain] = counts.get(domain, 0) + 1
        payload["domain_counts"] = dict(sorted(counts.items()))
        _write(path, payload)


def _patch_today(output_dir: Path) -> None:
    path = output_dir / "data" / "today.json"
    if not path.is_file():
        return
    payload = _load(path)
    changed = False
    for card in [*(payload.get("top_actions") or []), *((payload.get("sections") or {}).get("event_prep", {}).get("cards") or [])]:
        if card.get("kind") == "current" and str(card.get("id") or "").startswith("current:events:"):
            if card.get("route") != "event-calendar.html":
                card["route"] = "event-calendar.html"
                changed = True
    event_section = (payload.get("sections") or {}).get("event_prep")
    if isinstance(event_section, dict):
        desired = "Open Event Calendar for fresh collection-aware event windows. If event data is stale, the calendar retains it only as history."
        if event_section.get("calendar_handoff") != desired:
            event_section["calendar_handoff"] = desired
            changed = True
    if changed:
        _write(path, payload)


def _patch_nav(output_dir: Path) -> None:
    for filename in ("today.html", "reference.html"):
        path = output_dir / filename
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        if 'href="event-calendar.html"' in source:
            continue
        marker = '<a href="today.html">Today</a>'
        if marker in source:
            source = source.replace(marker, marker + '\n      <a href="event-calendar.html">Events</a>', 1)
            path.write_text(source, encoding="utf-8", newline="\n")


def _inject_backup_bridge(output_dir: Path) -> None:
    path = output_dir / "tools.html"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    if "data-event-calendar-backup" in source:
        return
    marker = "</body>"
    if marker not in source:
        raise ValueError("Generated Tools page is missing its body closing tag")
    source = source.replace(marker, '  <script defer src="assets/event-calendar-backup.js" data-event-calendar-backup></script>\n</body>', 1)
    path.write_text(source, encoding="utf-8", newline="\n")


def integrate(output_dir: Path) -> None:
    """Patch already-generated Today/Search/navigation with the new calendar handoff."""
    _patch_search(output_dir)
    _patch_today(output_dir)
    _patch_nav(output_dir)
    _inject_backup_bridge(output_dir)


def finalize_service_worker(output_dir: Path) -> None:
    """Add the Event Calendar to the final versioned service-worker precache."""
    path = output_dir / "sw.js"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    additions = []
    if '"event-calendar.html"' not in source:
        additions.append('"event-calendar.html"')
    if '"data/event-calendar.json"' not in source:
        additions.append('"data/event-calendar.json"')
    if not additions:
        return
    marker = '"today.html",'
    if marker not in source:
        raise ValueError("Final service worker is missing the Today precache entry")
    source = source.replace(marker, marker + " " + ", ".join(additions) + ",", 1)
    path.write_text(source, encoding="utf-8", newline="\n")


__all__ = ["integrate", "finalize_service_worker"]
