"""Canonical identity, conservative rescan reconciliation, and scan-quality reporting."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence

IDENTITY_VERSION = "1.0.0"
FOUNDATION_SCHEMA_VERSION = "2.0.0"
DEDUPLICATION_SCHEMA_VERSION = "1.0.0"
SCAN_QUALITY_SCHEMA_VERSION = "1.0.0"
STALE_SCAN_DAYS = 180

_AUTO_KEY_COLUMNS = (
    "Pokemon Number",
    "Name",
    "Form",
    "Gender",
    "CP",
    "HP",
    "Shadow/Purified",
    "Lucky",
    "Scan Date",
    "Original Scan Date",
)
_CORE_KEY_COLUMNS = (
    "Pokemon Number",
    "Name",
    "Form",
    "Gender",
    "CP",
    "HP",
    "Shadow/Purified",
    "Lucky",
)
_BLOCKING_CONFLICT_COLUMNS = (
    "Atk IV",
    "Def IV",
    "Sta IV",
    "Level Min",
    "Level Max",
    "Catch Date",
    "Quick Move",
    "Charge Move",
    "Charge Move 2",
)
_MEANINGFUL_PATHS = (
    ("hp",),
    ("gender",),
    ("ivs", "attack"),
    ("ivs", "defense"),
    ("ivs", "stamina"),
    ("ivs", "average_percent"),
    ("level", "minimum"),
    ("level", "maximum"),
    ("moves", "fast"),
    ("moves", "charged"),
    ("moves", "charged_second"),
    ("dates", "scan"),
    ("dates", "original_scan"),
    ("dates", "catch"),
    ("size", "weight"),
    ("size", "height"),
    ("dust",),
    ("pvp", "great", "rank_percent"),
    ("pvp", "ultra", "rank_percent"),
    ("pvp", "little", "rank_percent"),
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _hash_payload(payload: Any, length: int = 16) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:length]


def _get_path(record: Mapping[str, Any], path: Sequence[str]) -> Any:
    value: Any = record
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def _completeness(record: Mapping[str, Any]) -> int:
    score = 0
    for path in _MEANINGFUL_PATHS:
        value = _get_path(record, path)
        if value not in (None, ""):
            score += 1
    return score


def _contiguous(indices: Sequence[int]) -> bool:
    if not indices:
        return False
    ordered = sorted(indices)
    return ordered[-1] - ordered[0] == len(ordered) - 1


def _values_conflict(rows: Sequence[Mapping[str, Any]], column: str) -> bool:
    values = {_text(row.get(column)) for row in rows if _text(row.get(column))}
    return len(values) > 1


def _merge_missing(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    """Fill genuinely missing values without overwriting conflicting evidence."""
    for key, value in source.items():
        if key not in target:
            continue
        current = target[key]
        if isinstance(current, dict) and isinstance(value, Mapping):
            _merge_missing(current, value)
        elif current in (None, "") and value not in (None, ""):
            target[key] = copy.deepcopy(value)


def _record_for_exact_compare(record: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(record))
    result.pop("source_index", None)
    result.pop("identity", None)
    result.pop("provenance", None)
    return result


def _scan_values(records: Sequence[Mapping[str, Any]], indices: Sequence[int], key: str) -> list[str]:
    values = {
        _text(records[index].get("dates", {}).get(key))
        for index in indices
        if _text(records[index].get("dates", {}).get(key))
    }
    return sorted(values)


def _fingerprint_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    ivs = record.get("ivs", {})
    dates = record.get("dates", {})
    size = record.get("size", {})
    status = record.get("status", {})
    payload = {
        "pokemon_number": record.get("pokemon_number"),
        "form": record.get("form"),
        "gender": record.get("gender"),
        "exact_ivs": [ivs.get("attack"), ivs.get("defense"), ivs.get("stamina")],
        "original_scan": dates.get("original_scan"),
        "catch": dates.get("catch"),
        "size": [size.get("weight"), size.get("height")],
        "status": [status.get("shadow_purified"), status.get("lucky")],
    }
    if not dates.get("original_scan"):
        payload["fallback_state"] = {
            "cp": record.get("cp"),
            "hp": record.get("hp"),
            "level": [
                record.get("level", {}).get("minimum"),
                record.get("level", {}).get("maximum"),
            ],
        }
    return payload


def _fingerprint_confidence(record: Mapping[str, Any]) -> str:
    ivs = record.get("ivs", {})
    exact_ivs = all(ivs.get(key) is not None for key in ("attack", "defense", "stamina"))
    dates = record.get("dates", {})
    if dates.get("original_scan") and exact_ivs:
        return "high"
    if exact_ivs and (dates.get("catch") or dates.get("original_scan")):
        return "medium"
    return "low"


def _identity_and_provenance(
    record: dict[str, Any],
    *,
    source_filename: str,
    source_rows: Sequence[int],
    source_indices: Sequence[Any],
    duplicate_group_id: str | None,
    duplicate_confidence: str,
    observed_scan_values: Sequence[str],
) -> None:
    fingerprint = "fp_" + _hash_payload(_fingerprint_payload(record), 20)
    record_id = "pgc_" + _hash_payload(
        {
            "source_export": source_filename,
            "fingerprint": fingerprint,
            "source_rows": list(source_rows),
            "source_indices": [value for value in source_indices if value is not None],
        },
        20,
    )
    record["identity"] = {
        "version": IDENTITY_VERSION,
        "record_id": record_id,
        "id_scope": "build",
        "record_fingerprint": fingerprint,
        "fingerprint_scope": "best-effort-cross-build",
        "fingerprint_confidence": _fingerprint_confidence(record),
    }
    record["provenance"] = {
        "source_export": source_filename,
        "source_rows": list(source_rows),
        "source_indices": [value for value in source_indices if value is not None],
        "source_scan_count": len(source_rows),
        "first_observed_scan": observed_scan_values[0] if observed_scan_values else None,
        "last_observed_scan": observed_scan_values[-1] if observed_scan_values else None,
        "duplicate_group_id": duplicate_group_id,
        "duplicate_confidence": duplicate_confidence,
    }


def _auto_groups(
    rows: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], set[int]]:
    grouped: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        scan = _text(row.get("Scan Date"))
        original_scan = _text(row.get("Original Scan Date"))
        if not scan or not original_scan:
            continue
        key = tuple(_text(row.get(column)) for column in _AUTO_KEY_COLUMNS)
        grouped[key].append(index)

    groups: list[dict[str, Any]] = []
    consumed: set[int] = set()
    for key, indices in sorted(grouped.items(), key=lambda item: min(item[1])):
        if len(indices) < 2 or not _contiguous(indices):
            continue
        candidate_rows = [rows[index] for index in indices]
        conflicts = [
            column
            for column in _BLOCKING_CONFLICT_COLUMNS
            if _values_conflict(candidate_rows, column)
        ]
        if conflicts:
            continue
        comparable = [_record_for_exact_compare(records[index]) for index in indices]
        confidence = "exact" if all(item == comparable[0] for item in comparable[1:]) else "high-confidence"
        canonical_index = max(
            indices,
            key=lambda index: (_completeness(records[index]), -index),
        )
        group_id = "dup_" + _hash_payload(
            {"signature": key, "source_rows": [index + 2 for index in indices]},
            16,
        )
        groups.append(
            {
                "group_id": group_id,
                "confidence": confidence,
                "indices": list(indices),
                "canonical_index": canonical_index,
                "reasons": [
                    "same species/form/gender/CP/HP/status",
                    "same scan and original-scan timestamps",
                    "source rows are contiguous",
                    "no conflicting exact IV, level, catch-date, or move evidence",
                    "canonical scan chosen by completeness",
                ],
            }
        )
        consumed.update(indices)
    return groups, consumed


def _possible_groups(
    rows: Sequence[Mapping[str, Any]],
    auto_members: set[int],
) -> list[dict[str, Any]]:
    possible: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for left in range(len(rows) - 1):
        right = left + 1
        if left in auto_members and right in auto_members:
            continue
        left_key = tuple(_text(rows[left].get(column)) for column in _CORE_KEY_COLUMNS)
        right_key = tuple(_text(rows[right].get(column)) for column in _CORE_KEY_COLUMNS)
        if left_key != right_key:
            continue
        pair = (left, right)
        if pair in seen:
            continue
        seen.add(pair)
        conflicts = [
            column
            for column in _BLOCKING_CONFLICT_COLUMNS
            if _values_conflict([rows[left], rows[right]], column)
        ]
        possible.append(
            {
                "group_id": "possible_" + _hash_payload(
                    {"core": left_key, "source_rows": [left + 2, right + 2]},
                    16,
                ),
                "confidence": "possible",
                "indices": [left, right],
                "reasons": [
                    "adjacent rows share species/form/gender/CP/HP/status",
                    "automatic rescan evidence was insufficient",
                    *([f"conflicting fields: {', '.join(conflicts)}"] if conflicts else []),
                ],
            }
        )
    return possible


def reconcile_records(
    rows: Sequence[Mapping[str, Any]],
    records: Sequence[dict[str, Any]],
    *,
    source_filename: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[int, str]]:
    """Collapse only strongly evidenced rescans and attach canonical identity/provenance."""
    if len(rows) != len(records):
        raise ValueError("Raw-row and normalized-record counts differ")

    groups, auto_members = _auto_groups(rows, records)
    possible = _possible_groups(rows, auto_members)
    group_by_member: dict[int, dict[str, Any]] = {}
    for group in groups:
        for index in group["indices"]:
            group_by_member[index] = group

    retained: list[dict[str, Any]] = []
    source_row_to_record_id: dict[int, str] = {}
    emitted_groups: set[str] = set()
    automatic_report: list[dict[str, Any]] = []

    for index, original in enumerate(records):
        group = group_by_member.get(index)
        if group is None:
            record = copy.deepcopy(original)
            source_rows = [index + 2]
            source_indices = [original.get("source_index")]
            observed = _scan_values(records, [index], "scan")
            _identity_and_provenance(
                record,
                source_filename=source_filename,
                source_rows=source_rows,
                source_indices=source_indices,
                duplicate_group_id=None,
                duplicate_confidence="none",
                observed_scan_values=observed,
            )
            retained.append(record)
            source_row_to_record_id[index + 2] = record["identity"]["record_id"]
            continue

        if group["group_id"] in emitted_groups:
            continue
        emitted_groups.add(group["group_id"])
        indices = group["indices"]
        canonical = copy.deepcopy(records[group["canonical_index"]])
        for member in indices:
            if member != group["canonical_index"]:
                _merge_missing(canonical, records[member])

        source_rows = [member + 2 for member in indices]
        source_indices = [records[member].get("source_index") for member in indices]
        observed = _scan_values(records, indices, "scan")
        _identity_and_provenance(
            canonical,
            source_filename=source_filename,
            source_rows=source_rows,
            source_indices=source_indices,
            duplicate_group_id=group["group_id"],
            duplicate_confidence=group["confidence"],
            observed_scan_values=observed,
        )
        retained.append(canonical)
        record_id = canonical["identity"]["record_id"]
        for source_row in source_rows:
            source_row_to_record_id[source_row] = record_id
        automatic_report.append(
            {
                "group_id": group["group_id"],
                "confidence": group["confidence"],
                "canonical_record_id": record_id,
                "canonical_source_row": group["canonical_index"] + 2,
                "source_rows": source_rows,
                "source_indices": [value for value in source_indices if value is not None],
                "source_scan_count": len(source_rows),
                "reasons": group["reasons"],
            }
        )

    possible_report: list[dict[str, Any]] = []
    for group in possible:
        source_rows = [index + 2 for index in group["indices"]]
        possible_report.append(
            {
                "group_id": group["group_id"],
                "confidence": "possible",
                "source_rows": source_rows,
                "record_ids": [
                    source_row_to_record_id.get(source_row)
                    for source_row in source_rows
                    if source_row_to_record_id.get(source_row)
                ],
                "reasons": group["reasons"],
            }
        )

    report = {
        "schema_version": DEDUPLICATION_SCHEMA_VERSION,
        "source_file": source_filename,
        "source_record_count": len(records),
        "normalized_record_count": len(retained),
        "duplicates_collapsed": len(records) - len(retained),
        "automatic_group_count": len(automatic_report),
        "possible_group_count": len(possible_report),
        "policy": {
            "bias": "preserve ambiguous records",
            "automatic_confidence": ["exact", "high-confidence"],
            "possible_duplicates_are_collapsed": False,
            "requires_matching_scan_timestamps": True,
            "requires_contiguous_source_rows": True,
        },
        "automatic_groups": automatic_report,
        "possible_groups": possible_report,
    }
    return retained, report, source_row_to_record_id


def _parse_date(value: Any) -> date | None:
    text = _text(value)
    if not text:
        return None
    candidates = (text[:10], text)
    for candidate in candidates:
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            pass
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _finding(
    *,
    severity: str,
    reason_code: str,
    action: str,
    message: str,
    record: Mapping[str, Any] | None = None,
    source_rows: Sequence[int] | None = None,
    source_indices: Sequence[Any] | None = None,
) -> dict[str, Any]:
    provenance = record.get("provenance", {}) if isinstance(record, Mapping) else {}
    identity = record.get("identity", {}) if isinstance(record, Mapping) else {}
    return {
        "severity": severity,
        "reason_code": reason_code,
        "suggested_action": action,
        "message": message,
        "record_id": identity.get("record_id"),
        "source_rows": list(source_rows if source_rows is not None else provenance.get("source_rows", [])),
        "source_indices": [
            value
            for value in (source_indices if source_indices is not None else provenance.get("source_indices", []))
            if value is not None
        ],
    }


def build_scan_quality_report(
    records: Sequence[Mapping[str, Any]],
    deduplication_report: Mapping[str, Any],
    *,
    source_filename: str,
    reference_date: date | None,
    unknown_columns: Iterable[str] = (),
    semantic_warnings: Sequence[Mapping[str, Any]] = (),
    source_row_to_record_id: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    stale_before = reference_date - timedelta(days=STALE_SCAN_DAYS) if reference_date else None

    for record in records:
        ivs = record.get("ivs", {})
        if any(ivs.get(key) is None for key in ("attack", "defense", "stamina")):
            findings.append(_finding(
                severity="warning",
                reason_code="missing_exact_ivs",
                action="rescan",
                message="One or more exact IV values are missing.",
                record=record,
            ))
        if record.get("hp") is None:
            findings.append(_finding(
                severity="warning",
                reason_code="missing_hp",
                action="rescan",
                message="HP is missing, so scan completeness is reduced.",
                record=record,
            ))
        level = record.get("level", {})
        if level.get("minimum") is None or level.get("maximum") is None:
            findings.append(_finding(
                severity="warning",
                reason_code="missing_level",
                action="rescan",
                message="Level information is incomplete.",
                record=record,
            ))
        moves = record.get("moves", {})
        if not moves.get("fast") or not moves.get("charged"):
            findings.append(_finding(
                severity="info",
                reason_code="incomplete_moves",
                action="rescan",
                message="Fast or primary charged move is missing.",
                record=record,
            ))
        scan_date = _parse_date(record.get("dates", {}).get("scan"))
        if scan_date is None:
            findings.append(_finding(
                severity="info",
                reason_code="missing_scan_date",
                action="review",
                message="Scan date is missing or unparseable.",
                record=record,
            ))
        elif stale_before and scan_date <= stale_before:
            findings.append(_finding(
                severity="warning",
                reason_code="stale_scan",
                action="rescan",
                message=f"Scan is at least {STALE_SCAN_DAYS} days older than the export date.",
                record=record,
            ))

    row_map = source_row_to_record_id or {}
    record_by_id = {
        record.get("identity", {}).get("record_id"): record
        for record in records
        if record.get("identity", {}).get("record_id")
    }
    for warning in semantic_warnings:
        row_number = int(warning.get("row_number") or 0)
        record_id = row_map.get(row_number)
        record = record_by_id.get(record_id)
        column = _text(warning.get("column")) or "unknown"
        slug = re.sub(r"[^a-z0-9]+", "_", column.casefold()).strip("_") or "field"
        findings.append(_finding(
            severity="warning",
            reason_code=f"parser_warning_{slug}",
            action="parser_update" if "unrecognized" in _text(warning.get("message")).casefold() else "review",
            message=_text(warning.get("message")) or "Source value required parser fallback.",
            record=record,
            source_rows=[row_number] if row_number else [],
            source_indices=[warning.get("source_index")] if warning.get("source_index") else [],
        ))

    for group in deduplication_report.get("automatic_groups", []):
        findings.append(_finding(
            severity="info",
            reason_code="duplicate_scan_collapsed",
            action="informational",
            message=f"Repeated scan group {group['group_id']} was conservatively collapsed.",
            source_rows=group.get("source_rows", []),
            source_indices=group.get("source_indices", []),
        ))
        findings[-1]["record_id"] = group.get("canonical_record_id")

    for group in deduplication_report.get("possible_groups", []):
        findings.append(_finding(
            severity="warning",
            reason_code="possible_duplicate_scan",
            action="review",
            message=f"Possible duplicate group {group['group_id']} was preserved for manual review.",
            source_rows=group.get("source_rows", []),
        ))

    unknown = sorted({_text(value) for value in unknown_columns if _text(value)})
    for column in unknown:
        findings.append(_finding(
            severity="info",
            reason_code="unknown_source_column",
            action="parser_update",
            message=f"Unrecognized source column {column!r} is preserved in source-column metadata.",
        ))

    severity_counts = Counter(item["severity"] for item in findings)
    action_counts = Counter(item["suggested_action"] for item in findings)
    reason_counts = Counter(item["reason_code"] for item in findings)
    return {
        "schema_version": SCAN_QUALITY_SCHEMA_VERSION,
        "source_file": source_filename,
        "record_count": len(records),
        "stale_scan_days": STALE_SCAN_DAYS,
        "summary": {
            "finding_count": len(findings),
            "severity_counts": dict(sorted(severity_counts.items())),
            "action_counts": dict(sorted(action_counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
        },
        "coverage": {
            "exact_ivs": "validated",
            "hp_and_level_presence": "validated",
            "moves_presence": "validated",
            "scan_freshness": "validated when scan date is parseable",
            "status_parser_values": "validated through semantic diagnostics when available",
            "species_and_form_semantics": "not classified as unknown until the canonical species/mechanics knowledge base is available",
            "species_specific_cp_hp_plausibility": "deferred to the canonical species/mechanics knowledge base",
        },
        "findings": findings,
    }


def process_collection(
    rows: Sequence[Mapping[str, Any]],
    records: Sequence[dict[str, Any]],
    *,
    source_filename: str,
    reference_date: date | None,
    unknown_columns: Iterable[str] = (),
    semantic_warnings: Sequence[Mapping[str, Any]] = (),
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    normalized, deduplication, row_map = reconcile_records(
        rows,
        records,
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


def patch_record_schema(schema: dict[str, Any]) -> None:
    """Extend the normalized record contract with explicit identity and provenance."""
    required = schema.setdefault("required", [])
    for key in ("identity", "provenance"):
        if key not in required:
            required.append(key)
    properties = schema.setdefault("properties", {})
    properties["identity"] = {
        "type": "object",
        "required": [
            "version",
            "record_id",
            "id_scope",
            "record_fingerprint",
            "fingerprint_scope",
            "fingerprint_confidence",
        ],
        "properties": {
            "version": {"type": "string", "const": IDENTITY_VERSION},
            "record_id": {"type": "string", "pattern": "^pgc_[0-9a-f]{20}$"},
            "id_scope": {"type": "string", "const": "build"},
            "record_fingerprint": {"type": "string", "pattern": "^fp_[0-9a-f]{20}$"},
            "fingerprint_scope": {"type": "string", "const": "best-effort-cross-build"},
            "fingerprint_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "additionalProperties": False,
    }
    properties["provenance"] = {
        "type": "object",
        "required": [
            "source_export",
            "source_rows",
            "source_indices",
            "source_scan_count",
            "first_observed_scan",
            "last_observed_scan",
            "duplicate_group_id",
            "duplicate_confidence",
        ],
        "properties": {
            "source_export": {"type": "string", "minLength": 1},
            "source_rows": {
                "type": "array",
                "items": {"type": "integer", "minimum": 2},
                "minItems": 1,
                "uniqueItems": True,
            },
            "source_indices": {
                "type": "array",
                "items": {"type": ["integer", "number", "string"]},
            },
            "source_scan_count": {"type": "integer", "minimum": 1},
            "first_observed_scan": {"type": ["string", "null"]},
            "last_observed_scan": {"type": ["string", "null"]},
            "duplicate_group_id": {
                "anyOf": [
                    {"type": "string", "pattern": "^dup_[0-9a-f]{16}$"},
                    {"type": "null"},
                ]
            },
            "duplicate_confidence": {
                "type": "string",
                "enum": ["none", "exact", "high-confidence"],
            },
        },
        "additionalProperties": False,
    }
