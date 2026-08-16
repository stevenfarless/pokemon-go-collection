"""Conservative longitudinal identity for Poke Genie rescans.

This layer runs after same-state duplicate reconciliation. It treats CP, HP, level,
moves, scan timestamps, and other mutable values as observations while requiring
multiple independent stable clues before collapsing observations into one current
owned entity.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Mapping, Sequence

try:
    from .collection_integrity import build_scan_quality_report, reconcile_records
except ImportError:  # Direct execution through scripts/build_dashboard.py
    from collection_integrity import build_scan_quality_report, reconcile_records

LONGITUDINAL_SCHEMA_VERSION = "1.0.0"


def _hash_payload(payload: Any, length: int = 20) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:length]


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _stable_core(record: Mapping[str, Any]) -> tuple[Any, ...] | None:
    ivs = record.get("ivs", {})
    exact_ivs = tuple(ivs.get(key) for key in ("attack", "defense", "stamina"))
    if any(value is None for value in exact_ivs):
        return None
    status = record.get("status", {})
    return (
        record.get("pokemon_number"),
        _text(record.get("form")).casefold(),
        _text(record.get("gender")).casefold(),
        *exact_ivs,
        _text(status.get("shadow_purified") or "normal").casefold(),
        bool(status.get("lucky")),
    )


def _size_pair(record: Mapping[str, Any]) -> tuple[Any, Any] | None:
    size = record.get("size", {})
    weight = size.get("weight")
    height = size.get("height")
    return None if weight is None or height is None else (weight, height)


def _identity_evidence(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    """Describe whether two observations can safely represent one owned Pokémon."""
    left_core = _stable_core(left)
    right_core = _stable_core(right)
    if left_core is None or left_core != right_core:
        return {
            "compatible": False,
            "strong": False,
            "matched": [],
            "blocking": ["stable core differs"],
        }

    left_dates = left.get("dates", {})
    right_dates = right.get("dates", {})
    left_catch = _text(left_dates.get("catch"))
    right_catch = _text(right_dates.get("catch"))
    if left_catch and right_catch and left_catch != right_catch:
        return {
            "compatible": False,
            "strong": False,
            "matched": [],
            "blocking": ["catch date conflicts"],
        }

    left_size = _size_pair(left)
    right_size = _size_pair(right)
    if left_size is not None and right_size is not None and left_size != right_size:
        return {
            "compatible": False,
            "strong": False,
            "matched": [],
            "blocking": ["weight/height pair conflicts"],
        }

    matched: list[str] = []
    if left_catch and left_catch == right_catch:
        matched.append("matching non-empty catch date")
    if left_size is not None and left_size == right_size:
        matched.append("matching non-empty weight and height")

    left_original = _text(left_dates.get("original_scan"))
    right_original = _text(right_dates.get("original_scan"))
    if left_original and left_original == right_original:
        matched.append("matching non-empty original-scan value")

    return {
        "compatible": True,
        "strong": len(matched) >= 2,
        "matched": matched,
        "blocking": [],
    }


def _stable_buckets(records: Sequence[Mapping[str, Any]]) -> list[list[int]]:
    buckets: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        core = _stable_core(record)
        if core is not None:
            buckets[core].append(index)
    return [indices for indices in buckets.values() if len(indices) >= 2]


def _strong_components(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for indices in _stable_buckets(records):
        adjacency: dict[int, set[int]] = {index: set() for index in indices}
        edge_reasons: dict[tuple[int, int], list[str]] = {}
        for offset, left_index in enumerate(indices[:-1]):
            for right_index in indices[offset + 1:]:
                evidence = _identity_evidence(records[left_index], records[right_index])
                if not evidence["strong"]:
                    continue
                adjacency[left_index].add(right_index)
                adjacency[right_index].add(left_index)
                edge_reasons[(min(left_index, right_index), max(left_index, right_index))] = evidence[
                    "matched"
                ]

        seen: set[int] = set()
        for start in indices:
            if start in seen or not adjacency[start]:
                continue
            stack = [start]
            component: list[int] = []
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                component.append(current)
                stack.extend(sorted(adjacency[current] - seen, reverse=True))
            if len(component) < 2:
                continue
            component.sort()
            reasons = sorted(
                {
                    reason
                    for pair, pair_reasons in edge_reasons.items()
                    if pair[0] in component and pair[1] in component
                    for reason in pair_reasons
                }
            )
            groups.append({"indices": component, "reasons": reasons})
    return sorted(groups, key=lambda group: group["indices"][0])


def _ambiguous_pairs(
    records: Sequence[Mapping[str, Any]],
    groups: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Expose plausible but insufficient matches without changing ownership counts."""
    component_for: dict[int, int] = {}
    for group_number, group in enumerate(groups):
        for index in group["indices"]:
            component_for[index] = group_number

    candidates: list[dict[str, Any]] = []
    for indices in _stable_buckets(records):
        for offset, left_index in enumerate(indices[:-1]):
            for right_index in indices[offset + 1:]:
                if (
                    component_for.get(left_index) is not None
                    and component_for.get(left_index) == component_for.get(right_index)
                ):
                    continue
                evidence = _identity_evidence(records[left_index], records[right_index])
                if not evidence["compatible"] or evidence["strong"] or not evidence["matched"]:
                    continue
                source_rows = sorted(
                    {
                        int(row)
                        for index in (left_index, right_index)
                        for row in records[index].get("provenance", {}).get("source_rows", [])
                    }
                )
                candidates.append(
                    {
                        "candidate_id": "history_candidate_"
                        + _hash_payload(
                            {
                                "source_rows": source_rows,
                                "matched": evidence["matched"],
                            },
                            16,
                        ),
                        "schema_version": LONGITUDINAL_SCHEMA_VERSION,
                        "confidence": "ambiguous",
                        "source_rows": source_rows,
                        "matched_corroborators": evidence["matched"],
                        "matched_corroborator_count": len(evidence["matched"]),
                        "required_corroborator_count": 2,
                        "action": "preserve as separate current Pokémon pending stronger evidence",
                    }
                )
    return candidates


