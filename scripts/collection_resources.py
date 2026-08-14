"""Selective collection resources, static API aliases, and bounded history."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from . import build_collection as base
    from .collection_integrity import process_collection
    from .semantic_validation import validate_rows
except ImportError:
    import build_collection as base
    from collection_integrity import process_collection
    from semantic_validation import validate_rows

RESOURCE_SCHEMA_VERSION = "1.0.0"
HISTORY_SCHEMA_VERSION = "1.0.0"
API_VERSION = "v1"
HISTORY_RETENTION = 12


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return text or "pokemon"


def _record_id(record: Mapping[str, Any]) -> str:
    return str(record.get("identity", {}).get("record_id") or "")


def _fingerprint(record: Mapping[str, Any]) -> str:
    return str(record.get("identity", {}).get("record_fingerprint") or "")


def _resource_payload(*, manifest: Mapping[str, Any], records: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "schema_version": RESOURCE_SCHEMA_VERSION,
        "build_id": manifest["build_id"],
        "record_count": len(records),
        **extra,
        "records": records,
    }


def _knowledge_family_maps(knowledge_index: Mapping[str, Any]) -> tuple[dict[int, str | None], dict[str, dict[str, Any]]]:
    by_dex: dict[int, set[str | None]] = defaultdict(set)
    family_entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in knowledge_index.get("entries", []):
        dex = int(entry["dex"])
        family_id = entry.get("family_id")
        by_dex[dex].add(family_id)
        if family_id:
            family_entries[str(family_id)].append(entry)

    dex_family: dict[int, str | None] = {}
    for dex, family_ids in by_dex.items():
        nonnull = {value for value in family_ids if value}
        dex_family[dex] = next(iter(nonnull)) if len(nonnull) == 1 else None

    families: dict[str, dict[str, Any]] = {}
    for family_id, entries in family_entries.items():
        ordered = sorted(entries, key=lambda item: (int(item["dex"]), str(item["display_name"]).casefold(), str(item["form_key"])))
        root = ordered[0]
        families[family_id] = {
            "family_id": family_id,
            "root_dex": int(root["dex"]),
            "root_name": str(root["display_name"]),
            "species_dexes": sorted({int(item["dex"]) for item in ordered}),
        }
    return dex_family, families


def publish_species_family_resources(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Publish owned per-species and evolutionary-family resources."""
    payload = _load(output_dir / "data" / "pokemon.json")
    records = payload["records"]
    knowledge_index = _load(output_dir / "data" / "knowledge" / "species-index.json")
    dex_family, families = _knowledge_family_maps(knowledge_index)

    species_dir = output_dir / "data" / "pokemon" / "species"
    family_dir = output_dir / "data" / "pokemon" / "families"
    shutil.rmtree(species_dir, ignore_errors=True)
    shutil.rmtree(family_dir, ignore_errors=True)

    by_species: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        dex = int(record["pokemon_number"])
        by_species[(dex, str(record["name"]))].append(record)
        family_id = dex_family.get(dex)
        if family_id:
            by_family[family_id].append(record)

    species_entries: list[dict[str, Any]] = []
    for (dex, name), owned in sorted(by_species.items(), key=lambda item: (item[0][0], item[0][1].casefold())):
        relative = f"data/pokemon/species/{dex:03d}-{_slug(name)}.json"
        path = output_dir / relative
        species_payload = _resource_payload(
            manifest=manifest,
            records=owned,
            dex=dex,
            name=name,
            owned_count=len(owned),
            knowledge_dataset_version=knowledge_index["dataset_version"],
        )
        _write_json(path, species_payload, compact=True)
        species_entries.append({
            "dex": dex,
            "name": name,
            "owned_count": len(owned),
            "path": relative,
            "byte_size": path.stat().st_size,
            "schema_version": RESOURCE_SCHEMA_VERSION,
            "build_id": manifest["build_id"],
        })

    family_entries: list[dict[str, Any]] = []
    for family_id, owned in sorted(
        by_family.items(),
        key=lambda item: (families[item[0]]["root_dex"], families[item[0]]["root_name"].casefold()),
    ):
        meta = families[family_id]
        relative = f"data/pokemon/families/{meta['root_dex']:03d}-{_slug(meta['root_name'])}.json"
        path = output_dir / relative
        family_payload = _resource_payload(
            manifest=manifest,
            records=owned,
            family_id=family_id,
            root_dex=meta["root_dex"],
            root_name=meta["root_name"],
            species_dexes=meta["species_dexes"],
            owned_count=len(owned),
            knowledge_dataset_version=knowledge_index["dataset_version"],
        )
        _write_json(path, family_payload, compact=True)
        family_entries.append({
            "family_id": family_id,
            "root_dex": meta["root_dex"],
            "root_name": meta["root_name"],
            "species_dexes": meta["species_dexes"],
            "owned_count": len(owned),
            "path": relative,
            "byte_size": path.stat().st_size,
            "schema_version": RESOURCE_SCHEMA_VERSION,
            "build_id": manifest["build_id"],
        })

    species_index = {
        "schema_version": RESOURCE_SCHEMA_VERSION,
        "build_id": manifest["build_id"],
        "knowledge_dataset_version": knowledge_index["dataset_version"],
        "species_count": len(species_entries),
        "record_count": len(records),
        "entries": species_entries,
    }
    family_index = {
        "schema_version": RESOURCE_SCHEMA_VERSION,
        "build_id": manifest["build_id"],
        "knowledge_dataset_version": knowledge_index["dataset_version"],
        "family_count": len(family_entries),
        "record_count": sum(entry["owned_count"] for entry in family_entries),
        "entries": family_entries,
    }
    _write_json(output_dir / "data" / "species-index.json", species_index)
    _write_json(output_dir / "data" / "family-index.json", family_index)
    return {"species": species_index, "families": family_index}


