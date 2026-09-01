"""Aggregate Team GO Rocket branching matchup facts without inventing battle outcomes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from scripts import rocket_matchup

BRANCH_ANALYSIS_CONTRACT_VERSION = "1.0.0"


def _known_numbers(values: Iterable[Any]) -> list[float]:
    numbers: list[float] = []
    for value in values:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            numbers.append(parsed)
    return numbers


def summarize_branch_coverage(coverage: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Summarize conservative per-slot floors/ceilings across branching possibilities.

    Aggregates are emitted only when every possibility has the corresponding factual
    input. Partial branch data therefore cannot silently become a best/worst-case claim.
    Defensive values describe same-type pressure implied by species typing; they do not
    assert which moves a Rocket opponent actually carries.
    """
    by_slot: dict[Any, list[Mapping[str, Any]]] = defaultdict(list)
    for item in coverage:
        by_slot[item.get("slot")].append(item)

    summaries: list[dict[str, Any]] = []
    for slot in sorted(by_slot, key=lambda value: (value is None, str(value))):
        possibilities = by_slot[slot]
        total = len(possibilities)
        offensive = _known_numbers(item.get("best_effectiveness_multiplier") for item in possibilities)
        defensive = _known_numbers(
            item.get("worst_case_same_type_attack_multiplier") for item in possibilities
        )
        offensive_complete = total > 0 and len(offensive) == total
        defensive_complete = total > 0 and len(defensive) == total
        summaries.append(
            {
                "slot": slot,
                "possibility_count": total,
                "opponent_dexes": [item.get("opponent_dex") for item in possibilities],
                "offensive_known_count": len(offensive),
                "offensive_state": "available" if offensive_complete else "partial",
                "offensive_floor_multiplier": min(offensive) if offensive_complete else None,
                "offensive_ceiling_multiplier": max(offensive) if offensive_complete else None,
                "defensive_same_type_known_count": len(defensive),
                "defensive_same_type_state": "available" if defensive_complete else "partial",
                "defensive_worst_case_same_type_multiplier": max(defensive) if defensive_complete else None,
                "defensive_semantics": "species-type pressure only; opponent moves remain unknown",
            }
        )
    return summaries


def analyze_owned_branch_matchup(
    candidate: Mapping[str, Any],
    matchup_context: Mapping[str, Any],
    mechanics: Mapping[str, Any],
) -> dict[str, Any]:
    """Add uncertainty-aware branch summaries to the existing owned-matchup analysis."""
    result = dict(rocket_matchup.analyze_owned_matchup(candidate, matchup_context, mechanics))
    branch_summary = summarize_branch_coverage(result.get("coverage") or [])
    complete = bool(branch_summary) and all(
        item["offensive_state"] == "available" and item["defensive_same_type_state"] == "available"
        for item in branch_summary
    )
    result["branch_analysis"] = {
        "contract_version": BRANCH_ANALYSIS_CONTRACT_VERSION,
        "state": "available" if complete else "partial",
        "slots": branch_summary,
        "ranking_allowed": False,
        "reason": "Branch type coverage alone does not establish a Rocket counter or win outcome.",
    }
    return result


__all__ = [
    "BRANCH_ANALYSIS_CONTRACT_VERSION",
    "summarize_branch_coverage",
    "analyze_owned_branch_matchup",
]
