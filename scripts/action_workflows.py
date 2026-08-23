"""Publish exact-record decisions, bounded change timeline, Action Packs, and Scan Inbox/preflight contracts.

Issues #129-#132 are intentionally one workflow layer.  This module composes already
published canonical collection, decision-support, history, mechanics, and current-data
resources.  It does not create a second recommendation engine and never turns missing
facts into destructive advice.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator

try:
    from . import build_site, manifest_registry, schema_contracts
except ImportError:
    import build_site
    import manifest_registry
    import schema_contracts

WORKFLOW_VERSION = "1.0.0"
DECISION_VERSION = "1.0.0"
TIMELINE_VERSION = "1.0.0"
ACTION_PACK_VERSION = "1.0.0"
SCAN_INBOX_VERSION = "1.0.0"
PREFLIGHT_VERSION = "1.0.0"
BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"
MAX_TIMELINE_ITEMS_PER_LANE = 100


def _load(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _record_id(record: Mapping[str, Any]) -> str:
    return str(record.get("identity", {}).get("record_id") or record.get("record_id") or "")


def _human(value: Any) -> str:
    return str(value or "").replace("_", " ").replace("-", " ").strip().capitalize()


def _form_key(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return "normal" if text in {"", "normal", "none", "ordinary"} else re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _records(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    values = payload.get("records")
    return [dict(item) for item in values] if isinstance(values, list) else []


def _queue_memberships(output_dir: Path) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    index = _load(output_dir / "data" / "recommendations" / "index.json", {}) or {}
    for queue in index.get("queues") or []:
        path = queue.get("path")
        name = str(queue.get("name") or "review")
        if not path:
            continue
        payload = _load(output_dir / str(path), {}) or {}
        for item in payload.get("records") or []:
            record_id = str(item.get("record_id") or "")
            if record_id:
                result[record_id].append({"queue": name, "source": str(path), **dict(item)})
    return result


def _scan_findings(output_dir: Path) -> dict[str, list[dict[str, Any]]]:
    quality = _load(output_dir / "data" / "scan-quality-report.json", {}) or {}
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in quality.get("findings") or []:
        record_id = str(finding.get("record_id") or "")
        if record_id:
            result[record_id].append(dict(finding))
    return result


def _reasoning(output_dir: Path) -> dict[str, dict[str, Any]]:
    payload = _load(output_dir / "data" / "reasoning" / "records.json", {}) or {}
    return {str(item.get("record_id")): item for item in _records(payload) if item.get("record_id")}


def _investments(output_dir: Path) -> dict[str, dict[str, Any]]:
    payload = _load(output_dir / "data" / "investments" / "records.json", {}) or {}
    return {str(item.get("record_id")): item for item in _records(payload) if item.get("record_id")}


def _explicit_protections(record: Mapping[str, Any]) -> list[str]:
    status = record.get("status") or {}
    ivs = record.get("ivs") or {}
    protections = []
    if status.get("favorite"):
        protections.append("favorite")
    if status.get("lucky"):
        protections.append("lucky")
    if status.get("marked_for_pvp"):
        protections.append("marked_for_pvp")
    if status.get("shadow_purified") in {"shadow", "purified"}:
        protections.append(str(status.get("shadow_purified")))
    if ivs.get("is_hundo"):
        protections.append("hundo")
    if ivs.get("is_nundo"):
        protections.append("nundo")
    return protections


def _pvp_score(record: Mapping[str, Any]) -> float | None:
    values = [
        item.get("rank_percent")
        for item in (record.get("pvp") or {}).values()
        if isinstance(item, Mapping) and item.get("rank_percent") is not None
    ]
    return max(float(value) for value in values) if values else None


def _best_owned_alternative(record: Mapping[str, Any], group: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    current = _pvp_score(record)
    if current is None:
        return None
    alternatives = []
    for other in group:
        other_id = _record_id(other)
        if not other_id or other_id == _record_id(record):
            continue
        score = _pvp_score(other)
        if score is not None and score > current:
            alternatives.append((score, other_id, other))
    if not alternatives:
        return None
    score, record_id, other = sorted(alternatives, key=lambda item: (-item[0], item[1]))[0]
    return {
        "record_id": record_id,
        "rank_percent": score,
        "cp": other.get("cp"),
        "statement": "Another owned copy has a higher known Poke Genie PvP IV percentile. This is not a current-meta ranking.",
    }


def build_decisions(output_dir: Path, manifest: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    canonical = _load(output_dir / "data" / "pokemon.json", {}) or {}
    records = canonical.get("records") or []
    queues = _queue_memberships(output_dir)
    findings = _scan_findings(output_dir)
    reasoning = _reasoning(output_dir)
    investments = _investments(output_dir)
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(int(record.get("pokemon_number") or 0), _form_key(record.get("form")))].append(record)

    cards: list[dict[str, Any]] = []
    for record in records:
        record_id = _record_id(record)
        memberships = queues.get(record_id, [])
        queue_names = {item["queue"] for item in memberships}
        scan = findings.get(record_id, [])
        reason = reasoning.get(record_id) or {}
        protections = _explicit_protections(record)
        known_recommendations = [
            str(item.get("recommendation"))
            for item in reason.get("recommendations") or []
            if isinstance(item, Mapping) and item.get("recommendation")
        ]
        irreversible = sorted(set(reason.get("irreversible_actions_blocked") or []))
        why: list[str] = []
        for item in memberships:
            why.extend(_human(value) for value in item.get("reasons") or [])
        why.extend(f"Explicit {value.replace('_', ' ')} protection" for value in protections)
        why.extend(_human(value) for value in known_recommendations[:4])
        why = list(dict.fromkeys(value for value in why if value))[:8]

        if scan or "rescan" in queue_names or "review_or_rescan_before_consequential_decision" in known_recommendations:
            recommendation = "Rescan before consequential decisions"
            status = "blocked"
            next_step = {"label": "Open Scan Inbox", "route": f"scan-inbox.html?record={record_id}"}
        elif protections or "pvp-candidates" in queue_names:
            recommendation = "Keep/protect while you review its role"
            status = "protect"
            next_step = {"label": "Open exact record", "route": f"index.html?record={record_id}"}
        elif "evolution-review" in queue_names:
            recommendation = "Review the evolution opportunity before evolving"
            status = "review"
            next_step = {"label": "Open evolution handoff", "route": f"action-packs.html?pack=evolution-review&record={record_id}"}
        elif "raid-investment-inputs" in queue_names or "resource-review" in queue_names:
            recommendation = "Review this build opportunity before spending resources"
            status = "review"
            next_step = {"label": "Open build handoff", "route": f"action-packs.html?pack=build-review&record={record_id}"}
        elif "duplicate-review" in queue_names:
            recommendation = "Compare this duplicate with your other owned copies"
            status = "review"
            next_step = {"label": "Open duplicate Action Pack", "route": f"action-packs.html?pack=duplicate-review&record={record_id}"}
        else:
            recommendation = "No destructive recommendation is supported"
            status = "observe"
            next_step = {"label": "Review exact record", "route": f"index.html?record={record_id}"}

        if not why:
            why = ["No queue or reasoning rule currently supports a stronger conclusion."]
        could_change = []
        if scan:
            could_change.append("A complete, current Poke Genie rescan could change this recommendation.")
        could_change.append("Shiny, costume, background, Max/Gigantamax, trade-reservation, and other unsupported owned statuses remain unknown unless explicitly present in a supported source.")
        if reason.get("external_freshness") not in {None, "fresh"}:
            could_change.append("Fresh current-game data could change time-sensitive role or opportunity conclusions.")
        alternative = _best_owned_alternative(record, grouped[(int(record.get("pokemon_number") or 0), _form_key(record.get("form")))])
        if alternative:
            why.append(alternative["statement"])

        evidence = [
            {"layer": "owned", "resource": "data/pokemon.json", "record_id": record_id},
            *({"layer": "reasoning", "resource": "data/reasoning/records.json", "record_id": record_id},) if reason else (),
        ]
        evidence.extend({"layer": "recommendation", "resource": item["source"], "queue": item["queue"]} for item in memberships)
        if scan:
            evidence.append({"layer": "scan-quality", "resource": "data/scan-quality-report.json", "record_id": record_id})
        if record_id in investments:
            evidence.append({"layer": "calculated-input", "resource": "data/investments/records.json", "record_id": record_id})

        cards.append({
            "record_id": record_id,
            "pokemon_number": record.get("pokemon_number"),
            "name": record.get("name"),
            "form": record.get("form"),
            "cp": record.get("cp"),
            "status": status,
            "recommendation": recommendation,
            "why": why[:10],
            "what_could_change_this": could_change,
            "exact_next_step": next_step,
            "queue_memberships": sorted(queue_names),
            "explicit_protections": protections,
            "unknown_protection_classes": ["shiny", "costume", "background", "max_state", "trade_reservation", "legacy_move"],
            "irreversible_actions_blocked": irreversible,
            "better_owned_alternative": alternative,
            "evidence": evidence,
            "guidance_invariant": True,
            "action_pack_route": f"action-packs.html?pack=locate-exact&record={record_id}",
        })

    records_payload = {
        "schema_version": DECISION_VERSION,
        "workflow_version": WORKFLOW_VERSION,
        "build_id": manifest["build_id"],
        "record_count": len(cards),
        "safety": {
            "automatic_destructive_action": False,
            "absence_of_evidence_is_not_transfer_safety": True,
            "guidance_changes_results": False,
        },
        "cards": cards,
    }
    index = {
        "schema_version": DECISION_VERSION,
        "workflow_version": WORKFLOW_VERSION,
        "build_id": manifest["build_id"],
        "record_count": len(cards),
        "records": "data/decisions/records.json",
        "route_pattern": "index.html?record={canonical_record_id}",
        "action_pack_route_pattern": "action-packs.html?pack=locate-exact&record={canonical_record_id}",
    }
    return index, records_payload


def _timeline_record(record: Mapping[str, Any]) -> dict[str, Any]:
    record_id = str(record.get("record_id") or "")
    return {
        "record_id": record_id or None,
        "pokemon_number": record.get("pokemon_number"),
        "name": record.get("name"),
        "form": record.get("form"),
        "cp": record.get("cp"),
        "route": f"index.html?record={record_id}" if record_id else "index.html",
    }


def build_timeline(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    diff = _load(output_dir / "data" / "collection-diff.json", {}) or {}
    history = _load(output_dir / "data" / "history-index.json", {}) or {}
    mechanics = _load(output_dir / "data" / "mechanics" / "index.json", {}) or {}
    external = _load(output_dir / "data" / "external" / "index.json", {}) or {}
    snapshots = history.get("snapshots") or []
    previous_timestamp = snapshots[-2].get("export_timestamp") if len(snapshots) > 1 else None
    previous_day = str(previous_timestamp or "")[:10]

    collection_entries: list[dict[str, Any]] = []
    for item in diff.get("added") or []:
        collection_entries.append({"kind": "added", "title": f"Added {_timeline_record(item)['name']}", "summary": "Present in the current normalized export and not conservatively matched to the previous snapshot.", **_timeline_record(item)})
    for item in diff.get("removed") or []:
        collection_entries.append({"kind": "removed-from-export", "title": f"No longer present: {_timeline_record(item)['name']}", "summary": "No longer present in the current normalized export. This does not prove an in-game transfer.", **_timeline_record(item)})
    for change in diff.get("changed") or []:
        after = change.get("after") or {}
        collection_entries.append({
            "kind": "changed",
            "title": f"Updated {_timeline_record(after)['name']}",
            "summary": ", ".join(_human(value) for value in change.get("change_kinds") or []) or "Record evidence changed.",
            "match": change.get("match"),
            "confidence": change.get("confidence"),
            **_timeline_record(after),
        })
    for item in diff.get("ambiguous") or []:
        collection_entries.append({"kind": "ambiguous", "title": "Ambiguous cross-build identity", "summary": _human(item.get("reason")), "route": "scan-inbox.html"})

    source_by_id = {str(item.get("id")): item for item in mechanics.get("sources") or []}
    mechanics_entries = []
    for domain in mechanics.get("domains") or []:
        applicable = str(domain.get("applicable_at") or "")
        if previous_day and applicable < previous_day:
            continue
        sources = [source_by_id[source_id] for source_id in domain.get("source_ids") or [] if source_id in source_by_id]
        mechanics_entries.append({
            "kind": "mechanics-review",
            "title": str(domain.get("label") or domain.get("id")),
            "summary": f"Reviewed mechanics state: {domain.get('status', 'unknown')}.",
            "authority": ", ".join(sorted({str(source.get('authority') or 'Unknown') for source in sources})) or "No external authority attached",
            "date": applicable or mechanics.get("reviewed_at"),
            "sources": [{"title": source.get("title"), "url": source.get("url"), "reviewed_at": source.get("reviewed_at")} for source in sources],
            "route": "mechanics-coverage.md",
        })

    current_entries = []
    seen_categories: set[str] = set()
    for snapshot in sorted(external.get("snapshots") or [], key=lambda item: str(item.get("dataset_timestamp") or ""), reverse=True):
        category = str(snapshot.get("data_category") or "current")
        if category in seen_categories or (snapshot.get("freshness") or {}).get("state") != "fresh":
            continue
        seen_categories.add(category)
        current_entries.append({
            "kind": "current-data",
            "title": f"Current {_human(category)} data",
            "summary": f"Newest fresh reviewed snapshot from {snapshot.get('provider') or 'source'}.",
            "authority": snapshot.get("classification"),
            "date": snapshot.get("dataset_timestamp"),
            "source_reference": snapshot.get("source_reference"),
            "source_resource": snapshot.get("path"),
            "route": f"today.html#current-{re.sub(r'[^a-z0-9]+', '-', category.casefold()).strip('-')}",
        })

    app_entries = [
        {"kind": "release-note", "title": "Exact-record decision cards", "summary": "Unified recommendation, evidence, uncertainty, next-step, and alternative-copy review on owned records.", "issue": 129, "route": "index.html"},
        {"kind": "release-note", "title": "Human change timeline", "summary": "Bounded collection, mechanics, current-game, local-planning, and app change lanes.", "issue": 130, "route": "changes.html"},
        {"kind": "release-note", "title": "Action Packs", "summary": "Safe Pokémon GO search/checklist handoffs with explicit representational gaps.", "issue": 131, "route": "action-packs.html"},
        {"kind": "release-note", "title": "Poke Genie Scan Inbox and local preflight", "summary": "Browser-only CSV validation before repository upload plus exact-record rescan queues.", "issue": 132, "route": "scan-inbox.html"},
    ]

    lanes = {
        "collection": {"status": "available" if history.get("snapshot_count", 0) else "history-unavailable", "entries": collection_entries[:MAX_TIMELINE_ITEMS_PER_LANE], "total_count": len(collection_entries), "source": "data/collection-diff.json"},
        "local-planning": {"status": "browser-local", "entries": [], "total_count": 0, "privacy": "Only local schema/version/count health is rendered in the browser. Note/goal contents are never published."},
        "mechanics": {"status": "available", "entries": mechanics_entries[:MAX_TIMELINE_ITEMS_PER_LANE], "total_count": len(mechanics_entries), "source": "data/mechanics/index.json"},
        "current-game": {"status": "available", "entries": current_entries[:MAX_TIMELINE_ITEMS_PER_LANE], "total_count": len(current_entries), "source": "data/external/index.json"},
        "app": {"status": "available", "entries": app_entries, "total_count": len(app_entries), "source": "user-facing release contract"},
    }
    return {
        "schema_version": TIMELINE_VERSION,
        "workflow_version": WORKFLOW_VERSION,
        "build_id": manifest["build_id"],
        "from_build_id": diff.get("from_build_id"),
        "to_build_id": diff.get("to_build_id") or manifest["build_id"],
        "previous_export_timestamp": previous_timestamp,
        "bounded": True,
        "max_items_per_lane": MAX_TIMELINE_ITEMS_PER_LANE,
        "removal_semantics": diff.get("wording") or "A missing record never proves an in-game transfer.",
        "lanes": lanes,
    }


def _go_safe_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text if text and not any(character in text for character in "&,;:") else None


def record_search(record: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deliberately narrow reviewed search, never an asserted exact-record selector."""
    terms: list[str] = []
    gaps: list[str] = []
    dex = record.get("pokemon_number")
    cp = record.get("cp")
    if dex is not None:
        terms.append(str(int(dex)))
    if cp is not None:
        terms.append(f"cp{int(cp)}")
    status = record.get("status") or {}
    ivs = record.get("ivs") or {}
    shadow = status.get("shadow_purified")
    if shadow in {"shadow", "purified"}:
        terms.append(str(shadow))
    if status.get("lucky"):
        terms.append("lucky")
    if status.get("favorite"):
        terms.append("favorite")
    if ivs.get("is_hundo"):
        terms.append("4*")
    elif ivs.get("is_nundo"):
        terms.extend(["0attack", "0defense", "0hp"])
    elif any(ivs.get(key) is not None for key in ("attack", "defense", "stamina")):
        gaps.append("Exact non-hundo/nundo IV values are not represented exactly by the reviewed appraisal-band operators.")
    moves = record.get("moves") or {}
    fast = _go_safe_text(moves.get("fast"))
    charged = _go_safe_text(moves.get("charged"))
    if fast:
        terms.append(f"@1{fast}")
    elif moves.get("fast"):
        gaps.append("Fast move contains syntax-significant characters and was omitted.")
    if charged:
        terms.append(f"@2{charged}")
    elif moves.get("charged"):
        gaps.append("Charged move contains syntax-significant characters and was omitted.")
    if record.get("form"):
        gaps.append("Poke Genie form labels are not assumed to map exactly to Pokémon GO inventory-search form terms.")
    gaps.extend([
        "Canonical record IDs are companion-only and cannot be searched in Pokémon GO.",
        "Catch/scan timestamps are not encoded in this handoff.",
    ])
    return {"search": "&".join(terms), "representational_gaps": list(dict.fromkeys(gaps)), "exact": False}