def _view_record_ids(records: Iterable[Mapping[str, Any]]) -> list[str]:
    return [record_id for record in records if (record_id := _record_id(record))]


def publish_derived_views(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Publish deterministic collection subsets and an availability-aware view index."""
    records = _load(output_dir / "data" / "pokemon.json")["records"]
    quality = _load(output_dir / "data" / "scan-quality-report.json")
    data_dir = output_dir / "data" / "views"
    shutil.rmtree(data_dir, ignore_errors=True)

    rescan_ids = {
        finding.get("record_id")
        for finding in quality.get("findings", [])
        if finding.get("suggested_action") == "rescan" and finding.get("record_id")
    }
    definitions: dict[str, tuple[str, Any]] = {
        "hundos": ("Exact 15/15/15 IV records.", lambda r: bool(r.get("ivs", {}).get("is_hundo"))),
        "nundos": ("Exact 0/0/0 IV records.", lambda r: bool(r.get("ivs", {}).get("is_nundo"))),
        "shadow": ("Records explicitly exported as Shadow.", lambda r: r.get("status", {}).get("shadow_purified") == "shadow"),
        "purified": ("Records explicitly exported as Purified.", lambda r: r.get("status", {}).get("shadow_purified") == "purified"),
        "lucky": ("Records explicitly exported as Lucky.", lambda r: bool(r.get("status", {}).get("lucky"))),
        "favorites": ("Records explicitly exported as Favorite.", lambda r: bool(r.get("status", {}).get("favorite"))),
        "great-league-candidates": ("Records with a Poke Genie Great League IV rank percentage.", lambda r: r.get("pvp", {}).get("great", {}).get("rank_percent") is not None),
        "ultra-league-candidates": ("Records with a Poke Genie Ultra League IV rank percentage.", lambda r: r.get("pvp", {}).get("ultra", {}).get("rank_percent") is not None),
        "little-league-candidates": ("Records with a Poke Genie Little League IV rank percentage.", lambda r: r.get("pvp", {}).get("little", {}).get("rank_percent") is not None),
        "needs-rescan": ("Records referenced by scan-quality findings whose suggested action is rescan.", lambda r: _record_id(r) in rescan_ids),
    }
    index_entries: list[dict[str, Any]] = []
    for name, (definition, predicate) in definitions.items():
        selected = [record for record in records if predicate(record)]
        relative = f"data/views/{name}.json"
        _write_json(
            output_dir / relative,
            {
                "schema_version": RESOURCE_SCHEMA_VERSION,
                "build_id": manifest["build_id"],
                "name": name,
                "definition": definition,
                "record_count": len(selected),
                "record_ids": _view_record_ids(selected),
                "records": selected,
            },
            compact=True,
        )
        index_entries.append({
            "name": name,
            "status": "available",
            "definition": definition,
            "record_count": len(selected),
            "path": relative,
        })

    unsupported = {
        "legendary": "The Poke Genie export contract does not explicitly identify Legendary status.",
        "mythical": "The Poke Genie export contract does not explicitly identify Mythical status.",
        "ultra-beast": "The Poke Genie export contract does not explicitly identify Ultra Beast status.",
        "dynamax": "The current Poke Genie export contract does not explicitly identify Dynamax status.",
        "gigantamax": "The current Poke Genie export contract does not explicitly identify Gigantamax status.",
    }
    for name, reason in unsupported.items():
        index_entries.append({"name": name, "status": "unavailable", "definition": reason, "record_count": None, "path": None})

    index = {
        "schema_version": RESOURCE_SCHEMA_VERSION,
        "build_id": manifest["build_id"],
        "entries": sorted(index_entries, key=lambda item: item["name"]),
        "safety": "Unavailable source attributes remain unknown and are never inferred from species names or general game knowledge.",
    }
    _write_json(output_dir / "data" / "views-index.json", index)
    return index


def publish_assistant_context(output_dir: Path, manifest: Mapping[str, Any]) -> None:
    """Publish concise vendor-neutral machine retrieval instructions."""
    context = f"""# Pokémon GO collection assistant context

Build ID: `{manifest['build_id']}`  
Source export: `{manifest['source_file']}`  
Export timestamp: `{manifest['export_timestamp']}`  
Canonical record count: {manifest['normalized_record_count']}

## Authority and freshness

`data/build-manifest.json` is the freshness and resource authority for the published build. `data/pokemon.json` is the canonical normalized owned-record dataset. Aggregate summaries never prove ownership of an individual Pokémon. Original CSV evidence remains available at `data/latest-export.csv`.

## Selective retrieval

1. Read `data/build-manifest.json` and confirm the build ID and export timestamp.
2. For a species question, read `data/species-index.json`, then fetch only the listed species resource.
3. For an evolution decision, read `data/family-index.json`, then fetch the listed family resource.
4. For a supported subset question, read `data/views-index.json`, then fetch the named available view.
5. For a collection-wide scan, read `data/pokemon-index.json` and fetch only its bounded shards.
6. Fetch `data/pokemon.json` directly only when the client can reliably retrieve the complete canonical payload.

## Interpretation rules

Canonical records describe Pokémon present in the newest normalized Poke Genie export. Repeated scans may be conservatively reconciled before publication. `identity.record_id` is build-scoped; `identity.record_fingerprint` is best-effort cross-build identity with an explicit confidence level. Missing fields are uncertainty. Do not infer shiny, costume, background, trade, Legendary, Mythical, Ultra Beast, Dynamax, Gigantamax, legacy-move, or other unsupported statuses from absence in the export.

Poke Genie PvP rank fields describe IV distributions under a league cap. They do not establish current meta relevance. Current events, raid rotations, move availability, PvP metas, prices, and other time-sensitive Pokémon GO facts require an external current source with its own freshness check.

## Exact record citations

When making a decision about an owned Pokémon, cite its `identity.record_id`, species/name, form when present, CP, exact IVs when present, and the build ID. Use the record's provenance and scan-quality findings when stale or incomplete data could change the recommendation.
"""
    (output_dir / "data" / "assistant-context.md").write_text(context, encoding="utf-8", newline="\n")

    llms = f"""# Pokémon GO Collection

Current build: {manifest['build_id']}
Current source: {manifest['source_file']}
Export timestamp: {manifest['export_timestamp']}
Canonical Pokémon records: {manifest['normalized_record_count']}

Selective retrieval workflow:
1. /data/build-manifest.json - verify freshness and discover published resources.
2. /data/species-index.json - species-specific ownership lookup.
3. /data/family-index.json - evolutionary-family lookup.
4. /data/views-index.json - discover supported derived collection subsets.
5. /data/pokemon-index.json - bounded shards for collection-wide questions.
6. /data/pokemon.json - canonical complete dataset when full retrieval is practical.

Interpretation guidance:
- /data/assistant-context.md explains authority, provenance, unsupported fields, safe interpretation, exact-record citations, and the boundary between static collection facts and time-sensitive Pokémon GO facts.
- /data/collection-summary.json is aggregate-only and cannot prove ownership of an individual record.
- Missing source fields remain unknown; do not infer unsupported collector/game statuses.
- Poke Genie PvP IV ranks are collection facts, not current meta rankings.

Versioned static interface:
- /api/v1/index.json documents the stable v1 endpoint surface and compatibility policy.
"""
    (output_dir / "llms.txt").write_text(llms, encoding="utf-8", newline="\n")


def _historical_records(export_path: Path) -> list[dict[str, Any]]:
    with export_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        report = base.analyze_source_columns(fieldnames)
        missing = report["missing_required_columns"]
        if missing:
            raise ValueError(f"Historical export {export_path.name} is missing required columns: {', '.join(missing)}")
        rows, warnings = validate_rows(fieldnames, reader)
    raw_records = [base.legacy.normalize_row(row, row_number) for row_number, row in enumerate(rows, start=2)]
    parsed = base.legacy.parse_export_filename(export_path)
    normalized, _, _ = process_collection(
        rows,
        raw_records,
        source_filename=export_path.name,
        reference_date=parsed.timestamp.date() if parsed else None,
        unknown_columns=report["unknown_columns"],
        semantic_warnings=[warning.to_dict() for warning in warnings],
    )
    return normalized


def _snapshot_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "record_id": _record_id(record),
        "record_fingerprint": _fingerprint(record),
        "fingerprint_confidence": record.get("identity", {}).get("fingerprint_confidence"),
        "pokemon_number": record.get("pokemon_number"),
        "name": record.get("name"),
        "form": record.get("form"),
        "gender": record.get("gender"),
        "cp": record.get("cp"),
        "hp": record.get("hp"),
        "ivs": record.get("ivs"),
        "level": record.get("level"),
        "moves": record.get("moves"),
        "status": record.get("status"),
        "dates": record.get("dates"),
    }


def _history_id(source_file: str, records: Iterable[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    digest.update(source_file.encode("utf-8"))
    for record in records:
        digest.update(_fingerprint(record).encode("ascii", errors="ignore"))
        digest.update(b"\0")
    return digest.hexdigest()[:12]


def _secondary_key(record: Mapping[str, Any]) -> tuple[Any, ...] | None:
    ivs = record.get("ivs", {})
    exact = (ivs.get("attack"), ivs.get("defense"), ivs.get("stamina"))
    dates = record.get("dates", {})
    anchor = dates.get("original_scan") or dates.get("catch")
    if anchor is None or any(value is None for value in exact):
        return None
    status = record.get("status", {})
    return (
        record.get("pokemon_number"), record.get("form"), record.get("gender"), exact,
        anchor, status.get("shadow_purified"), status.get("lucky"),
    )


def _change_kinds(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    changes: list[str] = []
    if before.get("cp") != after.get("cp") or before.get("level") != after.get("level"):
        changes.append("level_or_cp")
    if before.get("moves") != after.get("moves"):
        changes.append("moveset")
    if before.get("ivs") != after.get("ivs"):
        changes.append("ivs_or_completeness")
    if before.get("status") != after.get("status") or before.get("form") != after.get("form"):
        changes.append("status_or_form")
    if before.get("hp") != after.get("hp") or before.get("dates") != after.get("dates"):
        changes.append("scan_data")
    return changes


def _diff_snapshots(previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> dict[str, Any]:
    current_records = current["records"]
    previous_records = previous["records"] if previous else []
    if previous is None:
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "from_build_id": None,
            "to_build_id": current["build_id"],
            "summary": {"added": len(current_records), "removed": 0, "changed": 0, "ambiguous": 0},
            "added": current_records,
            "removed": [],
            "changed": [],
            "ambiguous": [],
            "wording": "Removed means no longer present in the current normalized export; it does not by itself prove an in-game transfer.",
        }

    prev_by_fp: dict[str, list[dict[str, Any]]] = defaultdict(list)
    curr_by_fp: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in previous_records:
        prev_by_fp[str(record.get("record_fingerprint") or "")].append(record)
    for record in current_records:
        curr_by_fp[str(record.get("record_fingerprint") or "")].append(record)

    matched_prev: set[int] = set()
    matched_curr: set[int] = set()
    changed: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []

    for fp in sorted(set(prev_by_fp) & set(curr_by_fp)):
        left = prev_by_fp[fp]
        right = curr_by_fp[fp]
        if fp and len(left) == len(right) == 1:
            before, after = left[0], right[0]
            matched_prev.add(id(before))
            matched_curr.add(id(after))
            kinds = _change_kinds(before, after)
            if kinds:
                changed.append({"match": "fingerprint", "confidence": after.get("fingerprint_confidence"), "change_kinds": kinds, "before": before, "after": after})
        elif fp:
            ambiguous.append({"reason": "non_unique_fingerprint", "record_fingerprint": fp, "previous_count": len(left), "current_count": len(right)})

    remaining_prev = [record for record in previous_records if id(record) not in matched_prev]
    remaining_curr = [record for record in current_records if id(record) not in matched_curr]
    prev_by_key: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    curr_by_key: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for record in remaining_prev:
        if (key := _secondary_key(record)) is not None:
            prev_by_key[key].append(record)
    for record in remaining_curr:
        if (key := _secondary_key(record)) is not None:
            curr_by_key[key].append(record)
    for key in set(prev_by_key) & set(curr_by_key):
        left, right = prev_by_key[key], curr_by_key[key]
        if len(left) == len(right) == 1:
            before, after = left[0], right[0]
            matched_prev.add(id(before))
            matched_curr.add(id(after))
            kinds = _change_kinds(before, after) or ["identity_refresh"]
            changed.append({"match": "stable_secondary_key", "confidence": "medium", "change_kinds": kinds, "before": before, "after": after})
        else:
            ambiguous.append({"reason": "non_unique_secondary_key", "previous_count": len(left), "current_count": len(right)})

    removed = [record for record in previous_records if id(record) not in matched_prev]
    added = [record for record in current_records if id(record) not in matched_curr]
    return {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "from_build_id": previous["build_id"],
        "to_build_id": current["build_id"],
        "summary": {"added": len(added), "removed": len(removed), "changed": len(changed), "ambiguous": len(ambiguous)},
        "added": added,
        "removed": removed,
        "changed": changed,
        "ambiguous": ambiguous,
        "wording": "Removed means no longer present in the current normalized export; it does not by itself prove an in-game transfer.",
    }


def publish_history(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Generate bounded snapshots for archived exports and a current cross-build diff."""
    exports = base.discover_exports(repository_root)[-HISTORY_RETENTION:]
    current_records = _load(output_dir / "data" / "pokemon.json")["records"]
    snapshots: list[dict[str, Any]] = []

    for export in exports:
        is_current = export.path.name == Path(str(manifest["source_file"])).name
        normalized = current_records if is_current else _historical_records(export.path)
        build_id = str(manifest["build_id"]) if is_current else _history_id(export.path.name, normalized)
        snapshot = {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "build_id": build_id,
            "source_file": f"exports/{export.path.name}",
            "export_timestamp": export.timestamp.isoformat(timespec="milliseconds"),
            "record_count": len(normalized),
            "records": [_snapshot_record(record) for record in normalized],
        }
        _write_json(output_dir / "data" / "history" / build_id / "snapshot.json", snapshot, compact=True)
        snapshots.append(snapshot)

    current = snapshots[-1] if snapshots else {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "build_id": manifest["build_id"],
        "source_file": manifest["source_file"],
        "export_timestamp": manifest["export_timestamp"],
        "record_count": len(current_records),
        "records": [_snapshot_record(record) for record in current_records],
    }
    previous = snapshots[-2] if len(snapshots) > 1 else None
    diff = _diff_snapshots(previous, current)
    _write_json(output_dir / "data" / "collection-diff.json", diff)
    _write_json(output_dir / "data" / "history-index.json", {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "retention_limit": HISTORY_RETENTION,
        "snapshot_count": len(snapshots),
        "snapshots": [
            {key: snapshot[key] for key in ("build_id", "source_file", "export_timestamp", "record_count")}
            | {"path": f"data/history/{snapshot['build_id']}/snapshot.json"}
            for snapshot in snapshots
        ],
        "latest_diff": "data/collection-diff.json",
    })
    return diff


def publish_static_api(output_dir: Path, manifest: Mapping[str, Any]) -> None:
    """Publish a versioned, cacheable static API surface without server-side semantics."""
    api_root = output_dir / "api" / API_VERSION
    shutil.rmtree(api_root, ignore_errors=True)
    api_root.mkdir(parents=True, exist_ok=True)

    copies = {
        "manifest.json": output_dir / "data" / "build-manifest.json",
        "species/index.json": output_dir / "data" / "species-index.json",
        "families/index.json": output_dir / "data" / "family-index.json",
        "views/index.json": output_dir / "data" / "views-index.json",
        "history/latest-diff.json": output_dir / "data" / "collection-diff.json",
    }
    for relative, source in copies.items():
        target = api_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    for entry in _load(output_dir / "data" / "species-index.json")["entries"]:
        source = output_dir / entry["path"]
        shutil.copy2(source, api_root / "species" / f"{int(entry['dex']):03d}.json")
    for entry in _load(output_dir / "data" / "family-index.json")["entries"]:
        source = output_dir / entry["path"]
        shutil.copy2(source, api_root / "families" / f"{int(entry['root_dex']):03d}.json")
    for entry in _load(output_dir / "data" / "views-index.json")["entries"]:
        if entry["status"] == "available" and entry.get("path"):
            shutil.copy2(output_dir / entry["path"], api_root / "views" / f"{entry['name']}.json")

    index = {
        "api_version": API_VERSION,
        "build_id": manifest["build_id"],
        "stability": {
            "major_version": "Paths and required top-level meanings remain compatible within v1.",
            "breaking_changes": "Breaking endpoint or required-field changes require a new major API version.",
            "deprecation": "Deprecated v1 paths remain documented for at least one repository release before removal unless unsafe or invalid.",
        },
        "semantics": {
            "transport": "Static GitHub Pages files; no server-side query parameters or runtime database.",
            "cache": "Consumers should compare build_id/export timestamp through manifest.json before relying on cached collection facts.",
            "cors": "GitHub Pages responses are ordinary static web resources; consumers must obey the headers served by GitHub Pages.",
        },
        "endpoints": {
            "manifest": "manifest.json",
            "species_index": "species/index.json",
            "species": "species/{dex}.json",
            "family_index": "families/index.json",
            "families": "families/{root_dex}.json",
            "views_index": "views/index.json",
            "views": "views/{name}.json",
            "latest_diff": "history/latest-diff.json",
        },
    }
    _write_json(api_root / "index.json", index)


def validate_static_api(output_dir: Path) -> None:
    api_root = output_dir / "api" / API_VERSION
    index = _load(api_root / "index.json")
    manifest = _load(api_root / "manifest.json")
    if index["build_id"] != manifest["build_id"]:
        raise ValueError("Static API index and manifest use different build IDs")
    for required in ("species/index.json", "families/index.json", "views/index.json", "history/latest-diff.json"):
        if not (api_root / required).is_file():
            raise ValueError(f"Static API endpoint is missing: api/{API_VERSION}/{required}")
    for entry in _load(api_root / "species" / "index.json")["entries"]:
        if not (api_root / "species" / f"{int(entry['dex']):03d}.json").is_file():
            raise ValueError(f"Static API species endpoint missing for dex {entry['dex']}")
    for entry in _load(api_root / "families" / "index.json")["entries"]:
        if not (api_root / "families" / f"{int(entry['root_dex']):03d}.json").is_file():
            raise ValueError(f"Static API family endpoint missing for root dex {entry['root_dex']}")
    for entry in _load(api_root / "views" / "index.json")["entries"]:
        if entry["status"] == "available" and not (api_root / "views" / f"{entry['name']}.json").is_file():
            raise ValueError(f"Static API view endpoint missing for {entry['name']}")
