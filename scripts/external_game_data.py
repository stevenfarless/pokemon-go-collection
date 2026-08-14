"""Freshness-aware external Pokémon GO data framework and reviewed production adapters.

The core contract remains provider-independent. Production event/raid inputs are
human-reviewed factual metadata committed under ``external/providers``. The build
never scrapes official Pokémon GO pages. It validates source/licensing metadata,
joins referenced species to the pinned species index, preserves a committed
last-known-good snapshot on malformed refreshes, and publishes only static files.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

EXTERNAL_FRAMEWORK_VERSION = "1.1.0"
EXTERNAL_SNAPSHOT_SCHEMA_VERSION = "1.0.0"
PROVIDER_INPUT_SCHEMA_VERSION = "1.0.0"
AUTHORITY_CLASSIFICATIONS = (
    "Official",
    "Verified community data",
    "Simulation result",
    "Datamined",
    "Reported",
    "Outdated",
    "Unavailable",
)
FRESHNESS_STATES = ("fresh", "stale", "expired", "unavailable", "failed-update")
DATA_CATEGORIES = (
    "pvp",
    "raids",
    "moves",
    "events",
    "rocket",
    "max-battles",
    "mechanics",
)


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} is not a valid ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-") or "provider"


def assess_freshness(snapshot: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Calculate a deterministic freshness state from normalized snapshot metadata."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    dataset_at = _parse_timestamp(snapshot.get("dataset_timestamp"), "dataset_timestamp")
    policy = snapshot.get("freshness_policy") or {}
    max_age_hours = policy.get("max_age_hours")
    if not isinstance(max_age_hours, (int, float)) or max_age_hours <= 0:
        raise ValueError("freshness_policy.max_age_hours must be a positive number")

    valid_until_raw = snapshot.get("validity", {}).get("valid_until")
    valid_until = _parse_timestamp(valid_until_raw, "validity.valid_until") if valid_until_raw else None
    age_hours = max(0.0, (current - dataset_at).total_seconds() / 3600)
    if valid_until is not None and current > valid_until:
        state = "expired"
        reason = "validity_window_ended"
    elif age_hours > float(max_age_hours):
        state = "stale"
        reason = "dataset_exceeds_max_age"
    else:
        state = "fresh"
        reason = "within_freshness_policy"
    return {
        "state": state,
        "checked_at": _iso(current),
        "age_hours": round(age_hours, 3),
        "max_age_hours": float(max_age_hours),
        "reason": reason,
    }


def normalize_snapshot(raw: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Normalize one provider snapshot into the project-wide contract."""
    required_strings = (
        "provider",
        "source_reference",
        "dataset_timestamp",
        "data_category",
        "classification",
        "data_version",
        "schema_version",
    )
    for field in required_strings:
        if not isinstance(raw.get(field), str) or not str(raw[field]).strip():
            raise ValueError(f"External snapshot is missing required field {field!r}")
    if raw["data_category"] not in DATA_CATEGORIES:
        raise ValueError(f"Unsupported external data category: {raw['data_category']}")
    if raw["classification"] not in AUTHORITY_CLASSIFICATIONS:
        raise ValueError(f"Unsupported authority classification: {raw['classification']}")
    if raw["classification"] in {"Unavailable", "Outdated"}:
        raise ValueError("A provider payload cannot claim Unavailable/Outdated as its source classification")

    _parse_timestamp(raw["dataset_timestamp"], "dataset_timestamp")
    retrieved_at = raw.get("retrieved_at") or raw["dataset_timestamp"]
    _parse_timestamp(retrieved_at, "retrieved_at")
    license_info = raw.get("license")
    if not isinstance(license_info, Mapping) or not license_info.get("name"):
        raise ValueError("External snapshot requires explicit license metadata")
    if not isinstance(license_info.get("redistribution_permitted"), bool):
        raise ValueError("license.redistribution_permitted must be explicit")
    if not license_info["redistribution_permitted"]:
        raise ValueError("Snapshot cannot be published when redistribution is not permitted")
    join_keys = raw.get("join_keys")
    if not isinstance(join_keys, list) or not join_keys or not all(isinstance(value, str) and value for value in join_keys):
        raise ValueError("External snapshot requires one or more documented join_keys")
    facts = raw.get("facts")
    if not isinstance(facts, list):
        raise ValueError("External snapshot facts must be an array")
    if not all(isinstance(fact, Mapping) for fact in facts):
        raise ValueError("External snapshot facts must contain only objects")
    policy = raw.get("freshness_policy")
    if not isinstance(policy, Mapping) or not isinstance(policy.get("max_age_hours"), (int, float)) or policy["max_age_hours"] <= 0:
        raise ValueError("External snapshot requires freshness_policy.max_age_hours")

    validity = raw.get("validity") or {}
    if validity.get("valid_from"):
        _parse_timestamp(validity["valid_from"], "validity.valid_from")
    if validity.get("valid_until"):
        _parse_timestamp(validity["valid_until"], "validity.valid_until")

    normalized = {
        "schema_version": EXTERNAL_SNAPSHOT_SCHEMA_VERSION,
        "framework_version": EXTERNAL_FRAMEWORK_VERSION,
        "provider": str(raw["provider"]),
        "source_reference": str(raw["source_reference"]),
        "source_references": [str(value) for value in raw.get("source_references", []) if str(value).strip()],
        "retrieved_at": str(retrieved_at),
        "dataset_timestamp": str(raw["dataset_timestamp"]),
        "effective_game_context": raw.get("effective_game_context"),
        "validity": {
            "valid_from": validity.get("valid_from"),
            "valid_until": validity.get("valid_until"),
        },
        "data_category": str(raw["data_category"]),
        "classification": str(raw["classification"]),
        "data_version": str(raw["data_version"]),
        "provider_schema_version": str(raw["schema_version"]),
        "acquisition": raw.get("acquisition") or {
            "mode": "unspecified",
            "automated_source_scraping": False,
        },
        "license": {
            "name": str(license_info["name"]),
            "reference": license_info.get("reference"),
            "attribution": license_info.get("attribution"),
            "redistribution_permitted": True,
        },
        "join_keys": list(join_keys),
        "freshness_policy": {
            "max_age_hours": float(policy["max_age_hours"]),
            "on_stale": str(policy.get("on_stale") or "degrade-explicitly"),
            "on_failed_update": str(policy.get("on_failed_update") or "preserve-last-known-good"),
        },
        "facts": [dict(fact) for fact in facts],
    }
    normalized["freshness"] = assess_freshness(normalized, now=now)
    return normalized


