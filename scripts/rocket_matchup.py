"""Normalize current Team GO Rocket lineups into source-safe matchup inputs.

This module intentionally stops before ranking owned Pokémon. Current lineup identities
come from the freshness-gated Rocket provider; stable species typing comes from the
pinned Pokémon GO knowledge snapshot. Move typing, damage, timing, shields, and
survivability remain explicit prerequisites instead of being inferred from species names.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

MATCHUP_CONTRACT_VERSION = "1.0.0"


def _dex(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _reference_types(reference: Mapping[str, Any]) -> dict[int, tuple[str, ...] | None]:
    """Return one stable type tuple per dex, or None when released forms disagree."""
    by_dex: dict[int, set[tuple[str, ...]]] = defaultdict(set)
    for raw in reference.get("entries") or []:
        dex = _dex(raw.get("dex"))
        if dex is None or raw.get("released") is False:
            continue
        types = tuple(sorted({str(value).casefold() for value in raw.get("types") or [] if value}))
        if types:
            by_dex[dex].add(types)
    return {dex: next(iter(values)) if len(values) == 1 else None for dex, values in by_dex.items()}


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


def normalize_matchup_context(encounter: Mapping[str, Any], reference: Mapping[str, Any]) -> dict[str, Any]:
    """Build typed opponent-slot facts without creating a counter ranking."""
    type_map = _reference_types(reference)
    raw_slots = encounter.get("slots") or encounter.get("lineup") or encounter.get("lineups") or []
    slots: list[dict[str, Any]] = []
    unresolved: set[int] = set()

    for index, raw_slot in enumerate(raw_slots if isinstance(raw_slots, list) else [raw_slots], start=1):
        possibilities: list[dict[str, Any]] = []
        seen: set[int] = set()
        for raw in _slot_entries(raw_slot):
            dex = _dex(raw.get("dex"))
            if dex is None or dex in seen:
                continue
            seen.add(dex)
            types = type_map.get(dex)
            if types is None:
                unresolved.add(dex)
            possibilities.append(
                {
                    "dex": dex,
                    "name": raw.get("name"),
                    "types": list(types) if types else [],
                    "type_state": "stable-reference" if types else "unresolved-form-or-reference",
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
        "provenance": {
            "lineup": "freshness-gated current Rocket provider",
            "typing": "pinned versioned Pokémon GO species reference",
            "classification": "normalized factual inputs",
        },
        "ranking": {
            "state": "blocked-missing-battle-inputs",
            "reason": "Opponent typing alone does not establish an exact owned counter ranking.",
            "required_before_ranking": [
                "normalized type-effectiveness mechanic",
                "typed current fast and charged moves for each owned candidate",
                "battle timing/damage inputs for any timing, shield, or survivability claim",
            ],
        },
    }


def analyze_owned_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Expose exact owned facts needed by a future matcher without scoring them."""
    moves = candidate.get("moves") or {}
    knowledge = candidate.get("knowledge") or {}
    return {
        "record_id": candidate.get("record_id") or (candidate.get("identity") or {}).get("record_id"),
        "pokemon_number": candidate.get("pokemon_number"),
        "name": candidate.get("name"),
        "cp": candidate.get("cp"),
        "species_types": list(knowledge.get("types") or []),
        "observed_moves": {
            "fast": moves.get("fast"),
            "charged": moves.get("charged"),
            "charged_second": moves.get("charged_second"),
        },
        "move_typing_state": "unresolved",
        "matchup_score": None,
        "recommendation_allowed": False,
    }


__all__ = ["MATCHUP_CONTRACT_VERSION", "normalize_matchup_context", "analyze_owned_candidate"]
