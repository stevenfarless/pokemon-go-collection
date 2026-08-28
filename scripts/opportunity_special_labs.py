"""Publish freshness-gated Opportunity Finder and typed Special Mechanics Lab resources.

Issue #145 consumes only build-verified fresh acquisition snapshots and preserves
unknown restrictions/rates. Issue #146 composes reviewed special-mechanic facts
with exact owned records without inferring local fusion/resource state.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator

try:
    from . import manifest_registry
except ImportError:
    import manifest_registry

LAB_VERSION = "1.0.0"
OPPORTUNITY_VERSION = "1.0.0"
SPECIAL_VERSION = "1.0.0"
BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"
ACQUISITION_CATEGORIES = (
    "events", "raids", "max-battles", "research", "eggs", "rocket", "team-go-rocket", "rocket-lineups",
)
DEX_KEYS = {"dex", "pokemon_number", "boss_dex", "reward_dex", "encounter_dex", "pokemon_dex", "featured_dex"}
DEX_LIST_KEYS = {"featured_dexes", "boss_dexes", "reward_dexes", "encounter_dexes", "pokemon_dexes", "featured_dex", "raid_targets"}
FORM_KEYS = ("form_key", "form", "pokemon_form", "boss_form", "reward_form")
START_KEYS = ("start", "starts_at", "start_at", "start_time", "valid_from", "available_from")
END_KEYS = ("end", "ends_at", "end_at", "end_time", "valid_until", "available_until")
RATE_KEYS = ("encounter_rate", "rate", "odds", "probability")
RESTRICTION_KEYS = (
    "ticket_required", "ticket", "location", "region", "condition", "conditions", "requirements", "restriction", "restrictions",
)
DIRECT_CONTEXT_KEYS = {"name", "form", "form_key", "tier", "region", "reward", "encounter", "shiny_available"}
CONTAINER_KEYS = {"bosses", "encounters", "rewards", "pool"}
INHERITED_KEYS = {*START_KEYS, *END_KEYS, *RESTRICTION_KEYS, "timezone", "source_reference"}


def _load(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _form_key(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if text in {"", "normal", "none", "ordinary"}:
        return "normal"
    aliases = {"alolan": "alola", "galarian": "galar", "hisuian": "hisui", "paldean": "paldea"}
    text = aliases.get(text, text)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "normal"


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_of(manifest: Mapping[str, Any]) -> datetime:
    for key in ("export_timestamp", "generated_at", "build_timestamp"):
        parsed = _parse_time(manifest.get(key))
        if parsed:
            return parsed
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _first(raw: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = raw.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _dexes(value: Any) -> set[int]:
    found: set[int] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key).casefold()
            if name in DEX_KEYS and child not in (None, ""):
                values = child if isinstance(child, list) else [child]
                for item in values:
                    try:
                        found.add(int(item))
                    except (TypeError, ValueError):
                        pass
            elif name in DEX_LIST_KEYS and isinstance(child, list):
                for item in child:
                    try:
                        found.add(int(item))
                    except (TypeError, ValueError):
                        pass
            else:
                found.update(_dexes(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_dexes(child))
    return found


def _direct_dexes(raw: Mapping[str, Any]) -> set[int]:
    found: set[int] = set()
    for key, child in raw.items():
        name = str(key).casefold()
        if name not in DEX_KEYS and name not in DEX_LIST_KEYS:
            continue
        values = child if isinstance(child, list) else [child]
        for item in values:
            try:
                found.add(int(item))
            except (TypeError, ValueError):
                pass
    return found


def _looks_like_acquisition_fact(raw: Mapping[str, Any]) -> bool:
    keys = {str(key).casefold() for key in raw}
    direct = _direct_dexes(raw)
    markers = {
        "featured_dex", "featured_dexes", "boss_dex", "boss_dexes", "reward_dex", "reward_dexes",
        "encounter_dex", "encounter_dexes", "pokemon_dex", "pokemon_dexes", "raid_targets",
    }
    return bool(direct) and (bool(keys.intersection(markers)) or bool(keys.intersection(DIRECT_CONTEXT_KEYS)))


def _walk_acquisition_facts(value: Any, inherited: Mapping[str, Any] | None = None) -> Iterable[dict[str, Any]]:
    if isinstance(value, Mapping):
        context = dict(inherited or {})
        for key in INHERITED_KEYS:
            if key in value and value.get(key) not in (None, "", [], {}):
                context[key] = value.get(key)
        keys = {str(key).casefold() for key in value}
        if _looks_like_acquisition_fact(value) and not keys.intersection(CONTAINER_KEYS):
            yield {**context, **dict(value)}
        for child in value.values():
            yield from _walk_acquisition_facts(child, context)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_acquisition_facts(child, inherited)


def _fresh_snapshots(output_dir: Path) -> list[dict[str, Any]]:
    index = _load(output_dir / "data" / "external" / "index.json", {}) or {}
    allowed = {item.casefold() for item in ACQUISITION_CATEGORIES}
    result: list[dict[str, Any]] = []
    for raw in index.get("snapshots") or []:
        category = str(raw.get("data_category") or "").casefold()
        path = str(raw.get("path") or "")
        if category not in allowed or (raw.get("freshness") or {}).get("state") != "fresh" or not path:
            continue
        payload = _load(output_dir / path, {}) or {}
        if (payload.get("freshness") or {}).get("state") != "fresh":
            continue
        result.append({"index": dict(raw), "payload": payload})
    return result


def _reference_maps(reference: Mapping[str, Any]) -> tuple[dict[tuple[int, str], dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    by_key: dict[tuple[int, str], dict[str, Any]] = {}
    by_dex: dict[int, list[dict[str, Any]]] = {}
    for raw in reference.get("entries") or []:
        item = dict(raw)
        dex = int(item.get("dex") or 0)
        if not dex:
            continue
        by_key[(dex, _form_key(item.get("form_key")))] = item
        by_dex.setdefault(dex, []).append(item)
    return by_key, by_dex


def _fact_form(raw: Mapping[str, Any]) -> str | None:
    value = _first(raw, FORM_KEYS)
    return _form_key(value) if value not in (None, "") else None


def _match_reference(
    dex: int,
    fact: Mapping[str, Any],
    by_key: Mapping[tuple[int, str], dict[str, Any]],
    by_dex: Mapping[int, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str]:
    form = _fact_form(fact)
    if form is not None and (dex, form) in by_key:
        return by_key[(dex, form)], "exact-species-form"
    candidates = [item for item in by_dex.get(dex, []) if item.get("released") is True]
    ordinary = [item for item in candidates if not item.get("transformation_kind")]
    if form is None and len(ordinary) == 1:
        return ordinary[0], "unique-released-species"
    if form is None and (dex, "normal") in by_key:
        return by_key[(dex, "normal")], "species-only-form-unknown"
    return None, "ambiguous-or-unsupported-form"


def _window(raw: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    validity = source.get("validity") or {}
    start = _first(raw, START_KEYS) or _first(validity, START_KEYS)
    end = _first(raw, END_KEYS) or _first(validity, END_KEYS)
    return {
        "start": str(start) if start not in (None, "") else None,
        "end": str(end) if end not in (None, "") else None,
        "timezone": str(raw.get("timezone") or validity.get("timezone") or "source-defined/unknown"),
    }


def _restriction_details(raw: Mapping[str, Any]) -> dict[str, Any]:
    details = {key: raw.get(key) for key in RESTRICTION_KEYS if raw.get(key) not in (None, "", [], {})}
    for key, value in raw.items():
        normalized = str(key).casefold()
        if value in (None, "", [], {}) or key in details:
            continue
        if any(token in normalized for token in ("ticket", "paid", "pass", "location", "region", "condition", "restriction")):
            details[str(key)] = value
    return {"state": "qualified" if details else "not-specified-by-source", "details": details}


def _explicit_rate(raw: Mapping[str, Any]) -> dict[str, Any]:
    for key in RATE_KEYS:
        if key in raw and raw.get(key) not in (None, ""):
            return {"state": "source-provided", "value": raw.get(key), "field": key}
    return {"state": "unknown", "value": None, "field": None}


def _group_for_window(window: Mapping[str, Any], as_of: datetime) -> str:
    start = _parse_time(window.get("start"))
    end = _parse_time(window.get("end"))
    if start and start > as_of:
        return "this_week" if start <= as_of + timedelta(days=7) else "later"
    if end and end < as_of:
        return "expired"
    if end and end <= as_of + timedelta(hours=24):
        return "ending_soon"
    if not start or start <= as_of:
        return "right_now"
    return "this_week"


def _gap_maps(gap_payload: Mapping[str, Any]) -> tuple[dict[int, dict[str, Any]], set[tuple[int, str]]]:
    species = {int(item["dex"]): dict(item) for item in gap_payload.get("species") or [] if item.get("dex") is not None}
    missing_forms = {
        (int(item["dex"]), _form_key(item.get("form_key")))
        for item in gap_payload.get("forms") or []
        if item.get("dex") is not None and item.get("state") == "missing"
    }
    return species, missing_forms


def _weak_types(roster: Mapping[str, Any]) -> set[str]:
    return {str(item.get("type") or "").casefold() for item in roster.get("weakest") or [] if item.get("type")}


def _opportunity_id(category: str, dex: int, species_id: str, source: Mapping[str, Any], ordinal: int) -> str:
    raw = "|".join([category, str(dex), species_id, str(source.get("provider") or ""), str(source.get("dataset_timestamp") or ""), str(ordinal)])
    return re.sub(r"[^a-z0-9]+", "-", raw.casefold()).strip("-")[:180]


def build_opportunity_finder(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    reference = _load(output_dir / "data" / "reference" / "index.json", {}) or {}
    gaps = _load(output_dir / "data" / "gap-radar.json", {}) or {}
    roster = _load(output_dir / "data" / "roster-readiness.json", {}) or {}
    by_key, by_dex = _reference_maps(reference)
    gap_by_dex, missing_forms = _gap_maps(gaps)
    weak_types = _weak_types(roster)
    snapshots = _fresh_snapshots(output_dir)
    as_of = _as_of(manifest)

    opportunities: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for wrapped in snapshots:
        source = wrapped["index"]
        category = str(source.get("data_category") or "current").casefold()
        facts = list(_walk_acquisition_facts((wrapped["payload"] or {}).get("facts") or []))
        for ordinal, fact in enumerate(facts):
            for dex in sorted(_direct_dexes(fact)):
                ref, join_state = _match_reference(dex, fact, by_key, by_dex)
                species_id = str((ref or {}).get("species_id") or f"dex-{dex}")
                form = str((ref or {}).get("form_key") or _fact_form(fact) or "")
                key = (category, dex, form, source.get("provider"), source.get("dataset_timestamp"), json.dumps(fact, sort_keys=True, default=str))
                if key in seen:
                    continue
                seen.add(key)
                gap = gap_by_dex.get(dex) or {}
                missing_species = gap.get("species_state") == "missing"
                missing_form = bool(ref and (dex, _form_key(ref.get("form_key"))) in missing_forms)
                types = [str(value).casefold() for value in (ref or {}).get("types") or []]
                roster_match = sorted(set(types).intersection(weak_types))
                reasons = []
                if missing_species:
                    reasons.append("missing-species")
                if missing_form:
                    reasons.append("missing-form")
                if roster_match:
                    reasons.append("weak-roster-type")
                if not reasons:
                    reasons.append("currently-featured-owned-species")
                window = _window(fact, source)
                group = _group_for_window(window, as_of)
                if group == "expired":
                    continue
                opportunities.append({
                    "id": _opportunity_id(category, dex, species_id, source, ordinal),
                    "channel": category,
                    "dex": dex,
                    "species_id": species_id,
                    "display_name": (ref or {}).get("display_name") or (ref or {}).get("base_name") or f"Pokédex #{dex}",
                    "form_key": (ref or {}).get("form_key"),
                    "join_state": join_state,
                    "owned_count": int((ref or {}).get("owned_count") or len(gap.get("owned_record_ids") or [])),
                    "owned_record_ids": list((ref or {}).get("owned_record_ids") or gap.get("owned_record_ids") or []),
                    "personalization": {
                        "reasons": reasons,
                        "missing_species": missing_species,
                        "missing_form": missing_form,
                        "weak_roster_types": roster_match,
                    },
                    "window": window,
                    "group": group,
                    "source": {
                        "provider": source.get("provider"),
                        "classification": source.get("classification"),
                        "authority": source.get("authority"),
                        "dataset_timestamp": source.get("dataset_timestamp"),
                        "source_reference": fact.get("source_reference") or source.get("source_reference"),
                        "freshness": "fresh",
                    },
                    "restrictions": _restriction_details(fact),
                    "encounter_rate": _explicit_rate(fact),
                    "reference": (ref or {}).get("route") or f"reference.html?dex={dex}",
                    "raw_fact_summary": {key: value for key, value in fact.items() if key in {*START_KEYS, *END_KEYS, *RESTRICTION_KEYS, *RATE_KEYS}},
                })

    opportunities.sort(key=lambda item: (
        {"ending_soon": 0, "right_now": 1, "this_week": 2, "later": 3}.get(item["group"], 4),
        not item["personalization"]["missing_species"],
        not item["personalization"]["missing_form"],
        item["dex"], item["channel"], item["id"],
    ))

    current_dexes = {int(item["dex"]) for item in opportunities}
    no_path = []
    for item in gaps.get("species") or []:
        dex = int(item.get("dex") or 0)
        if not dex or item.get("species_state") != "missing" or dex in current_dexes:
            continue
        no_path.append({
            "dex": dex, "species_id": item.get("species_id"), "display_name": item.get("name"),
            "reason": "No build-verified fresh acquisition fact joins to this missing species.",
            "reference": (by_key.get((dex, "normal")) or {}).get("route") or f"reference.html?dex={dex}",
        })

    group_counts = {name: sum(1 for item in opportunities if item["group"] == name) for name in ("right_now", "ending_soon", "this_week", "later")}
    return {
        "schema_version": OPPORTUNITY_VERSION,
        "lab_version": LAB_VERSION,
        "build_id": manifest["build_id"],
        "as_of": as_of.isoformat().replace("+00:00", "Z"),
        "title": "Current Opportunity Finder",
        "fresh_snapshot_count": len(snapshots),
        "opportunity_count": len(opportunities),
        "groups": group_counts,
        "opportunities": opportunities,
        "no_verified_current_path": no_path,
        "ranking_contract": {
            "universal_rarity_score": False,
            "default_objective": "missing-first",
            "supported_objectives": ["missing-first", "roster-gaps", "owned-count"],
            "rule": "Objectives reorder inspectable dimensions only. Missing or stale source data never becomes evidence of availability.",
        },
        "storage": {"key": "pokemon-go-collection:opportunity-finder:v1", "schema_version": 1, "backup": "dedicated JSON export/import on the Opportunity Finder page"},
        "safety": {"fresh_only": True, "unknown_rate_is_not_zero": True, "restrictions_preserved": True, "automatic_account_action": False},
    }


def _owned_by_dex(collection: Mapping[str, Any]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {}
    for raw in collection.get("records") or []:
        dex = int(raw.get("pokemon_number") or 0)
        if dex:
            result.setdefault(dex, []).append(dict(raw))
    return result


def _record_ref(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str((record.get("identity") or {}).get("record_id") or record.get("record_id") or ""),
        "dex": int(record.get("pokemon_number") or 0),
        "name": record.get("name"), "form": record.get("form"), "cp": record.get("cp"), "moves": dict(record.get("moves") or {}),
    }


def _has_required_move(record: Mapping[str, Any], move: str) -> bool:
    moves = record.get("moves") or {}
    wanted = str(move).casefold()
    return any(str(moves.get(key) or "").casefold() == wanted for key in ("fast", "charged", "charged_second"))


def _source_map(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): dict(item) for item in registry.get("sources") or [] if item.get("id")}


def build_special_mechanics_lab(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    registry = _load(repository_root / "knowledge" / "special-mechanics.json", {}) or {}
    schema = _load(repository_root / "knowledge" / "special-mechanics.schema.json", {}) or {}
    Draft202012Validator(schema).validate(registry)
    collection = _load(output_dir / "data" / "pokemon.json", {}) or {}
    owned = _owned_by_dex(collection)
    sources = _source_map(registry)
    mechanics: list[dict[str, Any]] = []

    for raw in registry.get("mechanics") or []:
        kind = str(raw.get("kind") or "")
        evidence = [sources[source_id] for source_id in raw.get("source_ids") or [] if source_id in sources]
        if kind == "fusion":
            recipes = []
            for recipe in raw.get("recipes") or []:
                base_dex = int((recipe.get("base") or {}).get("dex") or 0)
                partner_dex = int((recipe.get("partner") or {}).get("dex") or 0)
                base_records = [_record_ref(item) for item in owned.get(base_dex, [])]
                partner_records = [_record_ref(item) for item in owned.get(partner_dex, [])]
                numeric_cost_known = (recipe.get("energy") or {}).get("amount") is not None and all(item.get("amount") is not None for item in recipe.get("candy") or [])
                recipes.append({
                    **dict(recipe),
                    "owned_prerequisites": {
                        "base": base_records, "partner": partner_records,
                        "base_owned": bool(base_records), "partner_owned": bool(partner_records),
                        "exact_owned_pair_available": bool(base_records and partner_records),
                    },
                    "resource_readiness": {
                        "state": "needs-local-balances-and-current-cost-verification",
                        "numeric_cost_fully_reviewed": numeric_cost_known,
                        "rule": "Ownership does not imply Candy or Fusion Energy balances. Unknown amounts must be verified in Pokémon GO before action.",
                    },
                    "local_state": "unknown-until-user-confirmed",
                })
            mechanics.append({
                "id": raw.get("id"), "kind": kind, "status": raw.get("status"), "rules": raw.get("rules") or {},
                "recipes": recipes, "evidence": evidence, "state_contract": raw.get("state_contract"),
            })
        elif kind == "adventure-effect":
            effects = []
            for effect in raw.get("effects") or []:
                dex = int((effect.get("pokemon") or {}).get("dex") or 0)
                candidates = []
                for record in owned.get(dex, []):
                    item = _record_ref(record)
                    item["required_move_owned"] = _has_required_move(record, str(effect.get("required_move") or ""))
                    candidates.append(item)
                effects.append({
                    **dict(effect),
                    "owned_candidates": candidates,
                    "usable_owned_record_ids": [item["record_id"] for item in candidates if item["required_move_owned"]],
                    "move_rule": "Required special move must already be present on the exact owned record. TM availability is never inferred.",
                })
            mechanics.append({
                "id": raw.get("id"), "kind": kind, "status": raw.get("status"), "rules": raw.get("rules") or {},
                "effects": effects, "unmodeled_official_examples": list(raw.get("unmodeled_official_examples") or []), "evidence": evidence,
            })

    return {
        "schema_version": SPECIAL_VERSION, "lab_version": LAB_VERSION, "build_id": manifest["build_id"], "title": "Special Mechanics Lab",
        "registry": {"path": "knowledge/special-mechanics.json", "dataset_version": registry.get("dataset_version"), "reviewed_at": registry.get("reviewed_at")},
        "mechanics": mechanics,
        "extension_contract": {
            "typed_mechanics_array": True,
            "supported_kinds": ["fusion", "adventure-effect"],
            "future_kind_rule": "Add a versioned typed entry and renderer; do not overload unrelated evolution/Mega/Max state.",
        },
        "storage": {
            "key": "pokemon-go-collection:special-mechanics:v1", "schema_version": 1, "unknown_is_explicit": True,
            "backup": "dedicated JSON export/import on the Special Mechanics Lab page",
        },
        "handoffs": {"decision_card": "index.html", "today": "today.html", "resource_optimizer": "tools.html#resource-optimizer", "move_lab": "move-lab.html"},
        "safety": {
            "local_special_state_inferred": False, "tm_learnability_inferred": False,
            "irreversible_or_resource_action_requires_review": True, "automatic_account_action": False,
        },
    }


def _schema(name: str, required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "$id": BASE_ID + name + ".schema.json",
        "type": "object", "required": required, "properties": properties, "additionalProperties": True,
    }


def schemas() -> dict[str, dict[str, Any]]:
    string = {"type": "string"}
    build = {"type": "string", "pattern": "^[0-9a-f]{12}$"}
    return {
        "opportunity-special-labs-index.schema.json": _schema(
            "opportunity-special-labs-index", ["schema_version", "build_id", "labs"],
            {"schema_version": string, "build_id": build, "labs": {"type": "object"}},
        ),
        "opportunity-finder.schema.json": _schema(
            "opportunity-finder", ["schema_version", "build_id", "opportunities", "no_verified_current_path", "ranking_contract"],
            {
                "schema_version": string, "build_id": build,
                "opportunities": {"type": "array", "items": {"type": "object"}},
                "no_verified_current_path": {"type": "array", "items": {"type": "object"}},
                "ranking_contract": {"type": "object"},
            },
        ),
        "special-mechanics-lab.schema.json": _schema(
            "special-mechanics-lab", ["schema_version", "build_id", "registry", "mechanics", "extension_contract"],
            {
                "schema_version": string, "build_id": build, "registry": {"type": "object"},
                "mechanics": {"type": "array", "items": {"type": "object"}}, "extension_contract": {"type": "object"},
            },
        ),
    }


def _register_contracts() -> None:
    mapping = {
        "data/opportunity-special-labs/index.json": "data/opportunity-special-labs-index.schema.json",
        "data/opportunity-finder.json": "data/opportunity-finder.schema.json",
        "data/special-mechanics-lab.json": "data/special-mechanics-lab.schema.json",
    }
    manifest_registry._SCHEMA_MAP.update(mapping)
    manifest_registry._STABLE_NAMES.update({
        "data/opportunity-special-labs/index.json": "opportunity_special_labs_index",
        "data/opportunity-finder.json": "opportunity_finder",
        "data/special-mechanics-lab.json": "special_mechanics_lab",
        "data/opportunity-special-labs-index.schema.json": "opportunity_special_labs_index_schema",
        "data/opportunity-finder.schema.json": "opportunity_finder_schema",
        "data/special-mechanics-lab.schema.json": "special_mechanics_lab_schema",
    })


def _page(output_dir: Path, filename: str, title: str, mount_id: str, description: str) -> None:
    html = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title><link rel="stylesheet" href="assets/opportunity-special-labs.css" data-opportunity-special-style></head>
<body><main class="opportunity-special-page"><header class="opportunity-special-header"><p><a href="today.html">Today</a> · <a href="tools.html">Tools</a> · <a href="index.html">Collection</a> · <a href="opportunity-finder.html">Opportunity Finder</a> · <a href="special-mechanics.html">Special Mechanics</a></p><h1>{title}</h1><p>{description}</p></header><div id="{mount_id}"><p role="status">Loading…</p></div></main><script defer src="assets/opportunity-special-labs.js" data-opportunity-special-script></script></body></html>"""
    (output_dir / filename).write_text(html, encoding="utf-8", newline="\n")