def refresh_with_last_known_good(
    candidate: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Validate a candidate and preserve the previous valid snapshot on failure."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    try:
        normalized = normalize_snapshot(candidate, now=current)
    except (TypeError, ValueError) as error:
        event = {
            "status": "failed-update",
            "checked_at": _iso(current),
            "message": str(error),
            "published_candidate": False,
            "preserved_last_known_good": previous is not None,
        }
        if previous is None:
            return None, event
        preserved = dict(previous)
        try:
            preserved["freshness"] = assess_freshness(preserved, now=current)
        except ValueError:
            return None, event | {"preserved_last_known_good": False, "message": f"{error}; previous snapshot also failed freshness validation"}
        return preserved, event
    return normalized, {
        "status": "published",
        "checked_at": _iso(current),
        "message": "Candidate snapshot validated and replaced the previous snapshot.",
        "published_candidate": True,
        "preserved_last_known_good": False,
    }


def _known_species(repository_root: Path) -> tuple[set[int], set[str]]:
    payload = _load(repository_root / "knowledge" / "species-index.json")
    dex = {int(entry["dex"]) for entry in payload.get("entries", []) if entry.get("dex") is not None}
    species_ids = {str(entry["species_id"]) for entry in payload.get("entries", []) if entry.get("species_id")}
    return dex, species_ids


def validate_snapshot_join_keys(snapshot: Mapping[str, Any], repository_root: Path) -> None:
    """Fail closed when a provider fact references an unknown #71 species identifier."""
    known_dex, known_species_ids = _known_species(repository_root)

    def walk(value: Any, path: str = "facts") -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if key in {"dex", "pokemon_number", "boss_dex"} and child not in (None, ""):
                    try:
                        number = int(child)
                    except (TypeError, ValueError) as error:
                        raise ValueError(f"{child_path} must be an integer Pokédex number") from error
                    if number not in known_dex:
                        raise ValueError(f"{child_path} references unknown Pokédex number {number}")
                elif key in {"featured_dex", "boss_dexes"} and isinstance(child, list):
                    for index, item in enumerate(child):
                        try:
                            number = int(item)
                        except (TypeError, ValueError) as error:
                            raise ValueError(f"{child_path}[{index}] must be an integer Pokédex number") from error
                        if number not in known_dex:
                            raise ValueError(f"{child_path}[{index}] references unknown Pokédex number {number}")
                elif key == "species_id" and child not in (None, "") and str(child) not in known_species_ids:
                    raise ValueError(f"{child_path} references unknown species_id {child!r}")
                walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(snapshot.get("facts") or [])


def external_index(*, snapshots: list[Mapping[str, Any]] | None = None, generated_at: str | None = None) -> dict[str, Any]:
    items = list(snapshots or [])
    states = [str(item.get("freshness", {}).get("state") or "unavailable") for item in items]
    if any(state == "fresh" for state in states):
        overall = "fresh"
    elif any(state == "stale" for state in states):
        overall = "stale"
    elif any(state == "expired" for state in states):
        overall = "expired"
    else:
        overall = "unavailable"
    return {
        "schema_version": "1.0.0",
        "framework_version": EXTERNAL_FRAMEWORK_VERSION,
        "generated_at": generated_at,
        "overall_freshness": overall,
        "snapshot_count": len(items),
        "classifications": list(AUTHORITY_CLASSIFICATIONS),
        "data_categories": list(DATA_CATEGORIES),
        "failure_policy": {
            "malformed_candidate": "reject",
            "failed_update": "preserve-last-known-good",
            "stale_snapshot": "retain-with-explicit-stale-state",
            "no_snapshot": "degrade-to-unavailable",
        },
        "architecture": {
            "runtime_server_required": False,
            "paid_service_required": False,
            "provider_required_for_core_collection": False,
            "publication_model": "repository-hosted-static-snapshots",
            "official_site_automated_scraping": False,
        },
        "snapshots": [
            {
                "provider": item.get("provider"),
                "data_category": item.get("data_category"),
                "classification": item.get("classification"),
                "source_reference": item.get("source_reference"),
                "source_references": item.get("source_references") or [],
                "dataset_timestamp": item.get("dataset_timestamp"),
                "data_version": item.get("data_version"),
                "freshness": item.get("freshness"),
                "validity": item.get("validity"),
                "join_keys": item.get("join_keys"),
                "license": item.get("license"),
                "path": item.get("path"),
                "refresh_event": item.get("refresh_event"),
            }
            for item in items
        ],
    }


def _load_previous(repository_root: Path, filename: str) -> dict[str, Any] | None:
    path = repository_root / "external" / "last-known-good" / filename
    if not path.is_file():
        return None
    payload = _load(path)
    if payload.get("framework_version") and payload.get("freshness_policy"):
        return payload
    return normalize_snapshot(payload)


def publish_external_framework(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Publish reviewed production snapshots while keeping the core collection provider-optional."""
    providers_dir = repository_root / "external" / "providers"
    published: list[dict[str, Any]] = []
    generated_at = str(manifest.get("generated_at_utc") or _iso(datetime.now(timezone.utc)))
    now = _parse_timestamp(generated_at, "generated_at_utc") if generated_at else datetime.now(timezone.utc)

    if providers_dir.is_dir():
        for source in sorted(providers_dir.glob("*.json")):
            candidate = _load(source)
            previous = _load_previous(repository_root, source.name)
            selected, refresh_event = refresh_with_last_known_good(candidate, previous, now=now)
            if selected is None:
                continue
            validate_snapshot_join_keys(selected, repository_root)
            selected = dict(selected)
            selected["build_id"] = manifest["build_id"]
            selected["refresh_event"] = refresh_event
            filename = f"{_slug(str(selected['data_category']))}-{_slug(str(selected['provider']))}.json"
            relative = f"data/external/snapshots/{filename}"
            selected["path"] = relative
            _write(output_dir / relative, selected)
            published.append(selected)

    index = external_index(snapshots=published, generated_at=generated_at)
    index["build_id"] = manifest["build_id"]
    index["design_document"] = "docs/external-game-data.md"
    index["snapshot_contract"] = "data/external-snapshot.schema.json"
    _write(output_dir / "data" / "external" / "index.json", index)
    return index
