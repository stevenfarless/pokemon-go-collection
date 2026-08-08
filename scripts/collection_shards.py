"""Generate and validate bounded, build-scoped collection shards."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

SHARD_SCHEMA_VERSION = "1.0.0"
INDEX_SCHEMA_VERSION = "1.0.0"
DEFAULT_TARGET_BYTES = 700 * 1024
HARD_MAX_BYTES = 900 * 1024
SHARD_DIRECTORY = "data/pokemon"
INDEX_PATH = "data/pokemon-index.json"
SHARD_SCHEMA_PATH = "data/pokemon-shard.schema.json"
INDEX_SCHEMA_PATH = "data/pokemon-index.schema.json"


def _json_text(payload: Any, *, compact: bool = True) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":") if compact else None,
        indent=None if compact else 2,
    ) + "\n"


def _write_json(path: Path, payload: Any, *, compact: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_text(payload, compact=compact), encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shard_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://stevenfarless.github.io/pokemon-go-collection/data/pokemon-shard.schema.json",
        "title": "Pokémon GO collection shard",
        "type": "object",
        "required": [
            "schema_version",
            "build_id",
            "normalized_schema_version",
            "canonical_dataset",
            "shard_number",
            "record_count",
            "first_record_id",
            "last_record_id",
            "records",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": SHARD_SCHEMA_VERSION},
            "build_id": {"type": "string", "pattern": "^[0-9a-f]{12}$"},
            "normalized_schema_version": {"type": "string", "minLength": 1},
            "canonical_dataset": {"type": "string", "const": "data/pokemon.json"},
            "shard_number": {"type": "integer", "minimum": 1},
            "record_count": {"type": "integer", "minimum": 1},
            "first_record_id": {"type": "string", "pattern": "^pgc_[0-9a-f]{20}$"},
            "last_record_id": {"type": "string", "pattern": "^pgc_[0-9a-f]{20}$"},
            "records": {"type": "array", "minItems": 1, "items": {"type": "object"}},
        },
        "additionalProperties": False,
    }


def index_schema() -> dict[str, Any]:
    shard = {
        "type": "object",
        "required": [
            "number",
            "path",
            "byte_size",
            "sha256",
            "record_count",
            "first_record_id",
            "last_record_id",
        ],
        "properties": {
            "number": {"type": "integer", "minimum": 1},
            "path": {"type": "string", "pattern": "^data/pokemon/chunk-[0-9]{4}\\.json$"},
            "byte_size": {"type": "integer", "minimum": 1, "maximum": HARD_MAX_BYTES},
            "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "record_count": {"type": "integer", "minimum": 1},
            "first_record_id": {"type": "string", "pattern": "^pgc_[0-9a-f]{20}$"},
            "last_record_id": {"type": "string", "pattern": "^pgc_[0-9a-f]{20}$"},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://stevenfarless.github.io/pokemon-go-collection/data/pokemon-index.schema.json",
        "title": "Pokémon GO collection shard index",
        "type": "object",
        "required": [
            "schema_version",
            "build_id",
            "normalized_schema_version",
            "canonical_dataset",
            "normalized_record_count",
            "strategy",
            "shard_count",
            "shards",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": INDEX_SCHEMA_VERSION},
            "build_id": {"type": "string", "pattern": "^[0-9a-f]{12}$"},
            "normalized_schema_version": {"type": "string", "minLength": 1},
            "canonical_dataset": {"type": "string", "const": "data/pokemon.json"},
            "normalized_record_count": {"type": "integer", "minimum": 1},
            "strategy": {
                "type": "object",
                "required": ["ordering", "target_bytes", "hard_max_bytes"],
                "properties": {
                    "ordering": {"type": "string", "const": "canonical-record-order"},
                    "target_bytes": {"type": "integer", "minimum": 1},
                    "hard_max_bytes": {"type": "integer", "const": HARD_MAX_BYTES},
                },
                "additionalProperties": False,
            },
            "shard_count": {"type": "integer", "minimum": 1},
            "shards": {"type": "array", "minItems": 1, "items": shard},
        },
        "additionalProperties": False,
    }


def _record_id(record: Mapping[str, Any]) -> str:
    value = record.get("identity", {}).get("record_id")
    if not isinstance(value, str) or not value:
        raise ValueError("Cannot shard a canonical record without identity.record_id")
    return value


def _shard_payload(
    records: Sequence[Mapping[str, Any]],
    *,
    build_id: str,
    normalized_schema_version: str,
    number: int,
) -> dict[str, Any]:
    return {
        "schema_version": SHARD_SCHEMA_VERSION,
        "build_id": build_id,
        "normalized_schema_version": normalized_schema_version,
        "canonical_dataset": "data/pokemon.json",
        "shard_number": number,
        "record_count": len(records),
        "first_record_id": _record_id(records[0]),
        "last_record_id": _record_id(records[-1]),
        "records": list(records),
    }


def _serialized_size(payload: Any) -> int:
    return len(_json_text(payload).encode("utf-8"))


def _partition_records(
    records: Sequence[Mapping[str, Any]],
    *,
    build_id: str,
    normalized_schema_version: str,
    target_bytes: int,
    hard_max_bytes: int,
) -> list[list[Mapping[str, Any]]]:
    if target_bytes <= 0 or target_bytes > hard_max_bytes:
        raise ValueError("Shard target must be positive and no greater than the hard maximum")

    shards: list[list[Mapping[str, Any]]] = []
    current: list[Mapping[str, Any]] = []
    number = 1
    for record in records:
        candidate = [*current, record]
        payload = _shard_payload(
            candidate,
            build_id=build_id,
            normalized_schema_version=normalized_schema_version,
            number=number,
        )
        candidate_size = _serialized_size(payload)
        if current and candidate_size > target_bytes:
            shards.append(current)
            number += 1
            current = [record]
            single = _shard_payload(
                current,
                build_id=build_id,
                normalized_schema_version=normalized_schema_version,
                number=number,
            )
            if _serialized_size(single) > hard_max_bytes:
                raise ValueError(f"Canonical record {_record_id(record)} exceeds the shard hard maximum")
        else:
            if candidate_size > hard_max_bytes:
                raise ValueError(f"Canonical record {_record_id(record)} exceeds the shard hard maximum")
            current = candidate
    if current:
        shards.append(current)
    return shards


def publish_collection_shards(
    output_dir: Path,
    manifest: Mapping[str, Any],
    *,
    target_bytes: int = DEFAULT_TARGET_BYTES,
    hard_max_bytes: int = HARD_MAX_BYTES,
) -> dict[str, Any]:
    """Publish deterministic bounded shards and their compact discovery index."""
    payload_path = output_dir / "data" / "pokemon.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    records = payload.get("records") or []
    if not records:
        raise ValueError("Canonical pokemon.json has no records to shard")

    build_id = str(manifest["build_id"])
    normalized_schema_version = str(manifest["schema_version"])
    if payload.get("manifest", {}).get("build_id") != build_id:
        raise ValueError("Canonical pokemon.json and manifest build IDs differ before sharding")

    shard_dir = output_dir / SHARD_DIRECTORY
    if shard_dir.exists():
        shutil.rmtree(shard_dir)
    shard_dir.mkdir(parents=True)

    shard_contract = shard_schema()
    index_contract = index_schema()
    Draft202012Validator.check_schema(shard_contract)
    Draft202012Validator.check_schema(index_contract)
    _write_json(output_dir / SHARD_SCHEMA_PATH, shard_contract, compact=False)
    _write_json(output_dir / INDEX_SCHEMA_PATH, index_contract, compact=False)

    groups = _partition_records(
        records,
        build_id=build_id,
        normalized_schema_version=normalized_schema_version,
        target_bytes=target_bytes,
        hard_max_bytes=hard_max_bytes,
    )

    index_entries: list[dict[str, Any]] = []
    for number, group in enumerate(groups, start=1):
        relative = f"{SHARD_DIRECTORY}/chunk-{number:04d}.json"
        path = output_dir / relative
        shard_payload = _shard_payload(
            group,
            build_id=build_id,
            normalized_schema_version=normalized_schema_version,
            number=number,
        )
        _write_json(path, shard_payload)
        byte_size = path.stat().st_size
        if byte_size > hard_max_bytes:
            raise ValueError(f"Shard {relative} exceeds hard maximum: {byte_size} > {hard_max_bytes}")
        index_entries.append(
            {
                "number": number,
                "path": relative,
                "byte_size": byte_size,
                "sha256": _sha256(path),
                "record_count": len(group),
                "first_record_id": _record_id(group[0]),
                "last_record_id": _record_id(group[-1]),
            }
        )

    index = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "build_id": build_id,
        "normalized_schema_version": normalized_schema_version,
        "canonical_dataset": "data/pokemon.json",
        "normalized_record_count": len(records),
        "strategy": {
            "ordering": "canonical-record-order",
            "target_bytes": target_bytes,
            "hard_max_bytes": hard_max_bytes,
        },
        "shard_count": len(index_entries),
        "shards": index_entries,
    }
    _write_json(output_dir / INDEX_PATH, index, compact=False)
    validate_collection_shards(output_dir, payload=payload, index=index)
    return index


def validate_collection_shards(
    output_dir: Path,
    *,
    payload: Mapping[str, Any] | None = None,
    index: Mapping[str, Any] | None = None,
) -> None:
    """Prove that shards reconstruct the canonical current-build record sequence exactly."""
    canonical = payload or json.loads((output_dir / "data" / "pokemon.json").read_text(encoding="utf-8"))
    shard_index = index or json.loads((output_dir / INDEX_PATH).read_text(encoding="utf-8"))
    canonical_records = list(canonical["records"])
    canonical_ids = [_record_id(record) for record in canonical_records]
    build_id = canonical["manifest"]["build_id"]

    if shard_index["build_id"] != build_id:
        raise ValueError("Shard index belongs to a different build")
    if shard_index["normalized_record_count"] != len(canonical_records):
        raise ValueError("Shard index normalized count differs from canonical data")
    if shard_index["shard_count"] != len(shard_index["shards"]):
        raise ValueError("Shard index count does not match its entries")

    reconstructed: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for expected_number, entry in enumerate(shard_index["shards"], start=1):
        if entry["number"] != expected_number:
            raise ValueError("Shard index numbers are not contiguous")
        relative = entry["path"]
        if relative in seen_paths:
            raise ValueError("Shard index contains a duplicate path")
        seen_paths.add(relative)
        path = output_dir / relative
        if not path.is_file():
            raise ValueError(f"Shard index references a missing file: {relative}")
        if path.stat().st_size != entry["byte_size"] or entry["byte_size"] > HARD_MAX_BYTES:
            raise ValueError(f"Shard byte-size invariant failed: {relative}")
        if _sha256(path) != entry["sha256"]:
            raise ValueError(f"Shard checksum invariant failed: {relative}")

        shard = json.loads(path.read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(shard_schema()).iter_errors(shard))
        if errors:
            raise ValueError(f"Shard schema failure in {relative}: {errors[0].message}")
        if shard["build_id"] != build_id:
            raise ValueError(f"Shard {relative} belongs to a different build")
        records = shard["records"]
        if len(records) != entry["record_count"] or len(records) != shard["record_count"]:
            raise ValueError(f"Shard record-count invariant failed: {relative}")
        if _record_id(records[0]) != entry["first_record_id"] or _record_id(records[-1]) != entry["last_record_id"]:
            raise ValueError(f"Shard record-range invariant failed: {relative}")
        reconstructed.extend(records)

    reconstructed_ids = [_record_id(record) for record in reconstructed]
    if len(reconstructed_ids) != len(set(reconstructed_ids)):
        raise ValueError("Shard union contains duplicate canonical record IDs")
    if reconstructed_ids != canonical_ids:
        raise ValueError("Shard union/order does not exactly match canonical normalized records")
    if reconstructed != canonical_records:
        raise ValueError("Shard records do not reconstruct canonical pokemon.json records exactly")

    actual_shards = {
        path.relative_to(output_dir).as_posix()
        for path in (output_dir / SHARD_DIRECTORY).glob("chunk-*.json")
        if path.is_file()
    }
    if actual_shards != seen_paths:
        raise ValueError("Stale or undeclared collection shard files are present")
