"""Publish collection companion labs for naming, gaps, roster, evolution, and moves.

The #133-#137 layer composes canonical owned records, versioned static knowledge,
reviewed mechanics, and freshness-checked current snapshots. Unknown data remains
unknown, and no browser feature automates Pokémon GO account actions.
"""

from __future__ import annotations

import json
import math
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator

try:
    from . import manifest_registry
except ImportError:
    import manifest_registry

LAB_VERSION = "1.0.0"
NAMING_VERSION = "1.0.0"
GAP_VERSION = "1.0.0"
ROSTER_VERSION = "1.0.0"
EVOLUTION_VERSION = "1.0.0"
MOVE_VERSION = "1.0.0"
ROSTER_SCORING_VERSION = "1.0.0"
BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"
TYPES = (
    "normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison",
    "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy",
)
LEAGUE_CAPS = (("Little-style", 500), ("Great League", 1500), ("Ultra League", 2500))
CURRENT_MATCH_KEYS = {"dex", "pokemon_number", "boss_dex"}
CURRENT_MATCH_LIST_KEYS = {"featured_dex", "boss_dexes"}


def _load(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _record_id(record: Mapping[str, Any]) -> str:
    return str(record.get("identity", {}).get("record_id") or record.get("record_id") or "")


def _form_key(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if text in {"", "normal", "none", "ordinary"}:
        return "normal"
    aliases = {"alolan": "alola", "galarian": "galar", "hisuian": "hisui", "paldean": "paldea"}
    text = aliases.get(text, text)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "normal"


def _knowledge(repository_root: Path) -> dict[str, Any]:
    payload = _load(repository_root / "knowledge" / "pokemon-go.json", {}) or {}
    if not payload.get("entries"):
        raise ValueError("knowledge/pokemon-go.json is required for player labs")
    return payload


def _knowledge_maps(snapshot: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[tuple[int, str], list[dict[str, Any]]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_key: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for raw in snapshot.get("entries") or []:
        entry = dict(raw)
        species_id = str(entry.get("species_id") or "")
        if species_id:
            by_id[species_id] = entry
        if entry.get("dex") is not None:
            by_key[(int(entry["dex"]), _form_key(entry.get("form_key")))].append(entry)
    return by_id, by_key


def _match_entry(record: Mapping[str, Any], by_key: Mapping[tuple[int, str], list[dict[str, Any]]]) -> dict[str, Any] | None:
    key = (int(record.get("pokemon_number") or 0), _form_key(record.get("form")))
    exact = list(by_key.get(key) or [])
    if len(exact) == 1:
        return exact[0]
    if not exact and key[1] == "normal":
        normal = [item for item in by_key.get((key[0], "normal"), []) if item.get("transformation", {}).get("kind") is None]
        if len(normal) == 1:
            return normal[0]
    return None


def _fact_dexes(value: Any) -> set[int]:
    found: set[int] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in CURRENT_MATCH_KEYS and child not in (None, ""):
                try:
                    found.add(int(child))
                except (TypeError, ValueError):
                    pass
            elif key in CURRENT_MATCH_LIST_KEYS and isinstance(child, list):
                for item in child:
                    try:
                        found.add(int(item))
                    except (TypeError, ValueError):
                        pass
            else:
                found.update(_fact_dexes(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_fact_dexes(child))
    return found


def _compact_fact(value: Any, *, depth: int = 0) -> Any:
    if depth >= 3:
        return None
    if isinstance(value, Mapping):
        output = {}
        for key, child in value.items():
            compact = _compact_fact(child, depth=depth + 1)
            if compact not in (None, {}, []):
                output[str(key)] = compact
        return output
    if isinstance(value, list):
        return [_compact_fact(item, depth=depth + 1) for item in value[:20]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _fresh_current(output_dir: Path) -> dict[str, dict[str, Any]]:
    index = _load(output_dir / "data" / "external" / "index.json", {}) or {}
    result: dict[str, dict[str, Any]] = {}
    for item in index.get("snapshots") or []:
        category = str(item.get("data_category") or "")
        if not category or item.get("freshness", {}).get("state") != "fresh" or not item.get("path"):
            continue
        payload = _load(output_dir / str(item["path"]), {}) or {}
        if payload.get("freshness", {}).get("state") != "fresh":
            continue
        current = result.setdefault(category, {"snapshots": [], "facts_by_dex": defaultdict(list), "global_facts": []})
        current["snapshots"].append({
            "provider": item.get("provider"), "dataset_timestamp": item.get("dataset_timestamp"),
            "source_reference": item.get("source_reference"), "path": item.get("path"),
        })
        for fact in payload.get("facts") or []:
            compact = _compact_fact(fact)
            dexes = _fact_dexes(fact)
            evidence = {
                "fact": compact,
                "provider": item.get("provider"),
                "dataset_timestamp": item.get("dataset_timestamp"),
                "source_reference": item.get("source_reference"),
            }
            if dexes:
                for dex in dexes:
                    current["facts_by_dex"][dex].append(evidence)
            else:
                current["global_facts"].append(evidence)
    for value in result.values():
        value["facts_by_dex"] = {str(key): facts for key, facts in value["facts_by_dex"].items()}
    return result


def _external_for_dex(current: Mapping[str, Any], dex: int, categories: Iterable[str]) -> list[dict[str, Any]]:
    output = []
    for category in categories:
        value = current.get(category) or {}
        for evidence in value.get("facts_by_dex", {}).get(str(int(dex)), []) or []:
            output.append({"category": category, **dict(evidence)})
    return output


def _find_explicit_flag(value: Any, names: set[str]) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in names and child is True:
                return True
            if _find_explicit_flag(child, names):
                return True
    elif isinstance(value, list):
        return any(_find_explicit_flag(child, names) for child in value)
    return False


def _find_move_signal(value: Any) -> bool:
    keys = {
        "evolution_move", "exclusive_move", "evolution_move_available", "move_available_by_evolution",
        "elite_tm", "elite_tm_available", "ordinary_tm", "ordinary_tm_available", "move_availability",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in keys and child not in (None, "", False, [], {}):
                return True
            if _find_move_signal(child):
                return True
    elif isinstance(value, list):
        return any(_find_move_signal(child) for child in value)
    return False


def _record_compact(record: Mapping[str, Any], species_id: str | None) -> dict[str, Any]:
    return {
        "record_id": _record_id(record), "pokemon_number": record.get("pokemon_number"), "name": record.get("name"),
        "form": record.get("form"), "species_id": species_id, "cp": record.get("cp"), "hp": record.get("hp"),
        "ivs": record.get("ivs") or {}, "level": record.get("level") or {}, "moves": record.get("moves") or {},
        "status": record.get("status") or {}, "pvp": record.get("pvp") or {},
    }


def _naming_record(record: Mapping[str, Any], species_id: str | None) -> dict[str, Any]:
    compact = _record_compact(record, species_id)
    ivs = record.get("ivs") or {}
    pct = ivs.get("average_percent")
    total = ivs.get("total")
    compact["naming"] = {
        "iv45": f"{int(total):02d}" if isinstance(total, (int, float)) else "??",
        "ivpct3": f"{int(round(float(pct))):03d}" if isinstance(pct, (int, float)) else "???",
        "iv1000": f"{int(round(float(pct) * 10)):04d}" if isinstance(pct, (int, float)) else "????",
        "attack": ivs.get("attack"), "defense": ivs.get("defense"), "stamina": ivs.get("stamina"),
    }
    return compact


def build_naming_studio(records: list[dict[str, Any]], snapshot: Mapping[str, Any], by_key: Mapping[tuple[int, str], list[dict[str, Any]]], manifest: Mapping[str, Any]) -> dict[str, Any]:
    items = []
    for record in records:
        entry = _match_entry(record, by_key)
        items.append(_naming_record(record, str(entry.get("species_id")) if entry else None))
    presets = [
        {"id": "general", "name": "General", "template": "{iv45}-{state}"},
        {"id": "pvp", "name": "PvP", "template": "{great}{greatRank}"},
        {"id": "raid", "name": "Raid", "template": "{iv1000}{fast}"},
        {"id": "trade", "name": "Trade", "template": "{iv45}{review}"},
        {"id": "cleanup", "name": "Cleanup", "template": "{ivpct3}{state}"},
    ]
    return {
        "schema_version": NAMING_VERSION, "lab_version": LAB_VERSION, "build_id": manifest["build_id"],
        "knowledge": {"dataset_version": snapshot.get("dataset_version"), "source_commit": snapshot.get("source", {}).get("commit")},
        "character_limit": 12,
        "character_count_rule": "Count Unicode code points in the exact pasted output. Device rendering can differ; the site does not claim keyboard or in-game rename automation.",
        "fixed_width_contract": {
            "iv45": "00-45, width 2, lexical order equals numeric IV-total order",
            "ivpct3": "000-100, width 3, lexical order equals rounded whole-percent order",
            "iv1000": "0000-1000, width 4, lexical order preserves one decimal percentage without a percent sign",
        },
        "fields": {
            "iv45": "Total IV out of 45, fixed width", "ivpct3": "Rounded IV percent, fixed width", "iv1000": "IV percent x10, fixed width",
            "atk": "Attack IV", "def": "Defense IV", "hp": "Stamina IV", "great": "Great League percentile", "greatRank": "Great League rank",
            "ultra": "Ultra League percentile", "ultraRank": "Ultra League rank", "level": "Known level/range", "fast": "Fast move abbreviation",
            "charged": "Charged move abbreviation", "state": "Shadow/Purified marker", "max": "Browser-local explicit Max marker", "review": "Browser-local keep/trade review marker", "legacy": "Browser-local legacy-move review marker",
        },
        "verified_symbol_palette": {
            "scope": "conservative ASCII palette verified by browser text handling; user device paste testing remains authoritative",
            "symbols": ["-", ".", "+", "_"],
            "decorative_unicode_assumed_compatible": False,
        },
        "default_presets": presets,
        "storage": {"key": "pokemon-go-collection:naming-presets:v1", "schema_version": 1, "unified_backup": True},
        "workflow": {"copy_only": True, "account_access": False, "keyboard_extension": False, "batch_renaming": False, "action_pack_handoff": "action-packs.html"},
        "records": items,
    }


def _base_entries(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(entry) for entry in snapshot.get("entries") or []
        if entry.get("released") is True and entry.get("transformation", {}).get("kind") is None
    ]


def build_gap_radar(records: list[dict[str, Any]], snapshot: Mapping[str, Any], by_key: Mapping[tuple[int, str], list[dict[str, Any]]], current: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    base = _base_entries(snapshot)
    owned_by_dex: dict[int, list[dict[str, Any]]] = defaultdict(list)
    owned_by_key: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    owned_family: dict[str, list[str]] = defaultdict(list)
    for record in records:
        dex = int(record.get("pokemon_number") or 0)
        owned_by_dex[dex].append(record)
        owned_by_key[(dex, _form_key(record.get("form")))].append(record)
        entry = _match_entry(record, by_key)
        family_id = str((entry or {}).get("family", {}).get("id") or "")
        if family_id and _record_id(record):
            owned_family[family_id].append(_record_id(record))

    species_entries: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for entry in base:
        species_entries[int(entry["dex"])].append(entry)
    gaps = []
    for dex, entries in sorted(species_entries.items()):
        normal = next((item for item in entries if _form_key(item.get("form_key")) == "normal"), entries[0])
        family_id = str(normal.get("family", {}).get("id") or "")
        owned = owned_by_dex.get(dex, [])
        opportunities = _external_for_dex(current, dex, ("events", "raids", "research", "eggs"))
        gaps.append({
            "dex": dex, "name": normal.get("base_name") or normal.get("display_name"), "species_id": normal.get("species_id"),
            "species_state": "yes" if owned else "missing", "owned_record_ids": [_record_id(item) for item in owned if _record_id(item)],
            "family_id": family_id or None, "family_fill_record_ids": owned_family.get(family_id, []) if family_id else [],
            "current_opportunities": opportunities, "actionable_now": bool(opportunities or (family_id and owned_family.get(family_id))),
            "links": {"reference": f"reference.html?dex={dex}", "evolution": f"evolution-lab.html?dex={dex}", "trade": f"action-packs.html?pack=trade-review&dex={dex}"},
        })

    forms = []
    for entry in sorted(base, key=lambda item: (int(item["dex"]), str(item.get("form_key")))):
        key = (int(entry["dex"]), _form_key(entry.get("form_key")))
        owned = owned_by_key.get(key, [])
        forms.append({
            "dex": entry["dex"], "species_id": entry.get("species_id"), "name": entry.get("display_name"), "form_key": key[1],
            "state": "yes" if owned else "missing", "owned_record_ids": [_record_id(item) for item in owned if _record_id(item)],
        })

    family_ids = sorted({str(entry.get("family", {}).get("id")) for entry in base if entry.get("family", {}).get("id")})
    families = [{"family_id": value, "state": "yes" if owned_family.get(value) else "missing", "owned_record_ids": owned_family.get(value, [])} for value in family_ids]
    species_owned = sum(1 for item in gaps if item["species_state"] == "yes")
    forms_owned = sum(1 for item in forms if item["state"] == "yes")
    families_owned = sum(1 for item in families if item["state"] == "yes")
    return {
        "schema_version": GAP_VERSION, "lab_version": LAB_VERSION, "build_id": manifest["build_id"],
        "denominators": {
            "knowledge_dataset_version": snapshot.get("dataset_version"), "source_commit": snapshot.get("source", {}).get("commit"),
            "species": len(gaps), "forms": len(forms), "families": len(families),
            "exclusions": ["unreleased knowledge entries", "Mega/Primal and other transformation entries", "attributes whose local state is unsupported or unknown"],
        },
        "completion": {"species": {"yes": species_owned, "total": len(gaps)}, "forms": {"yes": forms_owned, "total": len(forms)}, "families": {"yes": families_owned, "total": len(families)}},
        "attribute_support": {
            "lucky": "canonical-owned", "hundo": "canonical-owned", "nundo": "canonical-owned", "pvp_candidate": "canonical-owned",
            "shiny": "browser-local-explicit-only", "costume": "browser-local-explicit-only", "background": "browser-local-explicit-only",
            "dynamax": "browser-local-explicit-only", "gigantamax": "browser-local-explicit-only",
            "mega_primal_capability": "versioned-static-knowledge-only; capability is not current transformed state",
        },
        "unknown_policy": "Unknown local attributes remain unknown and never count as no or missing.",
        "storage": {"key": "pokemon-go-collection:gap-goals:v1", "schema_version": 1, "unified_backup": True},
        "species": gaps, "forms": forms, "families": families,
    }


def _level_value(record: Mapping[str, Any]) -> tuple[float | None, bool]:
    level = record.get("level") or {}
    low, high = level.get("minimum"), level.get("maximum")
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        return (float(low) + float(high)) / 2, float(low) == float(high)
    if isinstance(low, (int, float)):
        return float(low), False
    if isinstance(high, (int, float)):
        return float(high), False
    return None, False


def _roster_score(record: Mapping[str, Any]) -> dict[str, Any]:
    components: list[tuple[str, float, float]] = []
    cp = record.get("cp")
    if isinstance(cp, (int, float)) and cp > 0:
        components.append(("cp", min(float(cp) / 5000.0, 1.0), 50.0))
    iv = (record.get("ivs") or {}).get("average_percent")
    if isinstance(iv, (int, float)):
        components.append(("ivs", max(0.0, min(float(iv) / 100.0, 1.0)), 20.0))
    level, exact_level = _level_value(record)
    if level is not None:
        components.append(("level", max(0.0, min(level / 50.0, 1.0)), 15.0))
    moves = record.get("moves") or {}
    known_moves = sum(1 for key in ("fast", "charged") if moves.get(key))
    if known_moves:
        components.append(("moves", known_moves / 2.0, 15.0))
    total_weight = sum(weight for _, _, weight in components)
    score = 100.0 * sum(value * weight for _, value, weight in components) / total_weight if total_weight else None
    confidence = 1.0
    missing = []
    if not isinstance(iv, (int, float)):
        confidence -= 0.20; missing.append("IV percentage")
    if level is None:
        confidence -= 0.20; missing.append("level")
    elif not exact_level:
        confidence -= 0.05; missing.append("exact level")
    if known_moves < 2:
        confidence -= 0.25; missing.append("complete moveset")
    confidence = max(0.0, confidence)
    label = "high" if confidence >= 0.80 else "medium" if confidence >= 0.55 else "low"
    return {
        "score": round(score, 2) if score is not None else None, "confidence": round(confidence, 2), "confidence_label": label,
        "missing": missing, "components": {name: round(value, 4) for name, value, _ in components},
    }


def _known_improvement_cost(record_id: str, investments: Mapping[str, Any]) -> dict[str, Any] | None:
    item = investments.get(record_id) or {}
    builds = (item.get("derived") or {}).get("pvp_builds") or []
    known = [build for build in builds if build.get("stardust_cost") is not None and build.get("regular_candy_cost") is not None]
    if not known:
        return None
    cheapest = min(known, key=lambda item: (int(item["stardust_cost"]), int(item["regular_candy_cost"]), str(item.get("league"))))
    return {
        "stardust": int(cheapest["stardust_cost"]), "regular_candy": int(cheapest["regular_candy_cost"]),
        "scope": f"Poke Genie exported {cheapest.get('league')} target-build cost only; not a raid power-up estimate",
    }


def build_roster_readiness(records: list[dict[str, Any]], by_key: Mapping[tuple[int, str], list[dict[str, Any]]], current: Mapping[str, Any], investments_payload: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    investments = {str(item.get("record_id")): item for item in investments_payload.get("records") or [] if item.get("record_id")}
    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in TYPES}
    for record in records:
        entry = _match_entry(record, by_key)
        if not entry:
            continue
        assessment = _roster_score(record)
        candidate = {
            "record_id": _record_id(record), "name": record.get("name"), "form": record.get("form"), "cp": record.get("cp"),
            "score": assessment["score"], "confidence": assessment["confidence"], "confidence_label": assessment["confidence_label"],
            "missing": assessment["missing"], "components": assessment["components"], "status": (record.get("status") or {}).get("shadow_purified"),
            "improvement_cost": _known_improvement_cost(_record_id(record), investments),
        }
        for attack_type in entry.get("types") or []:
            key = str(attack_type).casefold()
            if key in buckets:
                buckets[key].append(candidate)
    matrix = []
    for attack_type in TYPES:
        candidates = sorted(buckets[attack_type], key=lambda item: (-(item["score"] if item["score"] is not None else -1), -item["confidence"], item["record_id"]))
        top = candidates[:6]
        scores = [item["score"] for item in candidates if item["score"] is not None]
        best = max(scores) if scores else None
        matrix.append({
            "type": attack_type, "best_score": best, "viable_count": sum(1 for value in scores if value >= 65), "strong_count": sum(1 for value in scores if value >= 80),
            "confidence": top[0]["confidence_label"] if top else "unavailable", "candidates": top,
            "text_summary": f"{attack_type.title()}: best deterministic owned score {best if best is not None else 'unavailable'}; {sum(1 for value in scores if value >= 65)} at or above the documented usable threshold.",
        })
    weakest = sorted(matrix, key=lambda item: ((item["best_score"] if item["best_score"] is not None else -1), item["viable_count"], item["type"]))[:3]
    fresh_matchups = any((current.get(category) or {}).get("snapshots") for category in ("raids", "max-battles", "rocket"))
    return {
        "schema_version": ROSTER_VERSION, "lab_version": LAB_VERSION, "scoring_version": ROSTER_SCORING_VERSION, "build_id": manifest["build_id"],
        "scoring": {
            "formula": "Weighted mean of known components only: CP 50%, IV 20%, level 15%, move completeness 15%. Missing components are not zero; they reduce confidence.",
            "cp_normalization": "min(CP/5000, 1)", "iv_normalization": "IV percent/100", "level_normalization": "level/50", "moves": "0.5 for one known attacking move, 1.0 for both",
            "thresholds": {"usable": 65, "strong": 80}, "not_a_simulation": True,
        },
        "current_matchup_layer": {
            "state": "fresh-data-present-but-no-supported-simulation" if fresh_matchups else "unavailable",
            "overlay_applied": False, "reason": "A static type score is not a raid/Max/Rocket simulation. No supported matchup simulator is wired into this lab.",
        },
        "max_roster": {"state": "browser-local-explicit-only", "reason": "Max eligibility/state is not inferred from ordinary owned records. Explicit local Dynamax/Gigantamax enrichment is shown separately in the browser."},
        "storage": {"key": "pokemon-go-collection:roster-locks:v1", "schema_version": 1, "unified_backup": True},
        "weakest": [{"type": item["type"], "best_score": item["best_score"], "viable_count": item["viable_count"]} for item in weakest],
        "types": matrix,
    }


def _cpm_for_level(mechanics: Mapping[str, Any], level: float) -> float | None:
    values = mechanics.get("cp_multiplier_levels")
    if isinstance(values, Mapping):
        for key in (str(level), f"{level:.1f}", str(int(level)) if level.is_integer() else ""):
            if key and isinstance(values.get(key), (int, float)):
                return float(values[key])
    if isinstance(values, list):
        for item in values:
            if isinstance(item, Mapping) and float(item.get("level", -1)) == float(level) and isinstance(item.get("cpm"), (int, float)):
                return float(item["cpm"])
            if isinstance(item, (list, tuple)) and len(item) >= 2 and float(item[0]) == float(level):
                return float(item[1])
    return None


def project_cp(record: Mapping[str, Any], target: Mapping[str, Any], mechanics: Mapping[str, Any]) -> dict[str, Any]:
    ivs = record.get("ivs") or {}
    if not all(isinstance(ivs.get(key), (int, float)) for key in ("attack", "defense", "stamina")):
        return {"state": "blocked", "reason": "exact IVs required"}
    level, exact = _level_value(record)
    if level is None or not exact:
        return {"state": "blocked", "reason": "exact level required"}
    cpm = _cpm_for_level(mechanics, level)
    stats = target.get("base_stats") or {}
    if cpm is None or not all(isinstance(stats.get(key), (int, float)) for key in ("attack", "defense", "stamina")):
        return {"state": "blocked", "reason": "CP multiplier/base stats unavailable"}
    attack = float(stats["attack"]) + float(ivs["attack"])
    defense = float(stats["defense"]) + float(ivs["defense"])
    stamina = float(stats["stamina"]) + float(ivs["stamina"])
    cp = max(10, math.floor(attack * math.sqrt(defense) * math.sqrt(stamina) * cpm * cpm / 10.0))
    return {
        "state": "projected", "cp": cp, "assumptions": ["same level after evolution", "same IVs after evolution", "pinned CP multiplier/base stats"],
        "league_cap_warnings": [f"Projected CP {cp} exceeds {label} cap {cap}." for label, cap in LEAGUE_CAPS if cp > cap],
        "eligibility_note": "CP cap comparison is not proof of species/cup eligibility.",
    }


def _requirements(entry: Mapping[str, Any]) -> dict[str, Any]:
    family = entry.get("family") or {}
    candy = family.get("evolution_candy_cost")
    special = family.get("special_requirements")
    known = candy is not None and special is not None
    return {
        "state": "known" if known else "unknown", "candy": candy, "special": special,
        "blocker": None if known else "Pinned knowledge does not provide complete evolution Candy/special requirements, so a definitive evolve-now recommendation is blocked.",
    }


def _exclusive_window(current: Mapping[str, Any], dex: int) -> dict[str, Any]:
    evidence = _external_for_dex(current, dex, ("moves", "events"))
    explicit = [item for item in evidence if _find_move_signal(item.get("fact"))]
    return {
        "state": "fresh-explicit" if explicit else "unavailable-or-unspecified",
        "evidence": explicit,
        "current_claim_allowed": bool(explicit),
        "reason": None if explicit else "Stable move pools do not prove a current evolution/exclusive-move window.",
    }


def build_evolution_lab(records: list[dict[str, Any]], snapshot: Mapping[str, Any], by_id: Mapping[str, dict[str, Any]], by_key: Mapping[tuple[int, str], list[dict[str, Any]]], current: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    catalog: dict[str, dict[str, Any]] = {}
    items = []
    mechanics = snapshot.get("mechanics") or {}
    for record in records:
        entry = _match_entry(record, by_key)
        if not entry:
            items.append({"record_id": _record_id(record), "state": "blocked", "reason": "No unique static species/form knowledge match."})
            continue
        species_id = str(entry.get("species_id"))
        requirements = _requirements(entry)
        branches = []
        for target_id in entry.get("family", {}).get("evolution_species_ids") or []:
            target = by_id.get(str(target_id))
            if not target:
                branches.append({"species_id": str(target_id), "state": "unknown-target"})
                continue
            projection = project_cp(record, target, mechanics)
            branches.append({
                "species_id": target.get("species_id"), "name": target.get("display_name"), "form_key": target.get("form_key"),
                "requirements": requirements, "cp_projection": projection, "reference": f"reference.html?dex={target.get('dex')}",
            })
        window = _exclusive_window(current, int(record.get("pokemon_number") or 0))
        decision = "not-applicable" if not branches else "review"
        reasons = []
        if branches and requirements["state"] != "known":
            reasons.append(requirements["blocker"])
        elif branches and window["state"] == "fresh-explicit":
            decision = "evolve-now-window-present"
            reasons.append("A fresh external snapshot explicitly carries an evolution/move availability signal. Verify the exact target and requirements before spending Candy/items.")
        elif branches:
            decision = "either-or-wait"
            reasons.append("No fresh exclusive-move window requires immediate action from the available evidence.")
        restriction = {
            "gigantamax_local_state": "requires-explicit-reviewed-no-evolve-rule",
            "official_no_evolve_rule": False,
            "reason": "Do not infer an evolution restriction from Gigantamax state alone. Block only when the reviewed mechanics registry explicitly publishes a no-evolve rule for the affected Max state.",
        }
        catalog[species_id] = {
            "species_id": species_id, "name": entry.get("display_name"), "family": entry.get("family"),
            "knowledge_dataset_version": snapshot.get("dataset_version"), "source_commit": snapshot.get("source", {}).get("commit"),
        }
        items.append({
            "record_id": _record_id(record), "pokemon_number": record.get("pokemon_number"), "name": record.get("name"), "form": record.get("form"),
            "species_id": species_id, "state": "available" if branches else "no-supported-branch", "branches": branches,
            "current_exclusive_move_window": window, "decision": {"state": decision, "definitive": decision == "evolve-now-window-present" and requirements["state"] == "known", "reasons": reasons},
            "irreversible": True, "restriction_policy": restriction,
            "links": {"decision_card": f"index.html?record={_record_id(record)}", "gap_radar": f"gap-radar.html?dex={record.get('pokemon_number')}", "action_pack": f"action-packs.html?pack=evolution-review&record={_record_id(record)}"},
        })
    return {
        "schema_version": EVOLUTION_VERSION, "lab_version": LAB_VERSION, "build_id": manifest["build_id"],
        "knowledge": {"dataset_version": snapshot.get("dataset_version"), "source_commit": snapshot.get("source", {}).get("commit"), "coverage": snapshot.get("coverage", {}).get("evolution_candy_and_special_requirements")},
        "current_window_contract": "Only fresh external move/event facts with an explicit evolution/exclusive-move signal may create a current window claim.",
        "records": items, "species_catalog": catalog,
    }


def _frustration_window(current: Mapping[str, Any], dex: int) -> dict[str, Any]:
    names = {"frustration_removal", "frustration_removal_available", "remove_frustration"}
    explicit = []
    for category in ("moves", "events"):
        value = current.get(category) or {}
        for evidence in value.get("facts_by_dex", {}).get(str(dex), []) or []:
            if _find_explicit_flag(evidence.get("fact"), names):
                explicit.append({"category": category, **dict(evidence)})
        for evidence in value.get("global_facts", []) or []:
            if _find_explicit_flag(evidence.get("fact"), names):
                explicit.append({"category": category, **dict(evidence)})
    return {
        "state": "fresh-verified" if explicit else "unavailable-or-unverified", "current_removal_allowed": bool(explicit), "evidence": explicit,
        "reason": None if explicit else "No fresh reviewed move/event fact explicitly confirms a current Frustration-removal window.",
    }


def _move_current_evidence(current: Mapping[str, Any], dex: int) -> list[dict[str, Any]]:
    return [item for item in _external_for_dex(current, dex, ("moves", "events")) if _find_move_signal(item.get("fact"))]


def build_move_lab(records: list[dict[str, Any]], snapshot: Mapping[str, Any], by_key: Mapping[tuple[int, str], list[dict[str, Any]]], current: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    species_catalog: dict[str, dict[str, Any]] = {}
    items = []
    by_species_owned: dict[str, list[str]] = defaultdict(list)
    matched: dict[str, dict[str, Any]] = {}
    for record in records:
        entry = _match_entry(record, by_key)
        if entry:
            species_id = str(entry.get("species_id"))
            matched[_record_id(record)] = entry
            by_species_owned[species_id].append(_record_id(record))
    for record in records:
        record_id = _record_id(record)
        entry = matched.get(record_id)
        if not entry:
            items.append({"record_id": record_id, "state": "blocked", "reason": "No unique static species/form knowledge match."})
            continue
        species_id = str(entry.get("species_id"))
        pool = entry.get("moves") or {}
        current_evidence = _move_current_evidence(current, int(record.get("pokemon_number") or 0))
        moves = record.get("moves") or {}
        is_shadow = (record.get("status") or {}).get("shadow_purified") == "shadow"
        has_frustration = any(str(moves.get(key) or "").casefold() == "frustration" for key in ("charged", "charged_second"))
        frustration = _frustration_window(current, int(record.get("pokemon_number") or 0)) if is_shadow and has_frustration else {"state": "not-applicable", "current_removal_allowed": False, "evidence": []}
        alternatives = [value for value in by_species_owned.get(species_id, []) if value != record_id]
        species_catalog[species_id] = {
            "species_id": species_id, "name": entry.get("display_name"), "stable_move_pool": pool,
            "provenance": {"dataset_version": snapshot.get("dataset_version"), "source_commit": snapshot.get("source", {}).get("commit"), "classification": snapshot.get("classification")},
            "current_availability": "not implied by stable move pool",
        }
        items.append({
            "record_id": record_id, "pokemon_number": record.get("pokemon_number"), "name": record.get("name"), "form": record.get("form"), "species_id": species_id,
            "known_moves": {"fast": moves.get("fast"), "charged": moves.get("charged"), "charged_second": moves.get("charged_second"), "second_move_known": moves.get("charged_second") is not None},
            "stable_move_pool": pool, "stable_pool_is_current_acquisition_proof": False,
            "current_acquisition": {"state": "fresh-explicit" if current_evidence else "unavailable-or-unspecified", "evidence": current_evidence, "ordinary_tm_vs_elite_tm": "Only explicit fresh evidence may classify current acquisition."},
            "frustration": frustration,
            "purification": {
                "suggested_to_remove_frustration": False,
                "permanent_tradeoff": "Purification permanently changes Shadow state and must not be recommended merely as a Frustration workaround.",
            },
            "elite_tm": {
                "spend_recommendation": "blocked-until-desired-move-and-current-acquisition-are-reviewed",
                "opportunity_cost": "Elite TM is a scarce irreversible resource choice. Compare current availability and owned alternatives first.",
                "owned_alternative_record_ids": alternatives,
            },
            "action_pack": f"action-packs.html?pack=move-review&record={record_id}",
        })
    return {
        "schema_version": MOVE_VERSION, "lab_version": LAB_VERSION, "build_id": manifest["build_id"],
        "knowledge": {"dataset_version": snapshot.get("dataset_version"), "source_commit": snapshot.get("source", {}).get("commit"), "move_pool_scope": snapshot.get("coverage", {}).get("move_pools")},
        "current_contract": "Stable learnable pools and fresh acquisition availability are separate. No current TM, event, Frustration, or relevance claim is inferred from a static pool.",
        "storage": {"key": "pokemon-go-collection:elite-tm-vault:v1", "schema_version": 1, "unified_backup": True, "count_inferred": False},
        "records": items, "species_catalog": species_catalog,
    }


def _schema(name: str, required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": BASE_ID + name + ".schema.json", "type": "object", "required": required, "properties": properties, "additionalProperties": True}


def schemas() -> dict[str, dict[str, Any]]:
    string = {"type": "string"}
    build = {"type": "string", "pattern": "^[0-9a-f]{12}$"}
    records = {"type": "array", "items": {"type": "object"}}
    return {
        "player-labs-index.schema.json": _schema("player-labs-index", ["schema_version", "build_id", "labs"], {"schema_version": string, "build_id": build, "labs": {"type": "object"}}),
        "naming-studio.schema.json": _schema("naming-studio", ["schema_version", "build_id", "fixed_width_contract", "records"], {"schema_version": string, "build_id": build, "fixed_width_contract": {"type": "object"}, "records": records}),
        "gap-radar.schema.json": _schema("gap-radar", ["schema_version", "build_id", "denominators", "unknown_policy", "species"], {"schema_version": string, "build_id": build, "denominators": {"type": "object"}, "unknown_policy": string, "species": records}),
        "roster-readiness.schema.json": _schema("roster-readiness", ["schema_version", "build_id", "scoring", "types"], {"schema_version": string, "build_id": build, "scoring": {"type": "object"}, "types": records}),
        "evolution-lab.schema.json": _schema("evolution-lab", ["schema_version", "build_id", "current_window_contract", "records"], {"schema_version": string, "build_id": build, "current_window_contract": string, "records": records}),
        "move-lab.schema.json": _schema("move-lab", ["schema_version", "build_id", "current_contract", "records"], {"schema_version": string, "build_id": build, "current_contract": string, "records": records}),
    }


def _register_contracts() -> None:
    mapping = {
        "data/player-labs/index.json": "data/player-labs-index.schema.json",
        "data/naming-studio.json": "data/naming-studio.schema.json",
        "data/gap-radar.json": "data/gap-radar.schema.json",
        "data/roster-readiness.json": "data/roster-readiness.schema.json",
        "data/evolution-lab.json": "data/evolution-lab.schema.json",
        "data/move-lab.json": "data/move-lab.schema.json",
    }
    manifest_registry._SCHEMA_MAP.update(mapping)
    stable = {
        "data/player-labs/index.json": "player_labs_index", "data/naming-studio.json": "naming_studio",
        "data/gap-radar.json": "gap_radar", "data/roster-readiness.json": "roster_readiness",
        "data/evolution-lab.json": "evolution_lab", "data/move-lab.json": "move_lab",
    }
    for resource, schema in mapping.items():
        stable[schema] = Path(schema).name.removesuffix(".json").replace("-", "_")
    manifest_registry._STABLE_NAMES.update(stable)


def _page(output_dir: Path, filename: str, title: str, mount_id: str, description: str) -> None:
    html = f'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title><link rel="stylesheet" href="assets/player-labs.css" data-player-labs-style></head>
<body><main class="product-page lab-page"><header class="product-page-header ds-card"><p><a href="today.html">Today</a> · <a href="index.html">Collection</a> · <a href="naming-studio.html">Naming</a> · <a href="gap-radar.html">Gaps</a> · <a href="roster-readiness.html">Roster</a> · <a href="evolution-lab.html">Evolution</a> · <a href="move-lab.html">Moves</a> · <a href="action-packs.html">Action Packs</a></p><h1>{title}</h1><p>{description}</p></header><div id="{mount_id}"><p class="ds-empty">Loading…</p></div></main><script defer src="assets/player-labs.js" data-player-labs-script></script></body></html>'''
    (output_dir / filename).write_text(html, encoding="utf-8", newline="\n")


def _install_tools_bridge(output_dir: Path) -> None:
    path = output_dir / "tools.html"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    if "data-player-labs-script" not in source:
        source = source.replace("</body>", '<script defer src="assets/player-labs.js" data-player-labs-script></script></body>', 1)
    path.write_text(source, encoding="utf-8", newline="\n")


def publish(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    _register_contracts()
    snapshot = _knowledge(repository_root)
    by_id, by_key = _knowledge_maps(snapshot)
    pokemon = _load(output_dir / "data" / "pokemon.json", {}) or {}
    records = [dict(item) for item in pokemon.get("records") or []]
    current = _fresh_current(output_dir)
    investments = _load(output_dir / "data" / "investments" / "records.json", {}) or {}

    naming = build_naming_studio(records, snapshot, by_key, manifest)
    gaps = build_gap_radar(records, snapshot, by_key, current, manifest)
    roster = build_roster_readiness(records, by_key, current, investments, manifest)
    evolution = build_evolution_lab(records, snapshot, by_id, by_key, current, manifest)
    moves = build_move_lab(records, snapshot, by_key, current, manifest)
    resources = {
        "naming": ("data/naming-studio.json", naming, "naming-studio.html"),
        "gaps": ("data/gap-radar.json", gaps, "gap-radar.html"),
        "roster": ("data/roster-readiness.json", roster, "roster-readiness.html"),
        "evolution": ("data/evolution-lab.json", evolution, "evolution-lab.html"),
        "moves": ("data/move-lab.json", moves, "move-lab.html"),
    }
    for _, (path, payload, _) in resources.items():
        _write(output_dir / path, payload)
    index = {
        "schema_version": LAB_VERSION, "build_id": manifest["build_id"],
        "labs": {name: {"data": path, "page": page} for name, (path, _, page) in resources.items()},
        "safety": {"account_access": False, "in_game_automation": False, "current_claim_requires_fresh_external_evidence": True, "unknown_is_not_false": True},
    }
    _write(output_dir / "data" / "player-labs" / "index.json", index)
    for filename, schema in schemas().items():
        Draft202012Validator.check_schema(schema)
        _write(output_dir / "data" / filename, schema)

    assets = output_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repository_root / "site" / "player-labs.js", assets / "player-labs.js")
    shutil.copyfile(repository_root / "site" / "player-labs.css", assets / "player-labs.css")
    _page(output_dir, "naming-studio.html", "Naming Studio", "naming-studio-root", "Build exact-record nickname previews and copy them manually into Pokémon GO. No keyboard or account automation is used.")
    _page(output_dir, "gap-radar.html", "Collection Gap Radar", "gap-radar-root", "See versioned Living Dex and form gaps without treating unknown collector attributes as missing.")
    _page(output_dir, "roster-readiness.html", "Roster Readiness", "roster-readiness-root", "Review deterministic 18-type owned-roster coverage. Scores are not raid-boss simulations.")
    _page(output_dir, "evolution-lab.html", "Evolution Lab", "evolution-lab-root", "Compare supported evolution branches, projections, blockers, and fresh move-window evidence before irreversible evolution.")
    _page(output_dir, "move-lab.html", "Move Lab", "move-lab-root", "Separate stable move pools from current acquisition evidence and review Elite TM or Frustration decisions safely.")
    _install_tools_bridge(output_dir)
    return index


__all__ = [
    "LAB_VERSION", "TYPES", "project_cp", "build_naming_studio", "build_gap_radar", "build_roster_readiness",
    "build_evolution_lab", "build_move_lab", "schemas", "publish",
]