def _install_tools_links(output_dir: Path) -> None:
    path = output_dir / "tools.html"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    if 'id="opportunity-special-labs"' in source:
        return
    block = """\n    <section id="opportunity-special-labs" class="planner-card" aria-labelledby="opportunity-special-labs-heading">
      <header><div><p class="eyebrow">#145/#146</p><h2 id="opportunity-special-labs-heading">Current opportunities and special mechanics</h2></div></header>
      <p>Find acquisition paths only from fresh current-data snapshots, or review Fusion and Adventure Effects with exact owned prerequisites and explicit unknown resource state.</p>
      <p><a href="opportunity-finder.html">Open Opportunity Finder</a> · <a href="special-mechanics.html">Open Special Mechanics Lab</a></p>
    </section>\n"""
    marker = "  </main>"
    if marker not in source:
        raise ValueError("Generated tools page is missing its main closing tag")
    path.write_text(source.replace(marker, block + marker, 1), encoding="utf-8", newline="\n")


def publish(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    _register_contracts()
    opportunity = build_opportunity_finder(output_dir, manifest)
    special = build_special_mechanics_lab(repository_root, output_dir, manifest)
    _write(output_dir / "data" / "opportunity-finder.json", opportunity)
    _write(output_dir / "data" / "special-mechanics-lab.json", special)
    index = {
        "schema_version": LAB_VERSION, "build_id": manifest["build_id"],
        "labs": {
            "opportunity_finder": {"data": "data/opportunity-finder.json", "page": "opportunity-finder.html", "issue": 145},
            "special_mechanics": {"data": "data/special-mechanics-lab.json", "page": "special-mechanics.html", "issue": 146},
        },
        "safety": {
            "current_claim_requires_fresh_external_evidence": True,
            "unknown_resource_state_is_not_zero": True,
            "automatic_account_action": False,
        },
    }
    _write(output_dir / "data" / "opportunity-special-labs" / "index.json", index)
    for filename, schema in schemas().items():
        Draft202012Validator.check_schema(schema)
        _write(output_dir / "data" / filename, schema)

    _page(
        output_dir, "opportunity-finder.html", "Current Opportunity Finder", "opportunity-finder-root",
        "Fresh acquisition facts are joined to collection gaps and roster needs. Stale categories never appear as available now.",
    )
    _page(
        output_dir, "special-mechanics.html", "Special Mechanics Lab", "special-mechanics-root",
        "Review Fusion and Adventure Effects with exact owned prerequisites, source/version coverage, resource costs, and explicit unknown state.",
    )
    _install_tools_links(output_dir)

    llms_path = output_dir / "llms.txt"
    if llms_path.is_file():
        with llms_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "\nOpportunity and special-mechanics labs:\n"
                "- /data/opportunity-finder.json and /opportunity-finder.html consume only fresh acquisition snapshots; unknown rates and restrictions remain explicit and missing targets without a verified path are listed separately.\n"
                "- /data/special-mechanics-lab.json and /special-mechanics.html combine reviewed Fusion/Adventure Effect facts with exact owned records. Local special state and resource balances are never inferred.\n"
            )
    return index


__all__ = [
    "LAB_VERSION", "OPPORTUNITY_VERSION", "SPECIAL_VERSION",
    "build_opportunity_finder", "build_special_mechanics_lab", "publish", "schemas",
]
