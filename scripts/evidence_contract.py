"""Shared trust-and-evidence contract for generated Pokémon GO resources and UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

EVIDENCE_VERSION = "1.0.0"
EVIDENCE_KINDS = (
    "canonical-owned",
    "official-current",
    "verified-community",
    "simulation",
    "calculated",
    "browser-local",
    "reported",
    "datamined",
    "outdated",
    "unknown",
)
FRESHNESS_STATES = ("fresh", "stale", "expired", "not-applicable", "unknown")
CONFIDENCE_STATES = ("high", "medium", "low", "unknown", "not-applicable")
PREREQUISITE_STATES = ("satisfied", "missing", "stale", "unsupported", "unknown")

_KIND_DEFAULTS = {
    "canonical-owned": ("Owned fact", "Poke Genie / canonical collection"),
    "official-current": ("Official current fact", "Official"),
    "verified-community": ("Verified community data", "Verified community data"),
    "simulation": ("Simulation result", "Simulation result"),
    "calculated": ("Calculated result", "Deterministic calculation"),
    "browser-local": ("User-confirmed local fact", "Browser-local user confirmation"),
    "reported": ("Reported information", "Reported"),
    "datamined": ("Datamined information", "Datamined"),
    "outdated": ("Outdated evidence", "Outdated"),
    "unknown": ("Unknown / unsupported", "Unknown"),
}


def _clean_list(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _clean_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def make_evidence(
    kind: str,
    *,
    label: str | None = None,
    authority: str | None = None,
    freshness: Mapping[str, Any] | None = None,
    confidence: Mapping[str, Any] | None = None,
    source: Mapping[str, Any] | None = None,
    assumptions: Any = None,
    rule_trace: Any = None,
    prerequisites: Any = None,
    uncertainty: Any = None,
) -> dict[str, Any]:
    """Build one normalized typed evidence object without converting unknowns to false values."""
    normalized_kind = str(kind or "unknown")
    if normalized_kind not in EVIDENCE_KINDS:
        normalized_kind = "unknown"
    default_label, default_authority = _KIND_DEFAULTS[normalized_kind]

    fresh = _clean_mapping(freshness)
    fresh_state = str(fresh.get("state") or ("not-applicable" if normalized_kind in {"canonical-owned", "simulation", "calculated", "browser-local"} else "unknown"))
    if fresh_state not in FRESHNESS_STATES:
        fresh_state = "unknown"
    freshness_value = {
        "state": fresh_state,
        "checked_at": fresh.get("checked_at"),
        "dataset_timestamp": fresh.get("dataset_timestamp"),
        "valid_until": fresh.get("valid_until"),
        "reason": fresh.get("reason"),
    }

    conf = _clean_mapping(confidence)
    confidence_state = str(conf.get("state") or ("not-applicable" if normalized_kind in {"canonical-owned", "official-current", "browser-local"} else "unknown"))
    if confidence_state not in CONFIDENCE_STATES:
        confidence_state = "unknown"
    confidence_value = {
        "state": confidence_state,
        "reason": conf.get("reason"),
    }

    normalized_prerequisites: list[dict[str, Any]] = []
    if isinstance(prerequisites, (list, tuple)):
        for raw in prerequisites:
            if not isinstance(raw, Mapping):
                continue
            state = str(raw.get("state") or "unknown")
            if state not in PREREQUISITE_STATES:
                state = "unknown"
            name = str(raw.get("name") or "prerequisite").strip() or "prerequisite"
            normalized_prerequisites.append(
                {
                    "name": name,
                    "state": state,
                    "reason": raw.get("reason"),
                    "remediation": raw.get("remediation"),
                }
            )

    return {
        "schema_version": EVIDENCE_VERSION,
        "kind": normalized_kind,
        "label": str(label or default_label),
        "authority": str(authority or default_authority),
        "freshness": freshness_value,
        "confidence": confidence_value,
        "source": _clean_mapping(source),
        "assumptions": _clean_list(assumptions),
        "rule_trace": _clean_list(rule_trace),
        "prerequisites": normalized_prerequisites,
        "uncertainty": _clean_list(uncertainty),
    }


def external_evidence(source: Mapping[str, Any] | None) -> dict[str, Any]:
    """Map normalized external-source metadata onto the shared evidence vocabulary."""
    value = _clean_mapping(source)
    classification = str(value.get("authority") or value.get("classification") or "")
    freshness = _clean_mapping(value.get("freshness"))
    freshness_state = str(freshness.get("state") or "unknown")
    if freshness_state in {"stale", "expired"}:
        kind = "outdated"
    elif classification == "Official":
        kind = "official-current"
    elif classification == "Verified community data":
        kind = "verified-community"
    elif classification == "Reported":
        kind = "reported"
    elif classification == "Datamined":
        kind = "datamined"
    else:
        kind = "unknown"

    source_value = {
        "title": value.get("source_title"),
        "url": value.get("source_reference"),
        "provider": value.get("provider"),
        "retrieved_at": value.get("retrieved_at"),
        "reviewed_at": value.get("reviewed_at"),
        "dataset_timestamp": value.get("dataset_timestamp"),
        "version": value.get("data_version"),
        "model_version": value.get("model_version"),
    }
    return make_evidence(
        kind,
        authority=classification or None,
        freshness={
            "state": freshness_state if freshness_state in FRESHNESS_STATES else "unknown",
            "checked_at": freshness.get("checked_at"),
            "dataset_timestamp": value.get("dataset_timestamp"),
            "valid_until": (_clean_mapping(value.get("validity"))).get("valid_until"),
            "reason": freshness.get("reason"),
        },
        source=source_value,
        prerequisites=[
            {
                "name": "current external source",
                "state": "satisfied" if freshness_state == "fresh" else "stale" if freshness_state in {"stale", "expired"} else "unknown",
                "reason": freshness.get("reason"),
                "remediation": "Refresh or review the external source before treating this as current." if freshness_state != "fresh" else None,
            }
        ],
        uncertainty=[] if kind != "unknown" else ["Source classification is not mapped to a supported trust category."],
    )


def owned_evidence(*, source_field: str | None = None, uncertainty: Any = None) -> dict[str, Any]:
    trace = [f"Canonical owned field: {source_field}"] if source_field else ["Canonical normalized owned record"]
    return make_evidence("canonical-owned", rule_trace=trace, uncertainty=uncertainty)


def calculated_evidence(
    *,
    label: str | None = None,
    confidence: str = "high",
    confidence_reason: str | None = None,
    assumptions: Any = None,
    rule_trace: Any = None,
    prerequisites: Any = None,
    uncertainty: Any = None,
    model_version: str | None = None,
) -> dict[str, Any]:
    return make_evidence(
        "calculated",
        label=label,
        confidence={"state": confidence, "reason": confidence_reason},
        source={"model_version": model_version} if model_version else {},
        assumptions=assumptions,
        rule_trace=rule_trace,
        prerequisites=prerequisites,
        uncertainty=uncertainty,
    )


def simulation_evidence(
    *,
    model_version: str,
    confidence: str = "unknown",
    confidence_reason: str | None = None,
    assumptions: Any = None,
    prerequisites: Any = None,
    uncertainty: Any = None,
) -> dict[str, Any]:
    return make_evidence(
        "simulation",
        confidence={"state": confidence, "reason": confidence_reason},
        source={"model_version": model_version},
        assumptions=assumptions,
        prerequisites=prerequisites,
        uncertainty=uncertainty,
    )


def unknown_evidence(reason: str, remediation: str | None = None) -> dict[str, Any]:
    return make_evidence(
        "unknown",
        prerequisites=[{"name": "required evidence", "state": "missing", "reason": reason, "remediation": remediation}],
        uncertainty=[reason],
    )


def schema() -> dict[str, Any]:
    prerequisite = {
        "type": "object",
        "required": ["name", "state", "reason", "remediation"],
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "state": {"enum": list(PREREQUISITE_STATES)},
            "reason": {"type": ["string", "null"]},
            "remediation": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://stevenfarless.github.io/pokemon-go-collection/data/evidence.schema.json",
        "type": "object",
        "required": ["schema_version", "kind", "label", "authority", "freshness", "confidence", "source", "assumptions", "rule_trace", "prerequisites", "uncertainty"],
        "properties": {
            "schema_version": {"const": EVIDENCE_VERSION},
            "kind": {"enum": list(EVIDENCE_KINDS)},
            "label": {"type": "string", "minLength": 1},
            "authority": {"type": "string", "minLength": 1},
            "freshness": {
                "type": "object",
                "required": ["state", "checked_at", "dataset_timestamp", "valid_until", "reason"],
                "properties": {
                    "state": {"enum": list(FRESHNESS_STATES)},
                    "checked_at": {"type": ["string", "null"]},
                    "dataset_timestamp": {"type": ["string", "null"]},
                    "valid_until": {"type": ["string", "null"]},
                    "reason": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
            "confidence": {
                "type": "object",
                "required": ["state", "reason"],
                "properties": {"state": {"enum": list(CONFIDENCE_STATES)}, "reason": {"type": ["string", "null"]}},
                "additionalProperties": False,
            },
            "source": {"type": "object"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "rule_trace": {"type": "array", "items": {"type": "string"}},
            "prerequisites": {"type": "array", "items": prerequisite},
            "uncertainty": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    }


def registry() -> dict[str, Any]:
    return {
        "schema_version": EVIDENCE_VERSION,
        "evidence_schema": "data/evidence.schema.json",
        "kinds": {
            kind: {"label": _KIND_DEFAULTS[kind][0], "authority": _KIND_DEFAULTS[kind][1]}
            for kind in EVIDENCE_KINDS
        },
        "freshness_states": list(FRESHNESS_STATES),
        "confidence_states": list(CONFIDENCE_STATES),
        "prerequisite_states": list(PREREQUISITE_STATES),
        "rules": {
            "unknown_is_not_false": True,
            "freshness_is_not_confidence": True,
            "simulation_is_not_official_fact": True,
            "stale_external_evidence_is_not_current": True,
            "consequential_claims_require_visible_evidence": True,
            "irreversible_or_high_cost_actions_require_prerequisites": True,
        },
        "remediation": {
            "missing-owned-fact": "Rescan the Pokémon or provide the missing supported owned field.",
            "stale-current-data": "Refresh or review the current external source.",
            "unsupported-mechanic": "Wait for a reviewed mechanics source or treat the answer as unavailable.",
            "browser-local-unknown": "Confirm the attribute locally if it matters to the decision.",
        },
    }


def publish(output_dir: Path) -> dict[str, Any]:
    payload = registry()
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    (output_dir / "data" / "evidence-contract.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (output_dir / "data" / "evidence.schema.json").write_text(json.dumps(schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return payload


__all__ = [
    "EVIDENCE_VERSION",
    "EVIDENCE_KINDS",
    "FRESHNESS_STATES",
    "CONFIDENCE_STATES",
    "PREREQUISITE_STATES",
    "make_evidence",
    "external_evidence",
    "owned_evidence",
    "calculated_evidence",
    "simulation_evidence",
    "unknown_evidence",
    "schema",
    "registry",
    "publish",
]