def _pack(pack_id: str, title: str, description: str, records: list[Mapping[str, Any]], *, warning: str, status: str = "available", steps: list[str] | None = None) -> dict[str, Any]:
    batches = []
    manual = []
    for record in records:
        search = record_search(record)
        record_id = _record_id(record)
        batches.append({
            "record_ids": [record_id] if record_id else [],
            "search": search["search"],
            "exact": False,
            "explanation": "Narrow Pokémon GO inventory search for manual identification. Verify the displayed Pokémon before acting.",
            "representational_gaps": search["representational_gaps"],
        })
        manual.append(record_id)
    return {
        "id": pack_id,
        "title": title,
        "description": description,
        "status": status,
        "warning": warning,
        "suggested_tag": f"PGC-{pack_id[:16]}",
        "batches": batches,
        "manual_review_record_ids": [value for value in manual if value],
        "steps": steps or ["Copy one narrow search batch.", "Paste it into Pokémon GO inventory search.", "Verify identity and every warning manually.", "Apply only the intended reversible tag/checklist step first."],
        "source_route": "index.html",
    }


def build_action_packs(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    records = _load(output_dir / "data" / "pokemon.json", {}).get("records", [])
    by_id = {_record_id(record): record for record in records if _record_id(record)}
    queues = _queue_memberships(output_dir)
    rescan_ids = sorted(record_id for record_id, items in queues.items() if any(item["queue"] == "rescan" for item in items))
    duplicate_ids = sorted(record_id for record_id, items in queues.items() if any(item["queue"] == "duplicate-review" for item in items))
    pvp_ids = sorted(record_id for record_id, items in queues.items() if any(item["queue"] == "pvp-candidates" for item in items))
    raid_ids = sorted(record_id for record_id, items in queues.items() if any(item["queue"] == "raid-investment-inputs" for item in items))
    evolution_ids = sorted(record_id for record_id, items in queues.items() if any(item["queue"] == "evolution-review" for item in items))

    packs = [
        _pack("rescan-incomplete", "Rescan incomplete records", "Locate records whose scan evidence blocks consequential decisions.", [by_id[value] for value in rescan_ids if value in by_id], warning="This pack locates review targets only. It does not change canonical data until a new export is committed and deployed.", steps=["Copy one narrow search.", "Open the matching Pokémon in GO.", "Run Appraise and show the full detail/move screen.", "Rescan it in Poke Genie.", "Export a new CSV only after the scans are complete."]),
        _pack("duplicate-review", "Review duplicate candidates", "Locate owned species/form duplicates for side-by-side review.", [by_id[value] for value in duplicate_ids if value in by_id], warning="Duplicate status is never proof that a copy is expendable. Do not use this as a blind transfer list."),
        _pack("pvp-party", "Build selected PvP party", "Starting candidates from known Poke Genie league-IV evidence. Current meta strength is not implied.", [by_id[value] for value in pvp_ids[:6] if value in by_id], warning="Verify league, moves, current meta, and resource costs before spending or using Elite TMs."),
        _pack("raid-max-party", "Build selected raid / Max party", "Starting candidates from static raid-investment inputs; current boss/Max suitability requires fresh data.", [by_id[value] for value in raid_ids[:6] if value in by_id], warning="Do not infer current raid or Max relevance from this static candidate set."),
        _pack("evolution-review", "Review evolution targets", "Locate records with a represented evolution opportunity.", [by_id[value] for value in evolution_ids if value in by_id], warning="Evolution is irreversible. Current exclusive-move windows and special requirements must be verified before evolving."),
        _pack("trade-review", "Review trade candidates", "No record becomes a trade candidate from duplicate status alone.", [], warning="Trading is irreversible and may change IVs. This pack remains manual until an explicit supported trade-candidate source exists.", status="manual-only"),
        _pack("locate-exact", "Locate recommendation records", "Interactive exact-record handoff. The browser filters this pack to record IDs supplied in the URL.", [], warning="Pokémon GO cannot search by companion canonical record ID. Generated searches are narrow locators and always require manual identity verification.", status="interactive"),
    ]
    operator_contract = {
        "mechanics_resource": "data/mechanics/index.json",
        "required_domain": "inventory-search",
        "authority": "Official Pokémon GO inventory search help, as reviewed by #123",
        "supported_templates": ["dex", "cp", "shadow", "purified", "lucky", "favorite", "4*", "0attack", "0defense", "0hp", "@1move", "@2move", "AND (&)"],
        "policy": "Every generated batch is a locator/review handoff unless an exact representability proof exists. No current template is labeled a safe blind transfer list.",
    }
    return {
        "schema_version": ACTION_PACK_VERSION,
        "workflow_version": WORKFLOW_VERSION,
        "build_id": manifest["build_id"],
        "operator_contract": operator_contract,
        "pack_count": len(packs),
        "packs": packs,
    }


_RESCAN_STEPS = {
    "missing_ivs": ["Open the Pokémon in Pokémon GO.", "Tap Appraise and reveal the IV bars.", "Rescan the appraisal in Poke Genie."],
    "missing_moves": ["Open the Pokémon detail screen.", "Scroll until both attacks are visible.", "Rescan in Poke Genie and verify the move names."],
    "missing_level": ["Open the full Pokémon detail screen with CP/HP/power-up arc visible.", "Rescan in Poke Genie and confirm the level estimate."],
    "stale_scan": ["Open the current Pokémon detail screen.", "Rescan it in Poke Genie so the export reflects current CP, level, and moves."],
    "ambiguous_identity": ["Verify form, gender, exact IVs, catch/original scan date, status, and moves for each similar copy.", "Rescan each copy separately in Poke Genie."],
}


def _steps_for(reason: Any) -> list[str]:
    key = str(reason or "").casefold().replace("-", "_")
    for needle, steps in _RESCAN_STEPS.items():
        if needle in key:
            return steps
    return ["Open the exact Pokémon in Pokémon GO.", "Show the full detail screen and Appraise view.", "Rescan in Poke Genie and verify form, status, IVs, level, and moves before exporting again."]


def build_scan_inbox(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    quality = _load(output_dir / "data" / "scan-quality-report.json", {}) or {}
    diff = _load(output_dir / "data" / "collection-diff.json", {}) or {}
    decisions = _load(output_dir / "data" / "decisions" / "records.json", {}) or {}
    by_decision = {str(item.get("record_id")): item for item in decisions.get("cards") or []}
    records = _load(output_dir / "data" / "pokemon.json", {}).get("records", [])
    by_id = {_record_id(record): record for record in records if _record_id(record)}
    queues = {"rescan-first": [], "verify": [], "ambiguous": [], "recommendation-blockers": [], "healthy": []}
    problem_ids: set[str] = set()
    for finding in quality.get("findings") or []:
        record_id = str(finding.get("record_id") or "")
        if not record_id:
            continue
        problem_ids.add(record_id)
        reason = finding.get("reason_code") or "scan_quality_finding"
        action = str(finding.get("suggested_action") or "review")
        queue = "rescan-first" if action == "rescan" else "verify"
        if "ambiguous" in str(reason).casefold() or "duplicate" in str(reason).casefold():
            queue = "ambiguous"
        queues[queue].append({
            "record_id": record_id,
            "name": (by_id.get(record_id) or {}).get("name"),
            "reason": reason,
            "severity": finding.get("severity"),
            "steps": _steps_for(reason),
            "record_route": f"index.html?record={record_id}",
            "action_pack_route": f"action-packs.html?pack=rescan-incomplete&record={record_id}",
        })
    for item in diff.get("ambiguous") or []:
        queues["ambiguous"].append({"record_id": None, "name": None, "reason": item.get("reason"), "severity": "review", "steps": _steps_for("ambiguous_identity"), "record_route": "index.html", "action_pack_route": "action-packs.html?pack=rescan-incomplete"})
    for record_id, card in by_decision.items():
        if card.get("status") == "blocked" and record_id not in problem_ids:
            queues["recommendation-blockers"].append({"record_id": record_id, "name": card.get("name"), "reason": "missing_or_stale_evidence_blocks_recommendation", "severity": "review", "steps": _steps_for("missing_ivs"), "record_route": f"index.html?record={record_id}", "action_pack_route": f"action-packs.html?pack=rescan-incomplete&record={record_id}"})
            problem_ids.add(record_id)
    for record in records:
        record_id = _record_id(record)
        if record_id and record_id not in problem_ids:
            queues["healthy"].append({"record_id": record_id, "name": record.get("name"), "record_route": f"index.html?record={record_id}"})
    counts = {name: len(items) for name, items in queues.items()}
    return {
        "schema_version": SCAN_INBOX_VERSION,
        "workflow_version": WORKFLOW_VERSION,
        "build_id": manifest["build_id"],
        "counts": counts,
        "queues": queues,
        "canonicality": "Browser preflight and Scan Inbox are advisory. Only a committed export that passes the production build becomes canonical.",
    }


def build_preflight_contract(manifest: Mapping[str, Any]) -> dict[str, Any]:
    optional_groups = {name: list(columns) for name, columns in schema_contracts.OPTIONAL_COLUMN_GROUPS.items()}
    return {
        "schema_version": PREFLIGHT_VERSION,
        "workflow_version": WORKFLOW_VERSION,
        "build_id": manifest["build_id"],
        "export_schema_version": schema_contracts.EXPORT_SCHEMA_VERSION,
        "normalized_schema_version": schema_contracts.NORMALIZED_SCHEMA_VERSION,
        "required_columns": list(schema_contracts.CORE_COLUMNS),
        "known_columns": list(schema_contracts.known_columns()),
        "optional_column_groups": optional_groups,
        "filename_pattern": build_site.EXPORT_PATTERN.pattern,
        "filename_example": "shared-text-2026-08-23 03_27_00.000.csv",
        "row_requirements": {
            "Name": "non-empty string",
            "Pokemon Number": "numeric value accepted by the production normalizer",
            "CP": "numeric value accepted by the production normalizer",
        },
        "normalization": {
            "blank_values": "null/false/normal according to the production field type",
            "numbers": "commas are removed before numeric parsing",
            "truthy": ["1", "true", "True", "TRUE", "yes", "Yes", "Y"],
            "shadow_codes": {"1": "shadow", "2": "purified", "other": "normal"},
        },
        "privacy": "Selected CSV bytes are parsed only in the browser and are never uploaded by the preflight code.",
        "upload": {"strategy": "derive GitHub repository from github.io host when possible; otherwise show manual repository-upload instructions", "destination": "exports/"},
    }


def _schema(name: str, required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE_ID + name + ".schema.json",
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": True,
    }


def schemas() -> dict[str, dict[str, Any]]:
    string = {"type": "string"}
    count = {"type": "integer", "minimum": 0}
    build = {"type": "string", "pattern": "^[0-9a-f]{12}$"}
    return {
        "decision-index.schema.json": _schema("decision-index", ["schema_version", "build_id", "record_count", "records"], {"schema_version": string, "build_id": build, "record_count": count, "records": string}),
        "decision-records.schema.json": _schema("decision-records", ["schema_version", "build_id", "record_count", "cards", "safety"], {"schema_version": string, "build_id": build, "record_count": count, "cards": {"type": "array", "items": {"type": "object"}}, "safety": {"type": "object"}}),
        "change-timeline.schema.json": _schema("change-timeline", ["schema_version", "build_id", "bounded", "lanes"], {"schema_version": string, "build_id": build, "bounded": {"type": "boolean", "const": True}, "lanes": {"type": "object"}}),
        "action-packs.schema.json": _schema("action-packs", ["schema_version", "build_id", "operator_contract", "pack_count", "packs"], {"schema_version": string, "build_id": build, "operator_contract": {"type": "object"}, "pack_count": count, "packs": {"type": "array", "items": {"type": "object"}}}),
        "scan-inbox.schema.json": _schema("scan-inbox", ["schema_version", "build_id", "counts", "queues", "canonicality"], {"schema_version": string, "build_id": build, "counts": {"type": "object"}, "queues": {"type": "object"}, "canonicality": string}),
        "preflight-contract.schema.json": _schema("preflight-contract", ["schema_version", "build_id", "required_columns", "known_columns", "filename_pattern", "row_requirements", "privacy"], {"schema_version": string, "build_id": build, "required_columns": {"type": "array", "items": string}, "known_columns": {"type": "array", "items": string}, "filename_pattern": string, "row_requirements": {"type": "object"}, "privacy": string}),
    }


def _publish_schemas(output_dir: Path) -> None:
    data = output_dir / "data"
    for filename, schema in schemas().items():
        Draft202012Validator.check_schema(schema)
        _write(data / filename, schema)


def _page(output_dir: Path, filename: str, title: str, mount_id: str, description: str) -> None:
    html = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
</head>
<body>
<main class="product-page">
  <header class="product-page-header ds-card">
    <p><a href="today.html">Today</a> · <a href="index.html">Collection</a> · <a href="changes.html">What changed?</a> · <a href="action-packs.html">Action Packs</a> · <a href="scan-inbox.html">Scan Inbox</a> · <a href="reference.html">Reference</a></p>
    <h1>{title}</h1>
    <p>{description}</p>
  </header>
  <div id="{mount_id}"><p class="ds-empty">Loading…</p></div>
</main>
</body>
</html>
'''
    (output_dir / filename).write_text(html, encoding="utf-8", newline="\n")


def _register_contracts() -> None:
    mappings = {
        "data/decisions/index.json": "data/decision-index.schema.json",
        "data/decisions/records.json": "data/decision-records.schema.json",
        "data/change-timeline.json": "data/change-timeline.schema.json",
        "data/action-packs/index.json": "data/action-packs.schema.json",
        "data/scan-inbox.json": "data/scan-inbox.schema.json",
        "data/preflight-contract.json": "data/preflight-contract.schema.json",
    }
    manifest_registry._SCHEMA_MAP.update(mappings)
    names = {
        "data/decisions/index.json": "decision_index",
        "data/decisions/records.json": "decision_records",
        "data/change-timeline.json": "change_timeline",
        "data/action-packs/index.json": "action_packs",
        "data/scan-inbox.json": "scan_inbox",
        "data/preflight-contract.json": "preflight_contract",
        "data/decision-index.schema.json": "decision_index_schema",
        "data/decision-records.schema.json": "decision_records_schema",
        "data/change-timeline.schema.json": "change_timeline_schema",
        "data/action-packs.schema.json": "action_packs_schema",
        "data/scan-inbox.schema.json": "scan_inbox_schema",
        "data/preflight-contract.schema.json": "preflight_contract_schema",
    }
    manifest_registry._STABLE_NAMES.update(names)


def publish(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Publish #129-#132 resources and human entry pages."""
    _register_contracts()
    decision_index, decisions = build_decisions(output_dir, manifest)
    _write(output_dir / "data" / "decisions" / "index.json", decision_index)
    _write(output_dir / "data" / "decisions" / "records.json", decisions)
    timeline = build_timeline(output_dir, manifest)
    _write(output_dir / "data" / "change-timeline.json", timeline)
    packs = build_action_packs(output_dir, manifest)
    _write(output_dir / "data" / "action-packs" / "index.json", packs)
    inbox = build_scan_inbox(output_dir, manifest)
    _write(output_dir / "data" / "scan-inbox.json", inbox)
    preflight = build_preflight_contract(manifest)
    _write(output_dir / "data" / "preflight-contract.json", preflight)
    _publish_schemas(output_dir)
    _page(output_dir, "changes.html", "What changed?", "change-timeline-root", "Meaningful collection, mechanics, current-game, local-planning, and app changes with conservative identity semantics.")
    _page(output_dir, "action-packs.html", "Action Packs", "action-packs-root", "Safe Pokémon GO search, tag, and checklist handoffs. Every representational gap remains explicit.")
    _page(output_dir, "scan-inbox.html", "Poke Genie Scan Inbox", "scan-inbox-root", "Review scan problems and preflight a Poke Genie CSV locally before repository upload. Selected files never leave this browser.")
    return {"decisions": decision_index, "timeline": timeline, "action_packs": packs, "scan_inbox": inbox, "preflight": preflight}


__all__ = [
    "WORKFLOW_VERSION", "build_decisions", "build_timeline", "build_action_packs",
    "build_scan_inbox", "build_preflight_contract", "record_search", "publish", "schemas",
]
