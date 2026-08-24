"""Publish advanced current-game and battle planning labs for issues #138-#142.

This layer composes exact owned records, versioned static knowledge, reviewed mechanics,
and freshness-checked rotating facts. Browser-local state is explicitly separate from
canonical Poke Genie facts. Current-event and current-boss claims fail closed.
"""

from __future__ import annotations

import json
import math
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator

try:
    from . import manifest_registry, player_labs
except ImportError:
    import manifest_registry
    import player_labs

ADVANCED_VERSION = "1.0.0"
MEGA_VERSION = "1.0.0"
MAX_VERSION = "1.0.0"
HYPER_VERSION = "1.0.0"
BUDDY_VERSION = "1.0.0"
RAID_VERSION = "1.0.0"
RAID_MODEL_VERSION = "1.0.0"
BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"
LEAGUE_CAPS = (("Little-style", 500), ("Great League", 1500), ("Ultra League", 2500))


def _load(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _record_id(record: Mapping[str, Any]) -> str:
    return str(record.get("identity", {}).get("record_id") or record.get("record_id") or "")


def _mechanics_domains(output_dir: Path) -> dict[str, dict[str, Any]]:
    payload = _load(output_dir / "data" / "mechanics" / "index.json", {}) or {}
    return {str(item.get("id")): dict(item) for item in payload.get("domains") or [] if item.get("id")}


def _fresh_snapshot_payloads(output_dir: Path, categories: Iterable[str]) -> list[dict[str, Any]]:
    wanted = set(categories)
    index = _load(output_dir / "data" / "external" / "index.json", {}) or {}
    output = []
    for item in index.get("snapshots") or []:
        if item.get("data_category") not in wanted or item.get("freshness", {}).get("state") != "fresh":
            continue
        path = item.get("path")
        if not path:
            continue
        payload = _load(output_dir / str(path), {}) or {}
        if payload.get("freshness", {}).get("state") != "fresh":
            continue
        output.append({"index": dict(item), "payload": payload})
    return output


def _snapshot_states(output_dir: Path, category: str) -> list[str]:
    index = _load(output_dir / "data" / "external" / "index.json", {}) or {}
    return sorted(
        {
            str(item.get("freshness", {}).get("state") or "unavailable")
            for item in index.get("snapshots") or []
            if item.get("data_category") == category
        }
    )


def _walk_bosses(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        bosses = value.get("bosses")
        if isinstance(bosses, list):
            for boss in bosses:
                if isinstance(boss, Mapping) and boss.get("dex") is not None:
                    result.append(dict(boss))
        for key, child in value.items():
            if key != "bosses":
                result.extend(_walk_bosses(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(_walk_bosses(child))
    return result


def _entry_for_dex(
    dex: int,
    by_key: Mapping[tuple[int, str], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    entries = list(by_key.get((int(dex), "normal")) or [])
    base = [item for item in entries if item.get("transformation", {}).get("kind") is None]
    if len(base) == 1:
        return base[0]
    if len(entries) == 1:
        return entries[0]
    return None


def _record_summary(record: Mapping[str, Any], entry: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "record_id": _record_id(record),
        "pokemon_number": record.get("pokemon_number"),
        "name": record.get("name"),
        "form": record.get("form"),
        "species_id": (entry or {}).get("species_id"),
        "cp": record.get("cp"),
        "hp": record.get("hp"),
        "ivs": record.get("ivs") or {},
        "level": record.get("level") or {},
        "moves": record.get("moves") or {},
        "status": record.get("status") or {},
    }


def _reviewed_domain(domains: Mapping[str, dict[str, Any]], domain_id: str) -> dict[str, Any]:
    domain = dict(domains.get(domain_id) or {})
    return {
        "id": domain_id,
        "status": domain.get("status", "unsupported"),
        "applicable_at": domain.get("applicable_at"),
        "facts": domain.get("normalized_facts") or [],
        "source_ids": domain.get("source_ids") or [],
    }


def _transformation_targets(entry: Mapping[str, Any], by_id: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    targets = []
    for species_id in entry.get("transformations") or []:
        target = by_id.get(str(species_id))
        if not target:
            continue
        targets.append(
            {
                "species_id": target.get("species_id"),
                "name": target.get("display_name"),
                "kind": target.get("transformation", {}).get("kind"),
                "types": target.get("types") or [],
                "base_stats": target.get("base_stats") or {},
            }
        )
    return targets


def _current_featured_types(
    output_dir: Path,
    by_key: Mapping[tuple[int, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    snapshots = _fresh_snapshot_payloads(output_dir, ("events", "raids"))
    featured: dict[str, dict[str, Any]] = {}
    evidence = []
    for wrapped in snapshots:
        item, payload = wrapped["index"], wrapped["payload"]
        dexes = player_labs._fact_dexes(payload.get("facts") or [])
        for dex in dexes:
            entry = _entry_for_dex(dex, by_key)
            if not entry:
                continue
            for attack_type in entry.get("types") or []:
                featured[str(attack_type).casefold()] = {
                    "dex": dex,
                    "name": entry.get("display_name"),
                }
        evidence.append(
            {
                "category": item.get("data_category"),
                "provider": item.get("provider"),
                "dataset_timestamp": item.get("dataset_timestamp"),
                "source_reference": item.get("source_reference"),
            }
        )
    return {
        "state": "fresh" if snapshots else "unavailable",
        "types": sorted(featured),
        "type_examples": featured,
        "evidence": evidence,
    }


def build_mega_lab(
    records: list[dict[str, Any]],
    snapshot: Mapping[str, Any],
    by_id: Mapping[str, dict[str, Any]],
    by_key: Mapping[tuple[int, str], list[dict[str, Any]]],
    output_dir: Path,
    domains: Mapping[str, dict[str, Any]],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    current = _current_featured_types(output_dir, by_key)
    items = []
    for record in records:
        entry = player_labs._match_entry(record, by_key)
        if not entry:
            continue
        targets = _transformation_targets(entry, by_id)
        relevant = [item for item in targets if str(item.get("kind") or "").casefold() in {"mega", "primal"}]
        if not relevant:
            continue
        target_types = sorted({str(value).casefold() for item in relevant for value in item.get("types") or []})
        type_match = sorted(set(target_types) & set(current["types"])) if current["state"] == "fresh" else []
        items.append(
            {
                **_record_summary(record, entry),
                "capability": {
                    "can_transform": True,
                    "targets": relevant,
                    "does_not_prove_history": True,
                },
                "local_state": {
                    "first_mega_unlocked": "unknown",
                    "mega_level": "unknown",
                    "super_max_unlocked": "unknown",
                    "mega_energy": None,
                    "next_free_mega": None,
                    "priority": None,
                    "favorite_project": None,
                },
                "current_objective_match": {
                    "state": "fresh-type-overlap" if type_match else current["state"],
                    "matched_types": type_match,
                    "freshness": current["state"],
                    "evidence": current["evidence"],
                    "recommendation_allowed": bool(type_match),
                },
                "opportunity_cost": "Rushing cooldown or Super Max progress spends Mega Energy; local balance and exact per-record state must be entered before comparing spend options.",
                "record_route": f"index.html?record={_record_id(record)}",
                "action_pack": f"action-packs.html?pack=locate-exact&record={_record_id(record)}",
            }
        )
    return {
        "schema_version": MEGA_VERSION,
        "advanced_version": ADVANCED_VERSION,
        "build_id": manifest["build_id"],
        "knowledge": {
            "dataset_version": snapshot.get("dataset_version"),
            "source_commit": snapshot.get("source", {}).get("commit"),
        },
        "mechanics": _reviewed_domain(domains, "mega-primal"),
        "super_max_contract": "Super Max Level is separate from ordinary Mega Level progression and requires Mega Energy investment under the reviewed current mechanic.",
        "state_contract": "Species capability never proves that this exact record has Mega history, level, Energy, or cooldown state.",
        "current_matching": current,
        "storage": {"key": "pokemon-go-collection:mega-state:v1", "schema_version": 1, "unified_backup": True},
        "records": items,
    }


def build_max_lab(
    records: list[dict[str, Any]],
    snapshot: Mapping[str, Any],
    by_key: Mapping[tuple[int, str], list[dict[str, Any]]],
    output_dir: Path,
    domains: Mapping[str, dict[str, Any]],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    fresh = _fresh_snapshot_payloads(output_dir, ("max-battles",))
    bosses = []
    for wrapped in fresh:
        item = wrapped["index"]
        for boss in _walk_bosses(wrapped["payload"].get("facts") or []):
            bosses.append(
                {
                    **boss,
                    "freshness": "fresh",
                    "provider": item.get("provider"),
                    "dataset_timestamp": item.get("dataset_timestamp"),
                    "source_reference": item.get("source_reference"),
                }
            )
    items = []
    for record in records:
        entry = player_labs._match_entry(record, by_key)
        if not entry:
            continue
        items.append(
            {
                **_record_summary(record, entry),
                "species_capability": {
                    "dynamax": entry.get("dynamax_eligibility"),
                    "gigantamax": entry.get("gigantamax_eligibility"),
                    "does_not_prove_owned_max_state": True,
                },
                "local_state": {
                    "dynamax": "unknown",
                    "gigantamax": "unknown",
                    "max_attack_level": None,
                    "max_guard_level": None,
                    "max_spirit_level": None,
                    "fast_move_type": None,
                    "max_build_priority": None,
                },
                "max_attack": {
                    "known_fast_move": (record.get("moves") or {}).get("fast"),
                    "type": "unknown-until-reviewed-or-user-confirmed",
                    "fast_tm_simulation_supported_when_type_known": True,
                },
                "trade_transfer_warning": "Max Move progress and Max/Gigantamax trade/transfer consequences must be reviewed before any irreversible handoff.",
                "record_route": f"index.html?record={_record_id(record)}",
                "action_pack": f"action-packs.html?pack=locate-exact&record={_record_id(record)}",
            }
        )
    return {
        "schema_version": MAX_VERSION,
        "advanced_version": ADVANCED_VERSION,
        "build_id": manifest["build_id"],
        "knowledge": {
            "dataset_version": snapshot.get("dataset_version"),
            "source_commit": snapshot.get("source", {}).get("commit"),
        },
        "mechanics": _reviewed_domain(domains, "max-pokemon"),
        "battle_contract": {
            "party_size": 3,
            "max_trainers": 4,
            "only_explicit_max_owned_state_is_eligible": True,
            "max_attack_follows_fast_attack_type": True,
            "max_guard_and_spirit_are_distinct_roles": True,
            "normal_raid_rankings_are_not_max_simulations": True,
        },
        "current_bosses": {
            "state": "fresh" if fresh else (_snapshot_states(output_dir, "max-battles")[-1] if _snapshot_states(output_dir, "max-battles") else "unavailable"),
            "planning_allowed": bool(fresh),
            "bosses": bosses,
        },
        "storage": {"key": "pokemon-go-collection:max-state:v1", "schema_version": 1, "unified_backup": True},
        "records": items,
    }


def hyper_cp(
    record: Mapping[str, Any],
    entry: Mapping[str, Any],
    mechanics: Mapping[str, Any],
    target_ivs: Mapping[str, int],
) -> dict[str, Any]:
    level, exact = player_labs._level_value(record)
    if level is None or not exact:
        return {"state": "blocked", "reason": "exact level required"}
    cpm = player_labs._cpm_for_level(mechanics, level)
    stats = entry.get("base_stats") or {}
    if cpm is None or not all(isinstance(stats.get(key), (int, float)) for key in ("attack", "defense", "stamina")):
        return {"state": "blocked", "reason": "CP multiplier/base stats unavailable"}
    values = {}
    for key in ("attack", "defense", "stamina"):
        value = target_ivs.get(key)
        if not isinstance(value, int) or value < 0 or value > 15:
            return {"state": "blocked", "reason": f"invalid {key} target"}
        values[key] = value
    attack = float(stats["attack"]) + values["attack"]
    defense = float(stats["defense"]) + values["defense"]
    stamina = float(stats["stamina"]) + values["stamina"]
    cp = math.floor(attack * math.sqrt(defense) * math.sqrt(stamina) * (float(cpm) ** 2) / 10)
    warnings = [f"Crosses {name} cap ({cap})." for name, cap in LEAGUE_CAPS if cp > cap]
    return {
        "state": "projected",
        "cp": max(10, int(cp)),
        "level": level,
        "target_ivs": values,
        "league_cap_warnings": warnings,
    }


def _hyper_next_points(
    record: Mapping[str, Any],
    entry: Mapping[str, Any],
    mechanics: Mapping[str, Any],
) -> list[dict[str, Any]]:
    ivs = record.get("ivs") or {}
    if not all(isinstance(ivs.get(key), int) for key in ("attack", "defense", "stamina")):
        return []
    output = []
    current = {key: int(ivs[key]) for key in ("attack", "defense", "stamina")}
    for stat in ("attack", "defense", "stamina"):
        if current[stat] >= 15:
            continue
        target = dict(current)
        target[stat] += 1
        output.append({"stat": stat, "from": current[stat], "to": target[stat], "projection": hyper_cp(record, entry, mechanics, target)})
    return output


def _owned_alternatives(record: Mapping[str, Any], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dex = int(record.get("pokemon_number") or 0)
    form = player_labs._form_key(record.get("form"))
    current_iv = (record.get("ivs") or {}).get("average_percent")
    alternatives = []
    for other in records:
        if _record_id(other) == _record_id(record):
            continue
        if int(other.get("pokemon_number") or 0) != dex or player_labs._form_key(other.get("form")) != form:
            continue
        other_iv = (other.get("ivs") or {}).get("average_percent")
        if isinstance(current_iv, (int, float)) and isinstance(other_iv, (int, float)) and other_iv > current_iv:
            alternatives.append({"record_id": _record_id(other), "iv_percent": other_iv, "cp": other.get("cp")})
    alternatives.sort(key=lambda item: (-float(item["iv_percent"]), str(item["record_id"])))
    return alternatives[:5]


def build_hyper_lab(
    records: list[dict[str, Any]],
    snapshot: Mapping[str, Any],
    by_key: Mapping[tuple[int, str], list[dict[str, Any]]],
    domains: Mapping[str, dict[str, Any]],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    mechanics = snapshot.get("mechanics") or {}
    items = []
    for record in records:
        entry = player_labs._match_entry(record, by_key)
        if not entry:
            continue
        status = record.get("status") or {}
        ivs = record.get("ivs") or {}
        if status.get("shadow_purified") == "shadow":
            eligibility = "ineligible-shadow"
        elif ivs.get("is_hundo"):
            eligibility = "ineligible-already-4-star"
        else:
            eligibility = "requires-local-good-buddy-confirmation"
        items.append(
            {
                **_record_summary(record, entry),
                "eligibility": eligibility,
                "next_stat_points": _hyper_next_points(record, entry, mechanics),
                "simulation": {
                    "base_stats": entry.get("base_stats") or {},
                    "current_ivs": {key: ivs.get(key) for key in ("attack", "defense", "stamina")},
                    "level": record.get("level") or {},
                    "formula": snapshot.get("mechanics", {}).get("cp_formula"),
                    "supports_all_targets_0_to_15": True,
                },
                "owned_alternatives": _owned_alternatives(record, records),
                "local_state": {
                    "active": "unknown",
                    "good_buddy_or_higher": "unknown",
                    "targets": None,
                    "completed_points": None,
                    "training_deadline": None,
                },
                "irreversible_warning": "Each completed Hyper Training stat point is irreversible and increases CP. Review the next point before completing it.",
                "home_warning": "Reviewed mechanics state that a Pokémon that has undergone Hyper Training cannot be sent to Pokémon HOME.",
                "record_route": f"index.html?record={_record_id(record)}",
                "action_pack": f"action-packs.html?pack=locate-exact&record={_record_id(record)}",
            }
        )
    return {
        "schema_version": HYPER_VERSION,
        "advanced_version": ADVANCED_VERSION,
        "build_id": manifest["build_id"],
        "knowledge": {
            "dataset_version": snapshot.get("dataset_version"),
            "source_commit": snapshot.get("source", {}).get("commit"),
        },
        "mechanics": _reviewed_domain(domains, "hyper-training"),
        "eligibility_contract": "Good Buddy or higher is required; Shadow and existing 4-star Pokémon are ineligible under the reviewed current mechanics.",
        "deadline_contract": "Bottle Cap expiration and training deadlines are browser-local user-entered values unless a future reviewed source explicitly provides them.",
        "storage": {"key": "pokemon-go-collection:hyper-training:v1", "schema_version": 1, "unified_backup": True},
        "records": items,
    }


def _investment_by_id(output_dir: Path) -> dict[str, dict[str, Any]]:
    payload = _load(output_dir / "data" / "investments" / "records.json", {}) or {}
    return {str(item.get("record_id")): dict(item) for item in payload.get("records") or [] if item.get("record_id")}


def build_buddy_queue(
    records: list[dict[str, Any]],
    snapshot: Mapping[str, Any],
    by_key: Mapping[tuple[int, str], list[dict[str, Any]]],
    output_dir: Path,
    domains: Mapping[str, dict[str, Any]],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    investments = _investment_by_id(output_dir)
    seeds = []
    for record in records:
        entry = player_labs._match_entry(record, by_key)
        if not entry:
            continue
        record_id = _record_id(record)
        distance = entry.get("buddy_distance_km")
        evolutions = entry.get("family", {}).get("evolution_species_ids") or []
        investment = investments.get(record_id) or {}
        builds = (investment.get("derived") or {}).get("pvp_builds") or []
        known_build_need = min(
            (
                {
                    "stardust": int(item["stardust_cost"]),
                    "candy": int(item["regular_candy_cost"]),
                    "league": item.get("league"),
                }
                for item in builds
                if item.get("stardust_cost") is not None and item.get("regular_candy_cost") is not None
            ),
            key=lambda item: (item["stardust"], item["candy"]),
            default=None,
        )
        objectives = []
        if evolutions:
            objectives.append({"kind": "evolution", "default_priority": 60, "unlocks": list(evolutions)})
        if known_build_need:
            objectives.append({"kind": "build-candy", "default_priority": 45, "unlocks": known_build_need})
        if not objectives:
            objectives.append({"kind": "best-buddy-user-goal", "default_priority": 20, "unlocks": "user-defined"})
        seeds.append(
            {
                "record_id": record_id,
                "pokemon_number": record.get("pokemon_number"),
                "name": record.get("name"),
                "form": record.get("form"),
                "buddy_distance_km": distance,
                "objectives": objectives,
                "mega_energy": "requires-local-Mega-history-and-reviewed-walking-eligibility",
                "hyper_training": "browser-local-active-state-integrates-at-runtime",
                "alternative_resource_paths": "Only display when separately reviewed or explicitly user-entered; exact Candy/Adventure Sync outcomes are not guessed.",
                "record_route": f"index.html?record={record_id}",
                "action_pack": f"action-packs.html?pack=locate-exact&record={record_id}",
            }
        )
    return {
        "schema_version": BUDDY_VERSION,
        "advanced_version": ADVANCED_VERSION,
        "build_id": manifest["build_id"],
        "knowledge": {
            "dataset_version": snapshot.get("dataset_version"),
            "source_commit": snapshot.get("source", {}).get("commit"),
        },
        "mechanics": _reviewed_domain(domains, "buddy"),
        "ranking_contract": {
            "base": "user priority 0-100 plus objective default priority",
            "deadline": "+40 due within 24h, +20 due within 7d",
            "pin": "+100",
            "skip_or_complete": "excluded",
            "distance": "reported when known, never converted into guaranteed Candy or Mega Energy yield",
        },
        "integrations": {
            "evolution": "data/evolution-lab.json",
            "build_costs": "data/investments/records.json",
            "mega_local_state": "pokemon-go-collection:mega-state:v1",
            "hyper_training_local_state": "pokemon-go-collection:hyper-training:v1",
        },
        "storage": {"key": "pokemon-go-collection:buddy-queue:v1", "schema_version": 1, "unified_backup": True},
        "candidates": seeds,
    }


def _raid_owned_inputs(
    record: Mapping[str, Any],
    entry: Mapping[str, Any],
    mechanics: Mapping[str, Any],
) -> dict[str, Any] | None:
    level, exact = player_labs._level_value(record)
    if level is None:
        return None
    cpm = player_labs._cpm_for_level(mechanics, level)
    if cpm is None:
        return None
    stats = entry.get("base_stats") or {}
    if not all(isinstance(stats.get(key), (int, float)) for key in ("attack", "defense", "stamina")):
        return None
    ivs = record.get("ivs") or {}
    attack_iv = int(ivs.get("attack")) if isinstance(ivs.get("attack"), int) else 0
    defense_iv = int(ivs.get("defense")) if isinstance(ivs.get("defense"), int) else 0
    stamina_iv = int(ivs.get("stamina")) if isinstance(ivs.get("stamina"), int) else 0
    attack = (float(stats["attack"]) + attack_iv) * float(cpm)
    defense = (float(stats["defense"]) + defense_iv) * float(cpm)
    hp = max(10, math.floor((float(stats["stamina"]) + stamina_iv) * float(cpm)))
    moves = record.get("moves") or {}
    known_moves = sum(1 for key in ("fast", "charged") if moves.get(key))
    confidence = 1.0 - (0.10 if not exact else 0.0) - (0.20 if known_moves < 2 else 0.0)
    return {
        "attack": attack,
        "defense": defense,
        "hp": hp,
        "move_completeness": known_moves / 2.0,
        "confidence": max(0.0, confidence),
    }


def simulate_raid(
    boss: Mapping[str, Any],
    records: list[dict[str, Any]],
    by_key: Mapping[tuple[int, str], list[dict[str, Any]]],
    mechanics: Mapping[str, Any],
    *,
    source_freshness: str,
    group_size: int = 1,
    weather_multiplier: float = 1.0,
    friendship_multiplier: float = 1.0,
    party_power_multiplier: float = 1.0,
    mega_multiplier: float = 1.0,
    survival_multiplier: float = 1.0,
) -> dict[str, Any]:
    if source_freshness != "fresh":
        return {"state": "blocked", "reason": "current boss data is not fresh", "model_version": RAID_MODEL_VERSION}
    required = ("hp", "defense", "timer_seconds")
    if not all(isinstance(boss.get(key), (int, float)) and float(boss[key]) > 0 for key in required):
        return {
            "state": "blocked",
            "reason": "boss hp, defense, and timer_seconds are required model inputs",
            "model_version": RAID_MODEL_VERSION,
        }
    if group_size < 1:
        raise ValueError("group_size must be at least 1")
    multipliers = [weather_multiplier, friendship_multiplier, party_power_multiplier, mega_multiplier]
    if any(not isinstance(value, (int, float)) or value <= 0 for value in multipliers) or survival_multiplier <= 0:
        raise ValueError("raid multipliers must be positive")
    candidates = []
    for record in records:
        entry = player_labs._match_entry(record, by_key)
        if not entry:
            continue
        inputs = _raid_owned_inputs(record, entry, mechanics)
        if not inputs:
            continue
        move_factor = 0.60 + 0.40 * float(inputs["move_completeness"])
        rate = (
            float(inputs["attack"])
            / float(boss["defense"])
            * 28.0
            * move_factor
            * float(weather_multiplier)
            * float(friendship_multiplier)
            * float(party_power_multiplier)
            * float(mega_multiplier)
        )
        bulk = float(inputs["defense"]) * math.sqrt(float(inputs["hp"])) / 100.0
        tdo_proxy = rate * bulk * float(survival_multiplier)
        candidates.append(
            {
                "record_id": _record_id(record),
                "name": record.get("name"),
                "form": record.get("form"),
                "cp": record.get("cp"),
                "known_moves": record.get("moves") or {},
                "dps_style_proxy": round(rate, 3),
                "tdo_style_proxy": round(tdo_proxy, 3),
                "confidence": round(float(inputs["confidence"]), 2),
                "owned": True,
            }
        )
    candidates.sort(key=lambda item: (-item["dps_style_proxy"], -item["tdo_style_proxy"], item["record_id"]))
    team = candidates[:6]
    if not team:
        return {"state": "blocked", "reason": "no owned records have sufficient model inputs", "model_version": RAID_MODEL_VERSION}
    mean_dps = sum(float(item["dps_style_proxy"]) for item in team) / len(team)
    group_dps = mean_dps * group_size
    ttw = float(boss["hp"]) / group_dps
    total_tdo = sum(float(item["tdo_style_proxy"]) for item in team) * group_size
    faint_pressure = float(boss["hp"]) / max(total_tdo, 1.0)
    estimated_faints = max(0, math.ceil(faint_pressure * len(team)) - len(team))
    practical = ttw <= float(boss["timer_seconds"]) * 0.90
    confidence = min(float(item["confidence"]) for item in team)
    return {
        "state": "simulated",
        "model_version": RAID_MODEL_VERSION,
        "model_class": "independent deterministic readiness estimator; not an official result and not a competitor algorithm",
        "team": team,
        "alternatives": candidates[6:12],
        "estimated_ttw_seconds": round(ttw, 1),
        "estimated_ttw_range_seconds": [round(ttw * 0.85, 1), round(ttw * 1.25, 1)],
        "estimated_faints": int(estimated_faints),
        "relobby_risk": "high" if estimated_faints >= 6 else "moderate" if estimated_faints >= 3 else "low",
        "practicality": "appears-practical-under-assumptions" if practical else "appears-not-practical-under-assumptions",
        "confidence": "high" if confidence >= 0.9 else "medium" if confidence >= 0.7 else "low",
        "assumptions": {
            "group_size": group_size,
            "weather_multiplier": weather_multiplier,
            "friendship_multiplier": friendship_multiplier,
            "party_power_multiplier": party_power_multiplier,
            "mega_multiplier": mega_multiplier,
            "survival_multiplier": survival_multiplier,
            "boss_hp": boss["hp"],
            "boss_defense": boss["defense"],
            "timer_seconds": boss["timer_seconds"],
            "move_power_model": "Known move completeness adjusts a transparent proxy. Exact PvE move power/cooldown is not silently invented.",
        },
    }


def _current_raid_bosses(
    output_dir: Path,
    by_key: Mapping[tuple[int, str], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fresh = _fresh_snapshot_payloads(output_dir, ("raids",))
    bosses = []
    evidence = []
    seen = set()
    for wrapped in fresh:
        item = wrapped["index"]
        evidence.append(
            {
                "provider": item.get("provider"),
                "dataset_timestamp": item.get("dataset_timestamp"),
                "source_reference": item.get("source_reference"),
                "validity": item.get("validity"),
            }
        )
        for boss in _walk_bosses(wrapped["payload"].get("facts") or []):
            key = (boss.get("dex"), boss.get("name"), boss.get("form"), boss.get("tier"))
            if key in seen:
                continue
            seen.add(key)
            entry = _entry_for_dex(int(boss["dex"]), by_key)
            bosses.append(
                {
                    **boss,
                    "freshness": "fresh",
                    "static_species": {
                        "species_id": (entry or {}).get("species_id"),
                        "types": (entry or {}).get("types") or [],
                        "base_stats": (entry or {}).get("base_stats") or {},
                    },
                    "model_input_state": "needs-user-or-source-backed-hp-defense-timer",
                    "simulation_allowed": False,
                }
            )
    return bosses, evidence


def build_raid_readiness(
    records: list[dict[str, Any]],
    snapshot: Mapping[str, Any],
    by_key: Mapping[tuple[int, str], list[dict[str, Any]]],
    output_dir: Path,
    domains: Mapping[str, dict[str, Any]],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    bosses, evidence = _current_raid_bosses(output_dir, by_key)
    owned = []
    mechanics = snapshot.get("mechanics") or {}
    for record in records:
        entry = player_labs._match_entry(record, by_key)
        if not entry:
            continue
        model_inputs = _raid_owned_inputs(record, entry, mechanics)
        owned.append(
            {
                **_record_summary(record, entry),
                "model_inputs": {
                    "state": "available" if model_inputs else "incomplete",
                    **(model_inputs or {}),
                },
                "move_lab": f"move-lab.html?record={_record_id(record)}",
                "investment": f"index.html?record={_record_id(record)}",
            }
        )
    states = _snapshot_states(output_dir, "raids")
    freshness = "fresh" if bosses else (states[-1] if states else "unavailable")
    return {
        "schema_version": RAID_VERSION,
        "advanced_version": ADVANCED_VERSION,
        "model_version": RAID_MODEL_VERSION,
        "build_id": manifest["build_id"],
        "knowledge": {
            "dataset_version": snapshot.get("dataset_version"),
            "source_commit": snapshot.get("source", {}).get("commit"),
        },
        "mechanics": _reviewed_domain(domains, "raids"),
        "current_bosses": {
            "freshness": freshness,
            "current_simulation_requires_fresh": True,
            "bosses": bosses,
            "evidence": evidence,
        },
        "model": {
            "version": RAID_MODEL_VERSION,
            "classification": "Simulation/Inference",
            "independent_implementation": True,
            "paid_service_required": False,
            "competitor_algorithm_copied": False,
            "formula_summary": "Owned attack stat and move completeness produce a deterministic DPS-style proxy; bulk produces a TDO-style proxy. TTW is emitted only when boss HP, defense, timer and assumption multipliers are explicit inputs.",
            "limits": [
                "No exact PvE move power/cooldown is invented from move names.",
                "Party Power, friendship, weather, Mega/Primal, dodge and other rule effects are explicit multipliers unless a reviewed current mechanic supplies a future deterministic value.",
                "Results are practical/not-practical estimates under assumptions, never guarantees.",
            ],
        },
        "resource_advice": {
            "investment_source": "data/investments/records.json",
            "move_source": "data/move-lab.json",
            "rule": "Compare feasible owned power-up/move alternatives by modeled improvement and known cost; do not recommend spending when required inputs are unknown.",
        },
        "storage": {"key": "pokemon-go-collection:raid-assumptions:v1", "schema_version": 1, "unified_backup": True},
        "owned_records": owned,
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
    build = {"type": "string", "pattern": "^[0-9a-f]{12}$"}
    records = {"type": "array", "items": {"type": "object"}}
    return {
        "advanced-labs-index.schema.json": _schema(
            "advanced-labs-index",
            ["schema_version", "build_id", "labs"],
            {"schema_version": string, "build_id": build, "labs": {"type": "object"}},
        ),
        "mega-lab.schema.json": _schema(
            "mega-lab",
            ["schema_version", "build_id", "super_max_contract", "records"],
            {"schema_version": string, "build_id": build, "super_max_contract": string, "records": records},
        ),
        "max-battle-lab.schema.json": _schema(
            "max-battle-lab",
            ["schema_version", "build_id", "battle_contract", "records"],
            {"schema_version": string, "build_id": build, "battle_contract": {"type": "object"}, "records": records},
        ),
        "hyper-training.schema.json": _schema(
            "hyper-training",
            ["schema_version", "build_id", "eligibility_contract", "records"],
            {"schema_version": string, "build_id": build, "eligibility_contract": string, "records": records},
        ),
        "buddy-queue.schema.json": _schema(
            "buddy-queue",
            ["schema_version", "build_id", "ranking_contract", "candidates"],
            {"schema_version": string, "build_id": build, "ranking_contract": {"type": "object"}, "candidates": records},
        ),
        "raid-readiness.schema.json": _schema(
            "raid-readiness",
            ["schema_version", "build_id", "model_version", "current_bosses", "owned_records"],
            {"schema_version": string, "build_id": build, "model_version": string, "current_bosses": {"type": "object"}, "owned_records": records},
        ),
    }


def _register_contracts() -> None:
    mapping = {
        "data/advanced-labs/index.json": "data/advanced-labs-index.schema.json",
        "data/mega-lab.json": "data/mega-lab.schema.json",
        "data/max-battle-lab.json": "data/max-battle-lab.schema.json",
        "data/hyper-training.json": "data/hyper-training.schema.json",
        "data/buddy-queue.json": "data/buddy-queue.schema.json",
        "data/raid-readiness.json": "data/raid-readiness.schema.json",
    }
    manifest_registry._SCHEMA_MAP.update(mapping)
    stable = {
        "data/advanced-labs/index.json": "advanced_labs_index",
        "data/mega-lab.json": "mega_lab",
        "data/max-battle-lab.json": "max_battle_lab",
        "data/hyper-training.json": "hyper_training",
        "data/buddy-queue.json": "buddy_queue",
        "data/raid-readiness.json": "raid_readiness",
    }
    for resource, schema in mapping.items():
        stable[schema] = Path(schema).name.removesuffix(".json").replace("-", "_")
    manifest_registry._STABLE_NAMES.update(stable)


def _page(output_dir: Path, filename: str, title: str, mount_id: str, description: str) -> None:
    html = f'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title><link rel="stylesheet" href="assets/advanced-labs.css" data-advanced-labs-style></head>
<body><main class="product-page advanced-lab-page"><header class="product-page-header ds-card"><p><a href="today.html">Today</a> · <a href="index.html">Collection</a> · <a href="mega-lab.html">Mega/Primal</a> · <a href="max-battle-lab.html">Max</a> · <a href="hyper-training.html">Hyper Training</a> · <a href="buddy-queue.html">Buddy Queue</a> · <a href="raid-readiness.html">Raid Readiness</a> · <a href="action-packs.html">Action Packs</a></p><h1>{title}</h1><p>{description}</p></header><div id="{mount_id}"><p class="ds-empty">Loading…</p></div></main><script defer src="assets/advanced-labs.js" data-advanced-labs-script></script></body></html>'''
    (output_dir / filename).write_text(html, encoding="utf-8", newline="\n")


def _install_bridges(output_dir: Path) -> None:
    tools = output_dir / "tools.html"
    if tools.is_file():
        source = tools.read_text(encoding="utf-8")
        if "data-advanced-labs-style" not in source:
            source = source.replace("</head>", '<link rel="stylesheet" href="assets/advanced-labs.css" data-advanced-labs-style></head>', 1)
        if "data-advanced-labs-script" not in source:
            player_script = '<script defer src="assets/player-labs.js" data-player-labs-script></script>'
            advanced_script = '<script defer src="assets/advanced-labs.js" data-advanced-labs-script></script>'
            if player_script in source:
                source = source.replace(player_script, advanced_script + player_script, 1)
            else:
                source = source.replace("</body>", advanced_script + "</body>", 1)
        tools.write_text(source, encoding="utf-8", newline="\n")
    today = output_dir / "today.html"
    if today.is_file():
        source = today.read_text(encoding="utf-8")
        if "data-advanced-labs-style" not in source:
            source = source.replace("</head>", '<link rel="stylesheet" href="assets/advanced-labs.css" data-advanced-labs-style></head>', 1)
        if "data-advanced-labs-script" not in source:
            source = source.replace("</body>", '<script defer src="assets/advanced-labs.js" data-advanced-labs-script></script></body>', 1)
        today.write_text(source, encoding="utf-8", newline="\n")


def publish(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    _register_contracts()
    snapshot = player_labs._knowledge(repository_root)
    by_id, by_key = player_labs._knowledge_maps(snapshot)
    pokemon = _load(output_dir / "data" / "pokemon.json", {}) or {}
    records = [dict(item) for item in pokemon.get("records") or []]
    domains = _mechanics_domains(output_dir)

    mega = build_mega_lab(records, snapshot, by_id, by_key, output_dir, domains, manifest)
    max_lab = build_max_lab(records, snapshot, by_key, output_dir, domains, manifest)
    hyper = build_hyper_lab(records, snapshot, by_key, domains, manifest)
    buddy = build_buddy_queue(records, snapshot, by_key, output_dir, domains, manifest)
    raids = build_raid_readiness(records, snapshot, by_key, output_dir, domains, manifest)
    resources = {
        "mega": ("data/mega-lab.json", mega, "mega-lab.html"),
        "max": ("data/max-battle-lab.json", max_lab, "max-battle-lab.html"),
        "hyper_training": ("data/hyper-training.json", hyper, "hyper-training.html"),
        "buddy": ("data/buddy-queue.json", buddy, "buddy-queue.html"),
        "raid_readiness": ("data/raid-readiness.json", raids, "raid-readiness.html"),
    }
    for _, (path, payload, _) in resources.items():
        _write(output_dir / path, payload)
    index = {
        "schema_version": ADVANCED_VERSION,
        "build_id": manifest["build_id"],
        "labs": {name: {"data": path, "page": page} for name, (path, _, page) in resources.items()},
        "safety": {
            "account_access": False,
            "in_game_automation": False,
            "current_claim_requires_fresh_external_evidence": True,
            "owned_state_not_inferred_from_species_capability": True,
            "simulation_is_not_official_fact": True,
        },
    }
    _write(output_dir / "data" / "advanced-labs" / "index.json", index)
    for filename, schema in schemas().items():
        Draft202012Validator.check_schema(schema)
        _write(output_dir / "data" / filename, schema)

    assets = output_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repository_root / "site" / "advanced-labs.js", assets / "advanced-labs.js")
    shutil.copyfile(repository_root / "site" / "advanced-labs.css", assets / "advanced-labs.css")
    _page(output_dir, "mega-lab.html", "Mega / Primal Lab", "mega-lab-root", "Plan exact-record Mega and Primal projects with explicit history, Energy, cooldown, Super Max, and current-event freshness boundaries.")
    _page(output_dir, "max-battle-lab.html", "Max Battle Lab", "max-battle-lab-root", "Track explicit Dynamax/Gigantamax state, Max Move roles, particles, parties, and fresh current-boss assumptions separately from ordinary raids.")
    _page(output_dir, "hyper-training.html", "Hyper Training Planner", "hyper-training-root", "Simulate exact IV/CP consequences before spending Bottle Caps or completing irreversible stat points.")
    _page(output_dir, "buddy-queue.html", "Buddy Queue", "buddy-queue-root", "Rank exact owned buddy projects by transparent user priorities, deadlines, evolution, build, Mega, and Hyper Training goals.")
    _page(output_dir, "raid-readiness.html", "Raid Readiness", "raid-readiness-root", "Estimate personalized raid readiness from exact owned records with explicit boss/model assumptions, confidence, and freshness.")
    _install_bridges(output_dir)
    return index


__all__ = [
    "ADVANCED_VERSION",
    "RAID_MODEL_VERSION",
    "hyper_cp",
    "simulate_raid",
    "build_mega_lab",
    "build_max_lab",
    "build_hyper_lab",
    "build_buddy_queue",
    "build_raid_readiness",
    "schemas",
    "publish",
]
