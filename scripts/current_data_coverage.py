"""Coverage and fail-closed selection for rotating Pokémon GO data categories."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from . import external_game_data
except ImportError:
    import external_game_data

COVERAGE_CONTRACT_VERSION = "1.0.0"
EXPANDED_CATEGORIES = ("gbl", "research", "eggs", "ditto")

CATEGORY_COVERAGE: dict[str, dict[str, Any]] = {
    "events": {
        "status": "available-path",
        "authority_preference": "Official",
        "production_acquisition_path": "Reviewed official event/news facts committed under external/providers; no runtime scraping.",
    },
    "raids": {
        "status": "available-path",
        "authority_preference": "Official",
        "production_acquisition_path": "Reviewed official raid-rotation facts committed under external/providers; no runtime scraping.",
    },
    "moves": {
        "status": "available-path",
        "authority_preference": "Official",
        "production_acquisition_path": "Reviewed official move-change or event-acquisition facts may be committed as normalized provider snapshots after license/source review.",
    },
    "gbl": {
        "status": "available-path",
        "authority_preference": "Official",
        "production_acquisition_path": "Reviewed official GO Battle League season/cup rules and dates may be normalized into a committed static snapshot.",
    },
    "rocket": {
        "status": "unavailable",
        "authority_preference": "Official then redistribution-reviewed verified community data",
        "unavailable_reason": "No complete, redistribution-reviewed production source for the rotating Grunt/Leader/Giovanni lineup is adopted yet.",
    },
    "max-battles": {
        "status": "available-path",
        "authority_preference": "Official",
        "production_acquisition_path": "Reviewed official Max Battle and Max Monday rotations may be normalized into committed static snapshots.",
    },
    "research": {
        "status": "unavailable",
        "authority_preference": "Official then redistribution-reviewed verified community data",
        "unavailable_reason": "No complete, maintainable, redistribution-reviewed current task/reward source is adopted yet.",
    },
    "eggs": {
        "status": "unavailable",
        "authority_preference": "Official then redistribution-reviewed verified community data",
        "unavailable_reason": "No complete, maintainable, redistribution-reviewed current egg-pool source is adopted yet.",
    },
    "ditto": {
        "status": "unavailable",
        "authority_preference": "Official then redistribution-reviewed verified community data",
        "unavailable_reason": "No reviewed current source for a complete Ditto disguise list is adopted yet.",
    },
    "pvp": {
        "status": "available-path",
        "authority_preference": "Versioned simulation/current-meta sources",
        "production_acquisition_path": "Current PvP/meta inputs remain a distinct reviewed simulation/current-data layer and never become official facts by implication.",
    },
    "mechanics": {
        "status": "available-path",
        "authority_preference": "Official",
        "production_acquisition_path": "Stable/current mechanic coverage is published separately at data/mechanics/index.json and linked as a prerequisite rather than treated as a rotating snapshot.",
    },
}


def install() -> tuple[str, ...]:
    """Extend the provider-independent external-data category contract."""
    categories = tuple(dict.fromkeys((*external_game_data.DATA_CATEGORIES, *EXPANDED_CATEGORIES)))
    external_game_data.DATA_CATEGORIES = categories
    return categories


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def select_current_snapshot(
    snapshots: Iterable[Mapping[str, Any]],
    category: str,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return the newest fresh snapshot or an explicit blocker.

    Stale/expired snapshots remain valid provenance, but they never satisfy a
    current-data prerequisite.
    """
    install()
    if category not in external_game_data.DATA_CATEGORIES:
        raise ValueError(f"Unsupported current-data category: {category}")
    matching = [dict(item) for item in snapshots if item.get("data_category") == category]
    if not matching:
        coverage = CATEGORY_COVERAGE.get(category, {})
        return None, {
            "state": "unavailable",
            "reason": coverage.get("unavailable_reason") or "no-reviewed-snapshot",
            "category": category,
            "current_claim_allowed": False,
        }

    checked: list[dict[str, Any]] = []
    for item in matching:
        candidate = dict(item)
        try:
            candidate["freshness"] = external_game_data.assess_freshness(candidate, now=now)
        except ValueError:
            candidate["freshness"] = {
                "state": "unavailable",
                "reason": "invalid-freshness-metadata",
            }
        checked.append(candidate)

    fresh = [item for item in checked if item.get("freshness", {}).get("state") == "fresh"]
    if fresh:
        selected = max(fresh, key=lambda item: _timestamp(item.get("dataset_timestamp")))
        return selected, {
            "state": "fresh",
            "reason": "fresh-reviewed-snapshot",
            "category": category,
            "current_claim_allowed": True,
            "provider": selected.get("provider"),
            "dataset_timestamp": selected.get("dataset_timestamp"),
            "source_reference": selected.get("source_reference"),
        }

    observed_states = sorted({str(item.get("freshness", {}).get("state") or "unavailable") for item in checked})
    blocker_state = "expired" if "expired" in observed_states else ("stale" if "stale" in observed_states else "unavailable")
    return None, {
        "state": blocker_state,
        "reason": "no-fresh-snapshot",
        "category": category,
        "current_claim_allowed": False,
        "observed_states": observed_states,
    }


def coverage_payload() -> dict[str, Any]:
    categories = install()
    coverage: dict[str, Any] = {}
    for category in categories:
        entry = dict(CATEGORY_COVERAGE.get(category) or {})
        if not entry:
            entry = {
                "status": "unavailable",
                "authority_preference": "Reviewed source required",
                "unavailable_reason": "No production acquisition path has been documented for this category.",
            }
        coverage[category] = entry
    return coverage


def publish_metadata(output_dir: Path) -> dict[str, Any]:
    """Augment the generated external index with category-level coverage."""
    path = output_dir / "data" / "external" / "index.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["coverage_contract_version"] = COVERAGE_CONTRACT_VERSION
    payload["category_coverage"] = coverage_payload()
    payload["consumer_contract"] = {
        "current_claim_requires": "fresh normalized snapshot",
        "stale_behavior": "retain as provenance/reference; block current recommendation",
        "expired_behavior": "retain as provenance/reference; block current recommendation",
        "unknown_rate_policy": "never fabricate encounter/rate probabilities",
        "join_key_policy": "normalize to canonical knowledge identifiers, never provider-specific display strings",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return payload


def patch_external_schema(output_dir: Path) -> None:
    """Extend the generated snapshot schema after the base schemas are published."""
    install()
    path = output_dir / "data" / "external-snapshot.schema.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["properties"]["data_category"]["enum"] = list(external_game_data.DATA_CATEGORIES)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


__all__ = [
    "COVERAGE_CONTRACT_VERSION",
    "EXPANDED_CATEGORIES",
    "CATEGORY_COVERAGE",
    "install",
    "select_current_snapshot",
    "coverage_payload",
    "publish_metadata",
    "patch_external_schema",
]
