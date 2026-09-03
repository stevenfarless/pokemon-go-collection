"""Normalize current Team GO Rocket lineups into source-safe matchup inputs.

Current lineup identities come from the freshness-gated Rocket provider; stable species
and form facts come from the pinned Pokémon GO knowledge snapshot. Pinned trainer-battle
mechanics can resolve exact observed move typing and factual type-effectiveness coverage.
Opponent levels and Rocket-specific move assignments, timing, shields, and survivability
remain explicit prerequisites for exact battle recommendations.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

MATCHUP_CONTRACT_VERSION = "1.1.0"


def _dex(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _form_token(value: Any) -> str:
    token = " ".join(str(value or "").casefold().replace("-", " ").split())
    aliases = {
        "alolan": "alola",
        "galarian": "galar",
        "hisuian": "hisui",
        "paldean": "paldea",
        "none": "normal",
        "ordinary": "normal",
    }
    return aliases.get(token, token)


def _reference_entries(reference: Mapping[str, Any]) -> dict[int, list[Mapping[str, Any]]]:
    by_dex: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for raw in reference.get("entries") or []:
        dex = _dex(raw.get("dex"))
        if dex is None or raw.get("released") is False:
            continue
        by_dex[dex].append(raw)
    return by_dex


def _entry_types(entry: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value).casefold() for value in entry.get("types") or [] if value}))


def _entry_move_pool(entry: Mapping[str, Any]) -> dict[str, list[str]] | None:
    raw = entry.get("moves")
    if not isinstance(raw, Mapping):
        return None
    pool = {
        key: sorted({str(value) for value in raw.get(key) or [] if value})
        for key in ("fast", "charged", "elite_or_exclusive", "legacy")
    }
    return pool if pool["fast"] or pool["charged"] else None


def _entry_form_aliases(entry: Mapping[str, Any]) -> set[str]:
    values = {
        _form_token(entry.get("form_key")),
        _form_token(entry.get("form_label")),
    }
    values.update(_form_token(value) for value in entry.get("form_aliases") or [])
    return values


def _reference_facts(
    opponent: Mapping[str, Any],
    by_dex: Mapping[int, list[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Resolve form-aware species facts without guessing across distinct released forms."""
    dex = _dex(opponent.get("dex"))
    candidates = list(by_dex.get(dex or -1) or [])
    requested_form = opponent.get("form")
    selected: Mapping[str, Any] | None = None
    resolution = "unresolved-form-or-reference"

    if requested_form:
        token = _form_token(requested_form)
        matches = [entry for entry in candidates if token in _entry_form_aliases(entry)]
        if len(matches) == 1:
            selected = matches[0]
            resolution = "provider-form-reference"
    else:
        normal = [entry for entry in candidates if "normal" in _entry_form_aliases(entry)]
        if len(normal) == 1:
            selected = normal[0]
            resolution = "default-normal-form-reference"
        elif len(candidates) == 1:
            selected = candidates[0]
            resolution = "single-released-form-reference"

    if selected is not None:
        types = _entry_types(selected)
        return {
            "types": types,
            "type_state": resolution if types else "unresolved-form-or-reference",
            "move_pool": _entry_move_pool(selected),
            "move_pool_state": "versioned-species-reference" if _entry_move_pool(selected) else "unavailable",
            "resolved_form_key": selected.get("form_key"),
        }

    type_sets = {_entry_types(entry) for entry in candidates if _entry_types(entry)}
    stable_types = next(iter(type_sets)) if len(type_sets) == 1 else ()
    return {
        "types": stable_types,
        "type_state": "stable-across-released-forms" if stable_types else "unresolved-form-or-reference",
        "move_pool": None,
        "move_pool_state": "unresolved-form-or-reference",
        "resolved_form_key": None,
    }