def _parse_recency(value: Any) -> tuple[int, str]:
    text = _text(value)
    if not text:
        return (0, "")
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return (int(parsed.timestamp()), text)
    except (ValueError, OverflowError):
        pass
    try:
        parsed_date = date.fromisoformat(text[:10])
        return (parsed_date.toordinal() * 86400, text)
    except ValueError:
        return (0, text)


def _completeness(record: Mapping[str, Any]) -> int:
    values = [
        record.get("hp"),
        record.get("gender"),
        record.get("ivs", {}).get("attack"),
        record.get("ivs", {}).get("defense"),
        record.get("ivs", {}).get("stamina"),
        record.get("level", {}).get("minimum"),
        record.get("level", {}).get("maximum"),
        record.get("moves", {}).get("fast"),
        record.get("moves", {}).get("charged"),
        record.get("dates", {}).get("catch"),
        record.get("size", {}).get("weight"),
        record.get("size", {}).get("height"),
    ]
    return sum(value not in (None, "") for value in values)


def _current_index(records: Sequence[Mapping[str, Any]], indices: Sequence[int]) -> int:
    return max(
        indices,
        key=lambda index: (
            _parse_recency(records[index].get("dates", {}).get("scan")),
            _completeness(records[index]),
            max(records[index].get("provenance", {}).get("source_rows", [0])),
        ),
    )


