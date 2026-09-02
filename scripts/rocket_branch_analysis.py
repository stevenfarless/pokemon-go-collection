"""Aggregate Team GO Rocket branching matchup facts without inventing battle outcomes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from scripts import rocket_matchup

BRANCH_ANALYSIS_CONTRACT_VERSION = "1.3.0"


def _known_numbers(values: Iterable[Any]) -> list[float]:
    numbers: list[float] = []
    for value in values:
        if isinstance(value, bool):
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            numbers.append(parsed)
    return numbers


def _missing_opponent_dexes(possibilities: Iterable[Mapping[str, Any]], metric: str) -> list[Any]:
    """Return exact branch identities whose required factual metric is unavailable."""
    return [
        item.get("opponent_dex")
        for item in possibilities
        if not _known_numbers([item.get(metric)])
    ]


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
        offensive_missing = _missing_opponent_dexes(possibilities, "best_effectiveness_multiplier")
        defensive_missing = _missing_opponent_dexes(
            possibilities,
            "worst_case_same_type_attack_multiplier",
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
                "offensive_missing_opponent_dexes": offensive_missing,
                "offensive_floor_multiplier": min(offensive) if offensive_complete else None,
                "offensive_ceiling_multiplier": max(offensive) if offensive_complete else None,
                "defensive_same_type_known_count": len(defensive),
                "defensive_same_type_state": "available" if defensive_complete else "partial",
                "defensive_same_type_missing_opponent_dexes": defensive_missing,
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
    offensive_blockers = list(
        dict.fromkeys(
            dex
            for item in branch_summary
            for dex in item["offensive_missing_opponent_dexes"]
            if dex is not None
        )
    )
    defensive_blockers = list(
        dict.fromkeys(
            dex
            for item in branch_summary
            for dex in item["defensive_same_type_missing_opponent_dexes"]
            if dex is not None
        )
    )
    result["branch_analysis"] = {
        "contract_version": BRANCH_ANALYSIS_CONTRACT_VERSION,
        "state": "available" if complete else "partial",
        "slots": branch_summary,
        "blocking_offensive_opponent_dexes": offensive_blockers,
        "blocking_defensive_opponent_dexes": defensive_blockers,
        "ranking_allowed": False,
        "reason": "Branch type coverage alone does not establish a Rocket counter or win outcome.",
    }
    return result


def _complete_slot_metrics(analysis: Mapping[str, Any]) -> dict[Any, tuple[float, float]] | None:
    """Return complete offensive-floor/defensive-pressure pairs for one owned record."""
    branch = analysis.get("branch_analysis") or {}
    slots = branch.get("slots") or []
    if branch.get("state") != "available" or not slots:
        return None

    metrics: dict[Any, tuple[float, float]] = {}
    for slot in slots:
        if slot.get("offensive_state") != "available" or slot.get("defensive_same_type_state") != "available":
            return None
        offensive = _known_numbers([slot.get("offensive_floor_multiplier")])
        defensive = _known_numbers([slot.get("defensive_worst_case_same_type_multiplier")])
        slot_number = slot.get("slot")
        if len(offensive) != 1 or len(defensive) != 1 or slot_number in metrics:
            return None
        metrics[slot_number] = (offensive[0], defensive[0])
    return metrics or None


def compare_candidate_coverage(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    """Compare two owned records using only complete factual branch type coverage.

    Dominance means one record has an equal-or-higher offensive floor and an
    equal-or-lower same-type defensive multiplier in every shared lineup slot, with at
    least one strict improvement. This is a type-coverage relationship. It is not a
    Rocket counter ranking because opponent moves, levels, timing, shields, and actual
    damage remain outside the current model.
    """
    left_metrics = _complete_slot_metrics(left)
    right_metrics = _complete_slot_metrics(right)
    if left_metrics is None or right_metrics is None or left_metrics.keys() != right_metrics.keys():
        return {
            "state": "blocked-incomplete-coverage",
            "left_dominates": False,
            "right_dominates": False,
            "ranking_allowed": False,
        }

    def dominates(first: Mapping[Any, tuple[float, float]], second: Mapping[Any, tuple[float, float]]) -> bool:
        weakly_better = all(
            first[slot][0] >= second[slot][0] and first[slot][1] <= second[slot][1]
            for slot in first
        )
        strictly_better = any(
            first[slot][0] > second[slot][0] or first[slot][1] < second[slot][1]
            for slot in first
        )
        return weakly_better and strictly_better

    return {
        "state": "available",
        "left_dominates": dominates(left_metrics, right_metrics),
        "right_dominates": dominates(right_metrics, left_metrics),
        "ranking_allowed": False,
        "semantics": "complete branch type-coverage dominance only",
    }


def summarize_candidate_dominance(analyses: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Expose pairwise type-coverage dominance for exact owned records when complete."""
    prepared: list[tuple[Any, Mapping[str, Any]]] = []
    seen_ids: set[Any] = set()
    for analysis in analyses:
        candidate = analysis.get("candidate") or {}
        record_id = candidate.get("record_id")
        if record_id is None or record_id in seen_ids:
            continue
        seen_ids.add(record_id)
        prepared.append((record_id, analysis))

    output: list[dict[str, Any]] = []
    for record_id, analysis in prepared:
        dominates_ids: list[Any] = []
        dominated_by_ids: list[Any] = []
        comparable = 0
        for other_id, other in prepared:
            if other_id == record_id:
                continue
            comparison = compare_candidate_coverage(analysis, other)
            if comparison["state"] != "available":
                continue
            comparable += 1
            if comparison["left_dominates"]:
                dominates_ids.append(other_id)
            if comparison["right_dominates"]:
                dominated_by_ids.append(other_id)
        output.append(
            {
                "record_id": record_id,
                "state": "available" if _complete_slot_metrics(analysis) is not None else "partial",
                "comparable_candidate_count": comparable,
                "dominates_record_ids": dominates_ids,
                "dominated_by_record_ids": dominated_by_ids,
                "ranking_allowed": False,
            }
        )
    return output