def _slot_entries(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if _dex(value.get("dex")) is not None:
            yield value
        else:
            for child in value.values():
                yield from _slot_entries(child)
    elif isinstance(value, list):
        for child in value:
            yield from _slot_entries(child)


def _move_key(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _move_index(mechanics: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    by_name: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for raw in mechanics.get("moves") or []:
        key = _move_key(raw.get("name"))
        if key:
            by_name[key].append(raw)
    return by_name


def _resolve_observed_move(value: Any, move_index: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, Any]:
    if not value:
        return {"name": value, "state": "not-observed", "type": None}

    matches = list(move_index.get(_move_key(value)) or [])
    if not matches:
        return {"name": value, "state": "unresolved", "type": None}

    types = sorted({str(raw.get("type")).casefold() for raw in matches if raw.get("type")})
    if len(types) != 1:
        return {
            "name": value,
            "state": "ambiguous",
            "type": None,
            "candidate_types": types,
            "candidate_move_ids": sorted(str(raw.get("move_id")) for raw in matches if raw.get("move_id")),
        }

    result: dict[str, Any] = {"name": value, "state": "resolved", "type": types[0]}
    if len(matches) == 1:
        raw = matches[0]
        result["mechanics"] = {
            key: raw.get(key)
            for key in ("move_id", "power", "energy", "energy_gain", "cooldown_ms", "turns", "archetype")
            if key in raw
        }
    else:
        result["mechanics_state"] = "ambiguous-same-type-variant"
        result["candidate_move_ids"] = sorted(str(raw.get("move_id")) for raw in matches if raw.get("move_id"))
    return result


def _positive_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _move_pressure_summary(
    move_slot: str,
    resolved: Mapping[str, Any],
    species_types: Iterable[Any],
    mechanics: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Derive generic trainer-battle pressure facts without claiming Rocket outcomes."""
    if resolved.get("state") != "resolved" or not isinstance(resolved.get("mechanics"), Mapping):
        return None

    raw = resolved["mechanics"]
    power = _positive_number(raw.get("power"))
    move_type = str(resolved.get("type") or "").casefold()
    owned_types = {str(value).casefold() for value in species_types if value}
    multipliers = mechanics.get("multipliers") or {}
    stab_multiplier = float(multipliers.get("same_type_attack_bonus", 1.0)) if move_type in owned_types else 1.0
    adjusted_power = power * stab_multiplier if power is not None else None

    summary: dict[str, Any] = {
        "move_slot": move_slot,
        "classification": "generic-trainer-battle-pressure",
        "same_type_attack_bonus_applies": move_type in owned_types,
        "same_type_attack_bonus_multiplier": stab_multiplier,
        "base_power": power,
        "stab_adjusted_power": adjusted_power,
    }

    turns = _positive_number(raw.get("turns"))
    energy_gain = _positive_number(raw.get("energy_gain"))
    energy_cost = _positive_number(raw.get("energy"))
    if move_slot == "fast":
        summary["turns"] = turns
        summary["power_per_turn"] = adjusted_power / turns if adjusted_power is not None and turns else None
        summary["energy_gain_per_turn"] = energy_gain / turns if energy_gain is not None and turns else None
    else:
        summary["energy_cost"] = energy_cost
        summary["power_per_energy"] = adjusted_power / energy_cost if adjusted_power is not None and energy_cost else None
    return summary


def type_effectiveness_multiplier(
    attacking_type: Any,
    defender_types: Iterable[Any],
    mechanics: Mapping[str, Any],
) -> float | None:
    """Return the pinned Pokémon GO type multiplier, or None for incomplete inputs."""
    attack = str(attacking_type or "").casefold()
    defenders = [str(value).casefold() for value in defender_types if value]
    type_traits = mechanics.get("type_traits") or {}
    multipliers = mechanics.get("multipliers") or {}
    required = ("super_effective", "resisted", "double_resisted")
    if not attack or not defenders or any(key not in multipliers for key in required):
        return None

    value = 1.0
    for defender in defenders:
        traits = type_traits.get(defender)
        if not isinstance(traits, Mapping):
            return None
        if attack in {str(item).casefold() for item in traits.get("immunities") or []}:
            value *= float(multipliers["double_resisted"])
        elif attack in {str(item).casefold() for item in traits.get("weaknesses") or []}:
            value *= float(multipliers["super_effective"])
        elif attack in {str(item).casefold() for item in traits.get("resistances") or []}:
            value *= float(multipliers["resisted"])
    return value


def normalize_matchup_context(encounter: Mapping[str, Any], reference: Mapping[str, Any]) -> dict[str, Any]:
    """Build form-aware typed opponent-slot facts without creating a counter ranking."""
    reference_by_dex = _reference_entries(reference)
    raw_slots = encounter.get("slots") or encounter.get("lineup") or encounter.get("lineups") or []
    slots: list[dict[str, Any]] = []
    unresolved: set[int] = set()
    unresolved_move_pools: set[int] = set()

    for index, raw_slot in enumerate(raw_slots if isinstance(raw_slots, list) else [raw_slots], start=1):
        possibilities: list[dict[str, Any]] = []
        seen: set[tuple[int, str]] = set()
        for raw in _slot_entries(raw_slot):
            dex = _dex(raw.get("dex"))
            if dex is None:
                continue
            form_token = _form_token(raw.get("form")) if raw.get("form") else "normal"
            identity = (dex, form_token)
            if identity in seen:
                continue
            seen.add(identity)
            facts = _reference_facts(raw, reference_by_dex)
            types = facts["types"]
            if not types:
                unresolved.add(dex)
            if facts["move_pool"] is None:
                unresolved_move_pools.add(dex)
            possibilities.append(
                {
                    "dex": dex,
                    "name": raw.get("name"),
                    "form": raw.get("form"),
                    "resolved_form_key": facts["resolved_form_key"],
                    "types": list(types),
                    "type_state": facts["type_state"],
                    "trainer_battle_move_pool": facts["move_pool"],
                    "move_pool_state": facts["move_pool_state"],
                    "rocket_move_assignment_verified": False,
                }
            )
        slots.append({"slot": index, "possibilities": possibilities})

    has_targets = any(slot["possibilities"] for slot in slots)
    return {
        "contract_version": MATCHUP_CONTRACT_VERSION,
        "state": "available" if has_targets and not unresolved else "partial" if has_targets else "blocked",
        "encounter_id": encounter.get("encounter_id"),
        "slots": slots,
        "unresolved_dexes": sorted(unresolved),
        "unresolved_move_pool_dexes": sorted(unresolved_move_pools),
        "provenance": {
            "lineup": "freshness-gated current Rocket provider",
            "typing": "pinned versioned Pokémon GO species/form reference",
            "trainer_battle_move_pool": "pinned versioned Pokémon GO species/form reference",
            "rocket_move_assignment_verified": False,
            "classification": "normalized factual inputs",
        },
        "ranking": {
            "state": "blocked-missing-battle-inputs",
            "reason": "Typed matchup coverage and species move pools do not establish an exact owned counter ranking.",
            "required_before_ranking": [
                "Rocket opponent levels and verified move assignments",
                "Rocket-specific battle timing and shield behavior",
                "damage and survivability calculation using exact owned stats",
            ],
        },
    }


def analyze_owned_candidate(
    candidate: Mapping[str, Any],
    mechanics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Expose exact owned facts and resolve observed move mechanics when available."""
    moves = candidate.get("moves") or {}
    knowledge = candidate.get("knowledge") or {}
    species_types = list(knowledge.get("types") or [])
    observed = {
        "fast": moves.get("fast"),
        "charged": moves.get("charged"),
        "charged_second": moves.get("charged_second"),
    }
    resolved_moves: dict[str, Any] = {}
    pressure_summary: dict[str, Any] = {}
    move_typing_state = "unresolved"
    if mechanics is not None:
        move_index = _move_index(mechanics)
        resolved_moves = {slot: _resolve_observed_move(value, move_index) for slot, value in observed.items()}
        observed_states = [resolved_moves[slot]["state"] for slot, value in observed.items() if value]
        if observed_states and all(state == "resolved" for state in observed_states):
            move_typing_state = "resolved"
        elif any(state == "resolved" for state in observed_states):
            move_typing_state = "partial"
        pressure_summary = {
            slot: summary
            for slot, resolved in resolved_moves.items()
            if (summary := _move_pressure_summary(slot, resolved, species_types, mechanics)) is not None
        }

    return {
        "record_id": candidate.get("record_id") or (candidate.get("identity") or {}).get("record_id"),
        "pokemon_number": candidate.get("pokemon_number"),
        "name": candidate.get("name"),
        "cp": candidate.get("cp"),
        "species_types": species_types,
        "observed_moves": observed,
        "resolved_moves": resolved_moves,
        "move_typing_state": move_typing_state,
        "pressure_summary": pressure_summary,
        "pressure_state": "available" if pressure_summary else "unavailable",
        "matchup_score": None,
        "recommendation_allowed": False,
    }


def analyze_owned_matchup(
    candidate: Mapping[str, Any],
    matchup_context: Mapping[str, Any],
    mechanics: Mapping[str, Any],
) -> dict[str, Any]:
    """Calculate factual type pressure while keeping battle recommendations blocked."""
    owned = analyze_owned_candidate(candidate, mechanics)
    coverage: list[dict[str, Any]] = []

    for slot in matchup_context.get("slots") or []:
        slot_number = slot.get("slot")
        for opponent in slot.get("possibilities") or []:
            defender_types = opponent.get("types") or []
            moves: list[dict[str, Any]] = []
            for move_slot, resolved in owned["resolved_moves"].items():
                if resolved.get("state") != "resolved":
                    continue
                multiplier = type_effectiveness_multiplier(resolved.get("type"), defender_types, mechanics)
                moves.append(
                    {
                        "move_slot": move_slot,
                        "name": resolved.get("name"),
                        "type": resolved.get("type"),
                        "effectiveness_multiplier": multiplier,
                    }
                )
            known = [item["effectiveness_multiplier"] for item in moves if item["effectiveness_multiplier"] is not None]

            same_type_attack_pressure = [
                {
                    "attacking_type": opponent_type,
                    "effectiveness_multiplier": type_effectiveness_multiplier(
                        opponent_type,
                        owned["species_types"],
                        mechanics,
                    ),
                }
                for opponent_type in defender_types
            ]
            known_incoming = [
                item["effectiveness_multiplier"]
                for item in same_type_attack_pressure
                if item["effectiveness_multiplier"] is not None
            ]
            coverage.append(
                {
                    "slot": slot_number,
                    "opponent_dex": opponent.get("dex"),
                    "opponent_name": opponent.get("name"),
                    "opponent_types": list(defender_types),
                    "moves": moves,
                    "best_effectiveness_multiplier": max(known) if known else None,
                    "same_type_attack_pressure": same_type_attack_pressure,
                    "worst_case_same_type_attack_multiplier": max(known_incoming) if known_incoming else None,
                }
            )

    return {
        "candidate": owned,
        "coverage_state": "available"
        if coverage and all(item["best_effectiveness_multiplier"] is not None for item in coverage)
        else "partial",
        "coverage": coverage,
        "recommendation": {
            "state": "blocked-missing-rocket-battle-inputs",
            "reason": "Type coverage and generic move pressure cannot establish an exact Rocket counter or win outcome.",
        },
    }


__all__ = [
    "MATCHUP_CONTRACT_VERSION",
    "normalize_matchup_context",
    "analyze_owned_candidate",
    "analyze_owned_matchup",
    "type_effectiveness_multiplier",
]
