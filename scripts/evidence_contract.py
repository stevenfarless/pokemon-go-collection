"""Shared trust-and-evidence contract for generated Pokémon GO resources and UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

try:
    from . import manifest_registry
except ImportError:
    import manifest_registry

EVIDENCE_VERSION = "1.0.0"
EVIDENCE_INDEX_VERSION = "1.0.0"
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


def _load(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


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
    freshness_default = (
        "not-applicable"
        if normalized_kind in {"canonical-owned", "simulation", "calculated", "browser-local"}
        else "unknown"
    )
    fresh_state = str(fresh.get("state") or freshness_default)
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
    confidence_default = (
        "not-applicable"
        if normalized_kind in {"canonical-owned", "official-current", "browser-local"}
        else "unknown"
    )
    confidence_state = str(conf.get("state") or confidence_default)
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
    prerequisite_state = (
        "satisfied"
        if freshness_state == "fresh"
        else "stale"
        if freshness_state in {"stale", "expired"}
        else "unknown"
    )
    return make_evidence(
        kind,
        authority=classification or None,
        freshness={
            "state": freshness_state if freshness_state in FRESHNESS_STATES else "unknown",
            "checked_at": freshness.get("checked_at"),
            "dataset_timestamp": value.get("dataset_timestamp"),
            "valid_until": _clean_mapping(value.get("validity")).get("valid_until"),
            "reason": freshness.get("reason"),
        },
        source=source_value,
        prerequisites=[
            {
                "name": "current external source",
                "state": prerequisite_state,
                "reason": freshness.get("reason"),
                "remediation": (
                    "Refresh or review the external source before treating this as current."
                    if freshness_state != "fresh"
                    else None
                ),
            }
        ],
        uncertainty=(
            []
            if kind != "unknown"
            else ["Source classification is not mapped to a supported trust category."]
        ),
    )


def owned_evidence(*, source_field: str | None = None, uncertainty: Any = None) -> dict[str, Any]:
    trace = (
        [f"Canonical owned field: {source_field}"]
        if source_field
        else ["Canonical normalized owned record"]
    )
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
        prerequisites=[
            {
                "name": "required evidence",
                "state": "missing",
                "reason": reason,
                "remediation": remediation,
            }
        ],
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
        "required": [
            "schema_version",
            "kind",
            "label",
            "authority",
            "freshness",
            "confidence",
            "source",
            "assumptions",
            "rule_trace",
            "prerequisites",
            "uncertainty",
        ],
        "properties": {
            "schema_version": {"const": EVIDENCE_VERSION},
            "kind": {"enum": list(EVIDENCE_KINDS)},
            "label": {"type": "string", "minLength": 1},
            "authority": {"type": "string", "minLength": 1},
            "freshness": {
                "type": "object",
                "required": [
                    "state",
                    "checked_at",
                    "dataset_timestamp",
                    "valid_until",
                    "reason",
                ],
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
                "properties": {
                    "state": {"enum": list(CONFIDENCE_STATES)},
                    "reason": {"type": ["string", "null"]},
                },
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


def index_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://stevenfarless.github.io/pokemon-go-collection/data/evidence-index.schema.json",
        "type": "object",
        "required": ["schema_version", "evidence_schema", "entries"],
        "properties": {
            "schema_version": {"const": EVIDENCE_INDEX_VERSION},
            "evidence_schema": {"const": "data/evidence.schema.json"},
            "entries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "id",
                        "surface",
                        "title",
                        "route",
                        "resource",
                        "consequential",
                        "evidence",
                    ],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "surface": {"type": "string", "minLength": 1},
                        "title": {"type": "string", "minLength": 1},
                        "route": {"type": "string", "minLength": 1},
                        "resource": {"type": "string", "minLength": 1},
                        "consequential": {"type": "boolean"},
                        "evidence": {"type": "object"},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    }


def registry() -> dict[str, Any]:
    return {
        "schema_version": EVIDENCE_VERSION,
        "evidence_schema": "data/evidence.schema.json",
        "evidence_index": "data/evidence-index.json",
        "kinds": {
            kind: {
                "label": _KIND_DEFAULTS[kind][0],
                "authority": _KIND_DEFAULTS[kind][1],
            }
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
            "unsupported-mechanic": (
                "Wait for a reviewed mechanics source or treat the answer as unavailable."
            ),
            "browser-local-unknown": (
                "Confirm the attribute locally if it matters to the decision."
            ),
        },
    }


def _external_by_path(output_dir: Path) -> dict[str, dict[str, Any]]:
    payload = _load(output_dir / "data" / "external" / "index.json", {}) or {}
    return {
        str(item.get("path")): dict(item)
        for item in payload.get("snapshots") or []
        if isinstance(item, Mapping) and item.get("path")
    }


def _today_evidence(
    card: Mapping[str, Any],
    external: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    source_path = str(card.get("source_resource") or "")
    snapshot = external.get(source_path)
    if card.get("kind") == "current" or snapshot:
        source = dict(snapshot or {})
        source.setdefault("source_reference", card.get("source_reference"))
        source.setdefault("provider", card.get("provider"))
        source.setdefault("dataset_timestamp", card.get("dataset_timestamp"))
        if card.get("freshness"):
            source.setdefault("freshness", card.get("freshness"))
        return external_evidence(source)

    warnings = _clean_list(card.get("warnings"))
    consequential = (
        card.get("reversibility") == "review-before-action"
        or bool(card.get("cost"))
        or bool(card.get("safety_critical"))
    )
    prerequisites = [
        {
            "name": "canonical owned collection inputs",
            "state": "satisfied",
            "reason": f"Derived from {source_path or 'published collection resources'}.",
            "remediation": None,
        }
    ]
    if consequential:
        prerequisites.append(
            {
                "name": "final in-game state and eligibility",
                "state": "unknown",
                "reason": (
                    "The static companion cannot confirm the final Pokémon GO screen "
                    "or resource balance at action time."
                ),
                "remediation": (
                    "Verify the exact Pokémon, cost, eligibility, and current in-game "
                    "state before committing the action."
                ),
            }
        )
    return calculated_evidence(
        label=str(card.get("evidence_layer") or "Calculated collection guidance"),
        confidence="medium" if warnings else "high",
        confidence_reason=(
            "One or more owned-data warnings reduce decision confidence."
            if warnings
            else "The published deterministic inputs required by this card are available."
        ),
        rule_trace=_clean_list(card.get("why")),
        prerequisites=prerequisites,
        uncertainty=warnings,
    )


def annotate_today(output_dir: Path) -> list[dict[str, Any]]:
    path = output_dir / "data" / "today.json"
    payload = _load(path)
    if not isinstance(payload, Mapping):
        return []
    value = dict(payload)
    external = _external_by_path(output_dir)
    entries: dict[str, dict[str, Any]] = {}

    def annotate(card: Any) -> Any:
        if not isinstance(card, Mapping):
            return card
        item = dict(card)
        evidence = _today_evidence(item, external)
        item["evidence"] = evidence
        card_id = str(item.get("id") or "")
        if card_id:
            entries[card_id] = {
                "id": f"today:{card_id}",
                "surface": "today-card",
                "title": str(item.get("title") or card_id),
                "route": str(item.get("route") or "today.html"),
                "resource": "data/today.json",
                "consequential": bool(
                    item.get("safety_critical")
                    or item.get("cost")
                    or item.get("reversibility") == "review-before-action"
                ),
                "evidence": evidence,
            }
        return item

    value["top_actions"] = [annotate(card) for card in value.get("top_actions") or []]
    sections = dict(value.get("sections") or {})
    for key, section in list(sections.items()):
        if not isinstance(section, Mapping):
            continue
        section_value = dict(section)
        if isinstance(section_value.get("cards"), list):
            section_value["cards"] = [
                annotate(card) for card in section_value.get("cards") or []
            ]
        sections[key] = section_value
    value["sections"] = sections
    value["evidence_contract"] = "data/evidence-contract.json"
    _write(path, value)
    return sorted(entries.values(), key=lambda item: item["id"])


def annotate_event_calendar(output_dir: Path) -> list[dict[str, Any]]:
    path = output_dir / "data" / "event-calendar.json"
    payload = _load(path)
    if not isinstance(payload, Mapping):
        return []
    value = dict(payload)
    entries: list[dict[str, Any]] = []

    def annotate(item: Any, surface: str) -> Any:
        if not isinstance(item, Mapping):
            return item
        result = dict(item)
        evidence = external_evidence(_clean_mapping(result.get("source")))
        prerequisites = list(evidence.get("prerequisites") or [])
        if surface == "event-deadline":
            exact = result.get("exact_owned_records") or []
            prerequisites.append(
                {
                    "name": "exact owned eligibility",
                    "state": "satisfied" if exact else "unknown",
                    "reason": (
                        "At least one exact owned record is linked for review."
                        if exact
                        else "No exact owned record is linked to this deadline."
                    ),
                    "remediation": (
                        None
                        if exact
                        else "Open the related planner and confirm an eligible owned Pokémon."
                    ),
                }
            )
            prerequisites.append(
                {
                    "name": "final in-game confirmation",
                    "state": "unknown",
                    "reason": result.get("manual_confirmation")
                    or "Eligibility can change outside the static export.",
                    "remediation": "Confirm the deadline and exact action in Pokémon GO before acting.",
                }
            )
        evidence["prerequisites"] = prerequisites
        result["evidence"] = evidence
        item_id = str(result.get("id") or "")
        if item_id:
            entries.append(
                {
                    "id": f"event-calendar:{item_id}",
                    "surface": surface,
                    "title": str(result.get("title") or item_id),
                    "route": str(result.get("route") or "event-calendar.html"),
                    "resource": "data/event-calendar.json",
                    "consequential": surface == "event-deadline",
                    "evidence": evidence,
                }
            )
        return result

    value["events"] = [annotate(item, "event-window") for item in value.get("events") or []]
    value["deadlines"] = [
        annotate(item, "event-deadline") for item in value.get("deadlines") or []
    ]
    value["evidence_contract"] = "data/evidence-contract.json"
    _write(path, value)
    return entries


def _page_entries(output_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    page_specs = (
        (
            "evolution-lab.html",
            "Evolution Lab evidence",
            "data/evolution-lab.json",
            calculated_evidence(
                label="Calculated evolution guidance",
                confidence="medium",
                confidence_reason=(
                    "Exact owned inputs are deterministic, while current move windows "
                    "still require fresh external evidence."
                ),
                prerequisites=[
                    {
                        "name": "exact owned evolution inputs",
                        "state": "satisfied",
                        "reason": "The lab joins exact canonical owned records.",
                        "remediation": None,
                    },
                    {
                        "name": "current move/event window when claimed",
                        "state": "unknown",
                        "reason": "A current window must be backed by a fresh reviewed snapshot.",
                        "remediation": "Confirm the current window and final evolution in Pokémon GO.",
                    },
                ],
                uncertainty=[
                    "Irreversible evolution should be confirmed in-game before execution."
                ],
            ),
        ),
        (
            "hyper-training.html",
            "Hyper Training evidence",
            "data/hyper-training.json",
            calculated_evidence(
                label="Calculated Hyper Training guidance",
                confidence="medium",
                confidence_reason=(
                    "Projected IV/CP consequences are deterministic when exact inputs "
                    "exist; local Bottle Cap and completion state are user-confirmed."
                ),
                prerequisites=[
                    {
                        "name": "exact owned IV inputs",
                        "state": "satisfied",
                        "reason": "Exact canonical IVs are required for projections.",
                        "remediation": None,
                    },
                    {
                        "name": "current local Bottle Cap and training state",
                        "state": "unknown",
                        "reason": "These values live only in browser-local user state.",
                        "remediation": "Confirm the local state and the final in-game action.",
                    },
                ],
                uncertainty=["Hyper Training actions may consume scarce resources."],
            ),
        ),
        (
            "raid-readiness.html",
            "Raid Readiness simulation evidence",
            "data/raid-readiness.json",
            simulation_evidence(
                model_version="owned-roster-readiness-estimator",
                confidence="unknown",
                confidence_reason=(
                    "Runtime confidence depends on exact owned moves and explicit boss assumptions."
                ),
                assumptions=[
                    "Boss HP, defense, timer, party size, and battle multipliers are explicit model inputs.",
                    "The estimator is not an official raid result or guarantee.",
                ],
                prerequisites=[
                    {
                        "name": "fresh current boss identity",
                        "state": "unknown",
                        "reason": "Current boss claims require a fresh external raid snapshot.",
                        "remediation": "Refresh or review current raid data.",
                    },
                    {
                        "name": "explicit boss/model assumptions",
                        "state": "unknown",
                        "reason": "The static source does not silently invent missing boss inputs.",
                        "remediation": "Review and enter the required model assumptions.",
                    },
                ],
                uncertainty=[
                    "Exact PvE move power/cooldown is not silently invented when unsupported."
                ],
            ),
        ),
    )
    for route, title, resource, evidence in page_specs:
        if not (output_dir / route).is_file() and not (output_dir / resource).is_file():
            continue
        entries.append(
            {
                "id": f"page:{route}",
                "surface": "page",
                "title": title,
                "route": route,
                "resource": resource,
                "consequential": True,
                "evidence": evidence,
            }
        )
    return entries


def publish(output_dir: Path) -> dict[str, Any]:
    """Publish the trust vocabulary, annotate consequential resources, and index UI evidence."""
    contract = registry()
    _write(output_dir / "data" / "evidence-contract.json", contract)
    _write(output_dir / "data" / "evidence.schema.json", schema())

    entries = [
        *annotate_today(output_dir),
        *annotate_event_calendar(output_dir),
        *_page_entries(output_dir),
    ]
    index = {
        "schema_version": EVIDENCE_INDEX_VERSION,
        "evidence_schema": "data/evidence.schema.json",
        "entries": sorted(entries, key=lambda item: item["id"]),
    }
    _write(output_dir / "data" / "evidence-index.json", index)
    _write(output_dir / "data" / "evidence-index.schema.json", index_schema())

    manifest_registry._SCHEMA_MAP["data/evidence-index.json"] = (
        "data/evidence-index.schema.json"
    )
    manifest_registry._STABLE_NAMES.update(
        {
            "data/evidence-contract.json": "evidence_contract",
            "data/evidence.schema.json": "evidence_schema",
            "data/evidence-index.json": "evidence_index",
            "data/evidence-index.schema.json": "evidence_index_schema",
        }
    )
    return {"contract": contract, "index": index}


__all__ = [
    "EVIDENCE_VERSION",
    "EVIDENCE_INDEX_VERSION",
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
    "index_schema",
    "registry",
    "annotate_today",
    "annotate_event_calendar",
    "publish",
]