def _group_identity_payload(
    records: Sequence[Mapping[str, Any]],
    indices: Sequence[int],
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Hash only corroborators that are stable across the entire reconciled group."""
    ivs = current.get("ivs", {})
    status = current.get("status", {})
    catch_values = {
        _text(records[index].get("dates", {}).get("catch"))
        for index in indices
        if _text(records[index].get("dates", {}).get("catch"))
    }
    size_values = {
        _size_pair(records[index])
        for index in indices
        if _size_pair(records[index]) is not None
    }
    original_scan_values = {
        _text(records[index].get("dates", {}).get("original_scan"))
        for index in indices
        if _text(records[index].get("dates", {}).get("original_scan"))
    }
    return {
        "pokemon_number": current.get("pokemon_number"),
        "form": current.get("form"),
        "gender": current.get("gender"),
        "exact_ivs": [ivs.get("attack"), ivs.get("defense"), ivs.get("stamina")],
        "status": [status.get("shadow_purified"), bool(status.get("lucky"))],
        "catch": next(iter(catch_values)) if len(catch_values) == 1 else None,
        "size": list(next(iter(size_values))) if len(size_values) == 1 else [None, None],
        "original_scan": (
            next(iter(original_scan_values)) if len(original_scan_values) == 1 else None
        ),
    }


def _fill_stable_missing(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    target_dates = target.setdefault("dates", {})
    source_dates = source.get("dates", {})
    if not target_dates.get("catch") and source_dates.get("catch"):
        target_dates["catch"] = source_dates["catch"]
    target_size = target.setdefault("size", {})
    source_size = source.get("size", {})
    for key in ("weight", "height"):
        if target_size.get(key) is None and source_size.get(key) is not None:
            target_size[key] = source_size[key]


def _observation(record: Mapping[str, Any]) -> dict[str, Any]:
    state = copy.deepcopy(dict(record))
    identity = state.pop("identity", {})
    provenance = state.pop("provenance", {})
    return {
        "observation_id": "obs_"
        + _hash_payload(
            {
                "source_rows": provenance.get("source_rows", []),
                "record_id": identity.get("record_id"),
                "state": state,
            },
            16,
        ),
        "source_rows": list(provenance.get("source_rows", [])),
        "source_indices": list(provenance.get("source_indices", [])),
        "source_scan_count": int(
            provenance.get("source_scan_count")
            or len(provenance.get("source_rows", []))
            or 1
        ),
        "state": state,
    }


def reconcile_longitudinal(
    records: Sequence[dict[str, Any]],
    deduplication_report: Mapping[str, Any],
    source_row_to_record_id: Mapping[int, str],
    *,
    source_filename: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[int, str]]:
    """Collapse only strongly corroborated mutable-state rescans into current entities."""
    groups = _strong_components(records)
    candidate_pairs = _ambiguous_pairs(records, groups)
    member_to_group: dict[int, dict[str, Any]] = {}
    for group in groups:
        for index in group["indices"]:
            member_to_group[index] = group

    retained: list[dict[str, Any]] = []
    row_map = dict(source_row_to_record_id)
    emitted: set[int] = set()
    report_groups: list[dict[str, Any]] = []

    for index, source in enumerate(records):
        group = member_to_group.get(index)
        if group is None:
            retained.append(copy.deepcopy(source))
            continue
        group_key = group["indices"][0]
        if group_key in emitted:
            continue
        emitted.add(group_key)

        current_index = _current_index(records, group["indices"])
        current = copy.deepcopy(records[current_index])
        for member in group["indices"]:
            if member != current_index:
                _fill_stable_missing(current, records[member])

        observations = [_observation(records[member]) for member in group["indices"]]
        source_rows = sorted({row for item in observations for row in item["source_rows"]})
        source_indices = [
            value
            for item in observations
            for value in item["source_indices"]
            if value is not None
        ]
        scan_values = sorted(
            {
                _text(records[member].get("dates", {}).get("scan"))
                for member in group["indices"]
                if _text(records[member].get("dates", {}).get("scan"))
            }
        )
        identity_payload = _group_identity_payload(records, group["indices"], current)
        entity_id = "entity_" + _hash_payload(identity_payload, 20)
        stable_fingerprint = "fp_" + _hash_payload(identity_payload, 20)
        record_id = "pgc_" + _hash_payload(
            {
                "source_export": source_filename,
                "entity_id": entity_id,
                "source_rows": source_rows,
            },
            20,
        )

        current_identity = current.setdefault("identity", {})
        current_identity["record_id"] = record_id
        current_identity["record_fingerprint"] = stable_fingerprint
        current_identity["fingerprint_confidence"] = "high"

        current_provenance = current.setdefault("provenance", {})
        current_provenance["source_rows"] = source_rows
        current_provenance["source_indices"] = source_indices
        current_provenance["source_scan_count"] = len(source_rows)
        current_provenance["first_observed_scan"] = scan_values[0] if scan_values else None
        current_provenance["last_observed_scan"] = scan_values[-1] if scan_values else None

        for member in group["indices"]:
            for row in records[member].get("provenance", {}).get("source_rows", []):
                row_map[int(row)] = record_id

        retained.append(current)
        report_groups.append(
            {
                "group_id": "history_"
                + _hash_payload(
                    {"entity_id": entity_id, "source_rows": source_rows},
                    16,
                ),
                "schema_version": LONGITUDINAL_SCHEMA_VERSION,
                "confidence": "high-confidence",
                "entity_id": entity_id,
                "entity_id_scope": "best-effort-cross-build-when-stable-evidence-remains-present",
                "identity_basis": identity_payload,
                "canonical_record_id": record_id,
                "current_observation_id": observations[
                    group["indices"].index(current_index)
                ]["observation_id"],
                "current_source_rows": list(
                    records[current_index].get("provenance", {}).get("source_rows", [])
                ),
                "source_rows": source_rows,
                "source_indices": source_indices,
                "observation_count": len(observations),
                "source_scan_count": len(source_rows),
                "reasons": [
                    "same species/form/gender/exact IVs and protected status boundary",
                    "mutable CP/HP/level/moves do not define identity",
                    "at least two independent non-empty corroborators matched on every connecting edge",
                    *group["reasons"],
                ],
                "observations": observations,
            }
        )

    updated = copy.deepcopy(dict(deduplication_report))
    updated["normalized_record_count"] = len(retained)
    updated["duplicates_collapsed"] = (
        int(updated.get("source_record_count", len(records))) - len(retained)
    )
    updated["longitudinal_schema_version"] = LONGITUDINAL_SCHEMA_VERSION
    updated["longitudinal_group_count"] = len(report_groups)
    updated["longitudinal_observations_collapsed"] = len(records) - len(retained)
    updated["longitudinal_groups"] = report_groups
    policy = updated.setdefault("policy", {})
    policy["longitudinal"] = {
        "bias": "preserve ambiguity",
        "mutable_fields": [
            "cp",
            "hp",
            "level",
            "moves",
            "scan timestamp",
            "favorite",
            "PvP outputs",
        ],
        "required_core": [
            "species/form",
            "gender",
            "exact IVs",
            "shadow/purified status",
            "lucky status",
        ],
        "corroborators": ["catch date", "weight+height pair", "original-scan value"],
        "minimum_matching_corroborators_per_edge": 2,
        "blocking_conflicts": [
            "catch date when both present",
            "weight+height when both complete",
            "protected status boundary",
        ],
        "species_and_ivs_alone_are_sufficient": False,
        "migration": (
            "Existing build-scoped record_id remains the canonical current-record key. "
            "longitudinal_groups adds a best-effort cross-build entity_id plus auditable "
            "observations without changing the normalized record schema."
        ),
    }

    for group in updated.get("automatic_groups", []):
        rows = group.get("source_rows", [])
        if rows:
            group["canonical_record_id"] = row_map.get(
                int(rows[0]),
                group.get("canonical_record_id"),
            )

    unresolved_possible: list[dict[str, Any]] = []
    for group in updated.get("possible_groups", []):
        record_ids = list(
            dict.fromkeys(
                row_map.get(int(row))
                for row in group.get("source_rows", [])
                if row_map.get(int(row))
            )
        )
        if len(record_ids) <= 1:
            continue
        group["record_ids"] = record_ids
        unresolved_possible.append(group)
    updated["possible_groups"] = unresolved_possible
    updated["possible_group_count"] = len(unresolved_possible)

    candidates: list[dict[str, Any]] = []
    for candidate in candidate_pairs:
        record_ids = list(
            dict.fromkeys(
                row_map.get(int(row))
                for row in candidate["source_rows"]
                if row_map.get(int(row))
            )
        )
        if len(record_ids) <= 1:
            continue
        candidate["record_ids"] = record_ids
        candidates.append(candidate)
    updated["longitudinal_candidate_count"] = len(candidates)
    updated["longitudinal_candidates"] = candidates

    return retained, updated, row_map


def process_longitudinal_collection(
    rows: Sequence[Mapping[str, Any]],
    records: Sequence[dict[str, Any]],
    *,
    source_filename: str,
    reference_date: date | None,
    unknown_columns: Sequence[str] = (),
    semantic_warnings: Sequence[Mapping[str, Any]] = (),
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Run exact reconciliation first, then longitudinal reconciliation and quality checks."""
    exact_records, deduplication, row_map = reconcile_records(
        rows,
        records,
        source_filename=source_filename,
    )
    normalized, deduplication, row_map = reconcile_longitudinal(
        exact_records,
        deduplication,
        row_map,
        source_filename=source_filename,
    )
    quality = build_scan_quality_report(
        normalized,
        deduplication,
        source_filename=source_filename,
        reference_date=reference_date,
        unknown_columns=unknown_columns,
        semantic_warnings=semantic_warnings,
        source_row_to_record_id=row_map,
    )
    return normalized, deduplication, quality