def summarize_candidate_frontier(dominance: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return exact owned records that survive complete type-coverage dominance pruning.

    The frontier contains only complete candidates with no known complete candidate that
    dominates them. Partial candidates remain explicitly excluded because missing branch
    facts cannot safely prove that they belong on the frontier. The frontier is a pruning
    aid, not a battle ranking or party recommendation.
    """
    frontier_ids: list[Any] = []
    dominated_ids: list[Any] = []
    partial_ids: list[Any] = []
    for item in dominance:
        record_id = item.get("record_id")
        if record_id is None:
            continue
        if item.get("state") != "available":
            partial_ids.append(record_id)
        elif item.get("dominated_by_record_ids"):
            dominated_ids.append(record_id)
        else:
            frontier_ids.append(record_id)

    return {
        "state": "available" if frontier_ids else "blocked-no-complete-candidates",
        "frontier_record_ids": frontier_ids,
        "dominated_record_ids": dominated_ids,
        "partial_record_ids": partial_ids,
        "ranking_allowed": False,
        "party_selection_allowed": False,
        "semantics": "non-dominated complete branch type-coverage candidates only",
    }


def analyze_owned_branch_candidates(
    candidates: Iterable[Mapping[str, Any]],
    matchup_context: Mapping[str, Any],
    mechanics: Mapping[str, Any],
) -> dict[str, Any]:
    """Analyze multiple exact owned records and expose safe type-coverage comparisons."""
    analyses = [analyze_owned_branch_matchup(candidate, matchup_context, mechanics) for candidate in candidates]
    dominance = summarize_candidate_dominance(analyses)
    return {
        "contract_version": BRANCH_ANALYSIS_CONTRACT_VERSION,
        "candidate_analyses": analyses,
        "candidate_dominance": dominance,
        "candidate_frontier": summarize_candidate_frontier(dominance),
        "recommendation": {
            "state": "blocked-missing-rocket-battle-inputs",
            "ranking_allowed": False,
            "reason": (
                "Type-coverage dominance can eliminate some strictly weaker coverage profiles, "
                "but it cannot select a Rocket party without verified opponent battle inputs."
            ),
        },
    }


__all__ = [
    "BRANCH_ANALYSIS_CONTRACT_VERSION",
    "summarize_branch_coverage",
    "analyze_owned_branch_matchup",
    "compare_candidate_coverage",
    "summarize_candidate_dominance",
    "summarize_candidate_frontier",
    "analyze_owned_branch_candidates",
]
