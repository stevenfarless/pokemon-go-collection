"""Core implementation for the collection-aware Event Calendar (#151)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator

try:
    from . import manifest_registry
except ImportError:
    import manifest_registry

CALENDAR_VERSION = "1.0.0"
LOCAL_STATE_VERSION = 1
BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"


def _load(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_of(manifest: Mapping[str, Any]) -> datetime:
    for key in ("generated_at_utc", "generated_at", "export_timestamp"):
        parsed = _time(manifest.get(key))
        if parsed:
            return parsed
    return datetime.now(timezone.utc)


def _normal(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _ints(value: Any) -> list[int]:
    result: list[int] = []
    for item in value if isinstance(value, list) else [value]:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if number > 0 and number not in result:
            result.append(number)
    return result


def _record_id(record: Mapping[str, Any]) -> str:
    return str((record.get("identity") or {}).get("record_id") or record.get("record_id") or "")


def _pvp(record: Mapping[str, Any]) -> float:
    values = [
        float(value)
        for league in ("great", "ultra", "little")
        if isinstance((value := ((record.get("pvp") or {}).get(league) or {}).get("rank_percent")), (int, float))
    ]
    return max(values) if values else 0.0


def _summary(record: Mapping[str, Any]) -> dict[str, Any]:
    record_id = _record_id(record)
    return {
        "record_id": record_id,
        "dex": record.get("pokemon_number"),
        "name": record.get("name"),
        "form": record.get("form"),
        "cp": record.get("cp"),
        "iv_percent": (record.get("ivs") or {}).get("average_percent"),
        "pvp_best_rank_percent": _pvp(record) or None,
        "shadow_purified": (record.get("status") or {}).get("shadow_purified"),
        "route": f"index.html?record={record_id}" if record_id else "index.html",
    }


def _owned_maps(records: Iterable[Mapping[str, Any]]) -> tuple[dict[int, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]]:
    by_dex: dict[int, list[dict[str, Any]]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for raw in records:
        record = dict(raw)
        try:
            dex = int(record.get("pokemon_number") or 0)
        except (TypeError, ValueError):
            dex = 0
        if dex:
            by_dex.setdefault(dex, []).append(record)
        name = _normal(record.get("name"))
        if name:
            by_name.setdefault(name, []).append(record)
    return by_dex, by_name


def _snapshots(output_dir: Path) -> list[dict[str, Any]]:
    index = _load(output_dir / "data" / "external" / "index.json", {}) or {}
    result = []
    for item in index.get("snapshots") or []:
        if str(item.get("data_category") or "").casefold() != "events" or not item.get("path"):
            continue
        payload = _load(output_dir / str(item["path"]), {}) or {}
        if str(payload.get("data_category") or "").casefold() == "events":
            result.append({"index": dict(item), "payload": payload})
    return result


def _source(snapshot: Mapping[str, Any], fact: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "provider": snapshot.get("provider"),
        "authority": snapshot.get("classification"),
        "source_reference": fact.get("source_reference") or snapshot.get("source_reference"),
        "source_references": list(snapshot.get("source_references") or []),
        "dataset_timestamp": snapshot.get("dataset_timestamp"),
        "data_version": snapshot.get("data_version"),
        "freshness": dict(snapshot.get("freshness") or {}),
        "validity": dict(snapshot.get("validity") or {}),
        "snapshot_path": snapshot.get("path"),
    }


def _fresh(source: Mapping[str, Any], now: datetime) -> bool:
    freshness = source.get("freshness") or {}
    if freshness.get("state") != "fresh":
        return False
    dataset = _time(source.get("dataset_timestamp"))
    max_age = freshness.get("max_age_hours")
    if not dataset or not isinstance(max_age, (int, float)) or max_age <= 0:
        return False
    if (now - dataset).total_seconds() / 3600 > float(max_age):
        return False
    valid_until = _time((source.get("validity") or {}).get("valid_until"))
    return not valid_until or now <= valid_until


def _actionable(source: Mapping[str, Any], start: Any, end: Any, now: datetime) -> bool:
    starts = _time(start)
    ends = _time(end)
    return bool(_fresh(source, now) and starts and ends and ends > starts and ends >= now)


def _event_dexes(fact: Mapping[str, Any]) -> list[int]:
    result: list[int] = []
    for key in ("featured_dex", "featured_dexes", "raid_targets", "boss_dexes", "reward_dexes"):
        for dex in _ints(fact.get(key)):
            if dex not in result:
                result.append(dex)
    return result


def _reference_types(reference: Mapping[str, Any]) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    for item in reference.get("entries") or []:
        try:
            dex = int(item.get("dex") or 0)
        except (TypeError, ValueError):
            continue
        if dex:
            result.setdefault(dex, set()).update(str(value).casefold() for value in item.get("types") or [])
    return result


def _overlays(
    fact: Mapping[str, Any],
    by_dex: Mapping[int, list[dict[str, Any]]],
    gaps: Mapping[str, Any],
    reference: Mapping[str, Any],
    roster: Mapping[str, Any],
) -> dict[str, Any]:
    gap_map = {int(item["dex"]): item for item in gaps.get("species") or [] if item.get("dex") is not None}
    weak = {str(item.get("type") or "").casefold() for item in roster.get("weakest") or [] if item.get("type")}
    types = _reference_types(reference)
    related = _event_dexes(fact)
    featured = _ints(fact.get("featured_dex"))
    owned = [_summary(record) for dex in related for record in by_dex.get(dex, [])]
    owned.sort(key=lambda item: (int(item.get("dex") or 0), str(item.get("record_id") or "")))
    missing = []
    for dex in featured:
        gap = gap_map.get(dex) or {}
        if gap.get("species_state") == "missing":
            missing.append({
                "dex": dex,
                "name": gap.get("name"),
                "route": (gap.get("links") or {}).get("reference") or f"reference.html?dex={dex}",
            })
    return {
        "exact_owned_records": owned,
        "strong_pvp_records": [item for item in owned if float(item.get("pvp_best_rank_percent") or 0) >= 98.0],
        "missing_featured_species": missing,
        "related_weak_roster_types": sorted({kind for dex in related for kind in types.get(dex, set()) if kind in weak}),
        "local_goal_matching": "runtime-browser-local",
        "prep_links": {
            "evolution": "evolution-lab.html",
            "moves": "move-lab.html",
            "mega_primal": "mega-lab.html",
            "max": "max-battle-lab.html",
            "buddy": "buddy-queue.html",
            "resources": "resource-vault.html",
            "opportunities": "opportunity-finder.html",
        },
    }


def _restrictions(fact: Mapping[str, Any]) -> dict[str, Any]:
    tokens = ("ticket", "paid", "region", "location", "condition", "requirement", "restriction")
    details = {
        key: value for key, value in fact.items()
        if value not in (None, "", [], {}) and any(token in str(key).casefold() for token in tokens)
    }
    return {"state": "qualified" if details else "none-explicitly-published", "details": details}


def _evolution_deadlines(
    fact: Mapping[str, Any], source: Mapping[str, Any], by_name: Mapping[str, list[dict[str, Any]]], event_id: str, start: str, now: datetime,
) -> list[dict[str, Any]]:
    result = []
    for index, target in enumerate(fact.get("evolution_targets") or []):
        if not isinstance(target, Mapping):
            continue
        source_name = str(target.get("required_evolution_from") or "").strip()
        end = target.get("window_ends_at") or target.get("ends_at")
        move = target.get("exclusive_charged_move") or target.get("exclusive_fast_move") or target.get("exclusive_move")
        target_name = target.get("name") or "target evolution"
        result.append({
            "id": f"{event_id}:evolution:{index}",
            "parent_event_id": event_id,
            "kind": "evolution-move-window",
            "title": f"Evolve {source_name or 'eligible Pokémon'} before the move window closes" + (f" for {target_name} with {move}" if move else ""),
            "starts_at": start,
            "ends_at": end,
            "timezone": fact.get("timezone"),
            "source": source,
            "actionable_at_build": _actionable(source, start, end, now),
            "exact_owned_records": [_summary(record) for record in by_name.get(_normal(source_name), [])],
            "target": {"dex": target.get("dex"), "name": target_name, "exclusive_move": move},
            "route": "evolution-lab.html",
            "manual_confirmation": "Confirm the exact eligible Pokémon and move window in Pokémon GO before evolving.",
        })
    return result


def _exclusive_deadlines(
    fact: Mapping[str, Any], source: Mapping[str, Any], by_dex: Mapping[int, list[dict[str, Any]]], event_id: str, start: str, now: datetime,
) -> list[dict[str, Any]]:
    result = []
    for index, window in enumerate(fact.get("exclusive_windows") or []):
        if not isinstance(window, Mapping):
            continue
        kind = str(window.get("kind") or "special-window")
        title = str(window.get("description") or kind.replace("-", " ").title())
        window_start = window.get("starts_at") or start
        end = window.get("ends_at") or window.get("window_ends_at")
        exact = []
        if "frustration" in f"{kind} {title}".casefold():
            exact = [
                _summary(record)
                for dex in _event_dexes(fact)
                for record in by_dex.get(dex, [])
                if str((record.get("status") or {}).get("shadow_purified") or "").casefold() == "shadow"
            ]
        result.append({
            "id": f"{event_id}:window:{index}",
            "parent_event_id": event_id,
            "kind": kind,
            "title": title,
            "starts_at": window_start,
            "ends_at": end,
            "timezone": fact.get("timezone"),
            "source": source,
            "actionable_at_build": _actionable(source, window_start, end, now),
            "exact_owned_records": exact,
            "route": "move-lab.html" if "frustration" in f"{kind} {title}".casefold() else "event-calendar.html",
            "manual_confirmation": "This deadline is actionable only while the reviewed source remains fresh at runtime.",
        })
    return result


def build_calendar(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    now = _as_of(manifest)
    records = list((_load(output_dir / "data" / "pokemon.json", {}) or {}).get("records") or [])
    reference = _load(output_dir / "data" / "reference" / "index.json", {}) or {}
    gaps = _load(output_dir / "data" / "gap-radar.json", {}) or {}
    roster = _load(output_dir / "data" / "roster-readiness.json", {}) or {}
    by_dex, by_name = _owned_maps(records)
    events: list[dict[str, Any]] = []
    deadlines: list[dict[str, Any]] = []
    snapshot_states: list[dict[str, Any]] = []

    for wrapped in _snapshots(output_dir):
        index = wrapped["index"]
        snapshot_states.append({
            "provider": index.get("provider"),
            "dataset_timestamp": index.get("dataset_timestamp"),
            "freshness": dict(index.get("freshness") or {}),
            "validity": dict(index.get("validity") or {}),
            "source_reference": index.get("source_reference"),
            "path": index.get("path"),
        })
        for position, raw in enumerate(wrapped["payload"].get("facts") or []):
            if not isinstance(raw, Mapping):
                continue
            fact = dict(raw)
            start = str(fact.get("starts_at") or fact.get("start") or "")
            end = str(fact.get("ends_at") or fact.get("end") or "")
            if not _time(start) or not _time(end):
                continue
            event_id = str(fact.get("event_id") or f"event-{position}")
            source = _source(index, fact)
            events.append({
                "id": event_id,
                "kind": "event",
                "title": fact.get("title") or event_id,
                "starts_at": start,
                "ends_at": end,
                "timezone": fact.get("timezone") or "source-defined local time",
                "source": source,
                "restrictions": _restrictions(fact),
                "featured_dex": _ints(fact.get("featured_dex")),
                "featured_species": list(fact.get("featured_species") or []),
                "raid_targets": _ints(fact.get("raid_targets")),
                "actionable_at_build": _actionable(source, start, end, now),
                "overlays": _overlays(fact, by_dex, gaps, reference, roster),
                "route": f"event-calendar.html?event={event_id}",
            })
            deadlines.extend(_evolution_deadlines(fact, source, by_name, event_id, start, now))
            deadlines.extend(_exclusive_deadlines(fact, source, by_dex, event_id, start, now))

    events.sort(key=lambda item: (_time(item["starts_at"]) or datetime.max.replace(tzinfo=timezone.utc), item["id"]))
    deadlines.sort(key=lambda item: (_time(item.get("ends_at")) or datetime.max.replace(tzinfo=timezone.utc), item["id"]))
    return {
        "schema_version": CALENDAR_VERSION,
        "build_id": manifest["build_id"],
        "generated_at": manifest.get("generated_at_utc") or manifest.get("generated_at"),
        "export_timestamp": manifest.get("export_timestamp"),
        "calendar_timezone_policy": "Source offsets are preserved; the browser renders exact times in the viewer's current IANA timezone and labels it explicitly.",
        "current_policy": {
            "required_snapshot_state": "fresh",
            "runtime_recheck": True,
            "stale_or_expired": "history-only; never shown in Now/Today/Next 7 days/Later actionable scopes",
            "unknown_time": "not actionable",
        },
        "history_policy": "Expired or stale reviewed events remain visible only in History with original evidence and timestamps.",
        "local_state": {
            "schema_version": LOCAL_STATE_VERSION,
            "storage": "browser-local-only",
            "contents": ["user reminders", "checklist completion", "selected scope"],
            "unified_backup": True,
            "canonical_collection_mutation": False,
        },
        "snapshot_states": snapshot_states,
        "events": events,
        "deadlines": deadlines,
        "actionable_at_build_count": sum(1 for item in [*events, *deadlines] if item.get("actionable_at_build")),
        "collection_overlay_policy": {
            "exact_owned_record_ids": True,
            "missing_featured_species_source": "data/gap-radar.json",
            "weak_roster_types_source": "data/roster-readiness.json",
            "pvp_strength_signal": "Poke Genie rank_percent >= 98 only; not a current-meta ranking",
            "local_goals": "matched at runtime from browser-local goal state",
        },
    }


def schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE_ID + "event-calendar.schema.json",
        "type": "object",
        "required": ["schema_version", "build_id", "current_policy", "history_policy", "local_state", "snapshot_states", "events", "deadlines"],
        "properties": {
            "schema_version": {"const": CALENDAR_VERSION},
            "build_id": {"type": "string", "pattern": "^[0-9a-f]{12}$"},
            "current_policy": {"type": "object"},
            "history_policy": {"type": "string"},
            "local_state": {"type": "object"},
            "snapshot_states": {"type": "array", "items": {"type": "object"}},
            "events": {"type": "array", "items": {"type": "object"}},
            "deadlines": {"type": "array", "items": {"type": "object"}},
        },
        "additionalProperties": True,
    }


def _page(output_dir: Path) -> None:
    (output_dir / "event-calendar.html").write_text('''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="Collection-aware Pokémon GO event agenda with freshness-gated deadlines and local reminders."><title>Event Calendar</title><link rel="stylesheet" href="assets/event-calendar.css" data-event-calendar-style></head>
<body><a class="skip-link" href="#event-calendar">Skip to content</a><main id="event-calendar" class="event-calendar-page">
<header class="event-calendar-header ds-card"><p><a href="today.html">Today</a> · <a href="index.html">Collection</a> · <a href="tools.html">Tools</a> · <a href="opportunity-finder.html">Opportunities</a></p><p class="event-calendar-eyebrow">#151 · Collection-aware planning</p><h1>Event Calendar</h1><p>Chronological Pokémon GO deadlines with exact local time, source freshness, collection overlays, and browser-local reminders.</p><p id="event-calendar-timezone" class="event-calendar-note"></p></header>
<section class="event-calendar-controls ds-card" aria-labelledby="calendar-scope-heading"><h2 id="calendar-scope-heading">Agenda scope</h2><div class="event-calendar-scopes" role="group" aria-label="Event agenda scope"><button type="button" data-calendar-scope="now" aria-pressed="true">Now</button><button type="button" data-calendar-scope="today" aria-pressed="false">Today</button><button type="button" data-calendar-scope="next7" aria-pressed="false">Next 7 days</button><button type="button" data-calendar-scope="later" aria-pressed="false">Later</button><button type="button" data-calendar-scope="history" aria-pressed="false">History</button></div><p id="event-calendar-status" role="status"></p></section>
<section class="event-calendar-reminders ds-card" aria-labelledby="event-reminders-heading"><h2 id="event-reminders-heading">Local reminders</h2><p class="event-calendar-note">Stored only in this browser and included in unified local-data backup.</p><div class="event-calendar-reminder-form"><label>Reminder <input id="event-reminder-title" type="text" maxlength="120" autocomplete="off"></label><label>When <input id="event-reminder-at" type="datetime-local"></label><button id="event-reminder-add" type="button">Add reminder</button></div><div id="event-reminder-list"></div></section>
<div id="event-calendar-root" aria-live="polite"><p class="ds-empty">Loading event agenda…</p></div></main><script defer src="assets/event-calendar.js" data-event-calendar-script></script></body></html>''', encoding="utf-8", newline="\n")


def _tools(output_dir: Path) -> None:
    path = output_dir / "tools.html"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    if 'id="event-calendar-tool"' not in source:
        block = '\n    <section id="event-calendar-tool" class="planner-card"><h2>Event Calendar</h2><p>Freshness-gated Pokémon GO deadlines with collection-aware preparation overlays.</p><p><a href="event-calendar.html">Open Event Calendar</a></p></section>\n'
        source = source.replace("  </main>", block + "  </main>", 1)
        path.write_text(source, encoding="utf-8", newline="\n")


def publish(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    del repository_root
    manifest_registry._SCHEMA_MAP["data/event-calendar.json"] = "data/event-calendar.schema.json"
    manifest_registry._STABLE_NAMES["data/event-calendar.json"] = "event_calendar"
    manifest_registry._STABLE_NAMES["data/event-calendar.schema.json"] = "event_calendar_schema"
    payload = build_calendar(output_dir, manifest)
    contract = schema()
    Draft202012Validator.check_schema(contract)
    Draft202012Validator(contract).validate(payload)
    _write(output_dir / "data" / "event-calendar.json", payload)
    _write(output_dir / "data" / "event-calendar.schema.json", contract)
    _page(output_dir)
    _tools(output_dir)
    llms = output_dir / "llms.txt"
    if llms.is_file():
        with llms.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\nEvent Calendar:\n- /event-calendar.html is the accessible agenda for current/upcoming Pokémon GO event windows and separate evolution/move deadlines.\n- /data/event-calendar.json retains stale/expired entries only as history; actionable scopes require fresh source evidence at runtime.\n")
    return payload


__all__ = ["CALENDAR_VERSION", "LOCAL_STATE_VERSION", "build_calendar", "schema", "publish"]
