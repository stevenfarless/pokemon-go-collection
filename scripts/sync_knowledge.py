#!/usr/bin/env python3
"""Build the repository-local Pokémon GO knowledge snapshot from a pinned PvPoke commit."""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator

KNOWLEDGE_SCHEMA_VERSION = "1.0.0"
INDEX_SCHEMA_VERSION = "1.0.0"
USER_AGENT = "pokemon-go-collection-knowledge-sync/1.0"

_REGION_ALIASES = {
    "alolan": "alola",
    "alola": "alola",
    "galarian": "galar",
    "galar": "galar",
    "hisuian": "hisui",
    "hisui": "hisui",
    "paldean": "paldea",
    "paldea": "paldea",
}


def _slug(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.casefold().replace("’", "'")
    text = re.sub(r"\bforme?\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    if text in _REGION_ALIASES:
        return _REGION_ALIASES[text]
    return "-".join(text.split()) or "normal"


def normalize_form(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text or text.casefold() in {"normal", "none", "ordinary"}:
        return "normal"
    normalized = _slug(text)
    for source, target in _REGION_ALIASES.items():
        normalized = re.sub(rf"(^|-)({re.escape(source)})(-|$)", rf"\1{target}\3", normalized)
    return normalized


def _split_species_name(display_name: str) -> tuple[str, str]:
    match = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", display_name.strip())
    if not match:
        return display_name.strip(), "normal"
    return match.group(1).strip(), match.group(2).strip() or "normal"


def _aliases(form_label: str, form_key: str) -> list[str]:
    values = {form_key, normalize_form(form_label)}
    if form_key == "normal":
        values.update({"normal", "none", ""})
    reverse_regions = {
        "alola": {"alola", "alolan"},
        "galar": {"galar", "galarian"},
        "hisui": {"hisui", "hisuian"},
        "paldea": {"paldea", "paldean"},
    }
    values.update(reverse_regions.get(form_key, set()))
    return sorted(values)


def _read_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _raw_url(repo: str, commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"


def _extract_cpms(source: str) -> list[dict[str, float]]:
    match = re.search(r"\bvar\s+cpms\s*=\s*\[(.*?)\]\s*;", source, re.DOTALL)
    if not match:
        raise ValueError("Pinned PvPoke mechanics source no longer exposes the expected cpms array")
    values = [float(item) for item in re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?", match.group(1))]
    if len(values) < 99:
        raise ValueError(f"CP multiplier table is unexpectedly short: {len(values)} values")
    result: list[dict[str, float]] = []
    for index, multiplier in enumerate(values):
        result.append({"level": 1.0 + index * 0.5, "multiplier": multiplier})
    return result


def _transformation_kind(tags: Iterable[str], form_label: str) -> str | None:
    lowered = {str(tag).casefold() for tag in tags}
    label = form_label.casefold()
    if "primal" in lowered or label.startswith("primal"):
        return "primal"
    if "mega" in lowered or label.startswith("mega"):
        return "mega"
    return None


def _normalize_entry(item: Mapping[str, Any]) -> dict[str, Any] | None:
    species_id = str(item.get("speciesId") or "").strip()
    tags = [str(value) for value in item.get("tags", [])]
    lowered_tags = {value.casefold() for value in tags}
    if not species_id or species_id.endswith("_shadow") or "shadow" in lowered_tags:
        return None

    dex = item.get("dex")
    display_name = str(item.get("speciesName") or "").strip()
    stats = item.get("baseStats") or {}
    if not isinstance(dex, int) or not display_name:
        return None
    if not all(isinstance(stats.get(key), (int, float)) for key in ("atk", "def", "hp")):
        return None

    base_name, form_label = _split_species_name(display_name)
    form_key = normalize_form(form_label)
    family = item.get("family") if isinstance(item.get("family"), Mapping) else {}
    kind = _transformation_kind(tags, form_label)
    types = [str(value).casefold() for value in item.get("types", []) if str(value).casefold() != "none"]

    entry = {
        "dex": dex,
        "species_id": species_id,
        "display_name": display_name,
        "base_name": base_name,
        "form_label": form_label,
        "form_key": form_key,
        "form_aliases": _aliases(form_label, form_key),
        "base_stats": {
            "attack": int(stats["atk"]),
            "defense": int(stats["def"]),
            "stamina": int(stats["hp"]),
        },
        "types": types,
        "buddy_distance_km": item.get("buddyDistance"),
        "second_charged_move_cost": {
            "stardust": item.get("thirdMoveCost"),
            "candy": None,
            "candy_status": "not-provided-by-pinned-source",
        },
        "moves": {
            "fast": sorted({str(value) for value in item.get("fastMoves", [])}),
            "charged": sorted({str(value) for value in item.get("chargedMoves", [])}),
            "elite_or_exclusive": sorted({str(value) for value in item.get("eliteMoves", [])}),
            "legacy": sorted({str(value) for value in item.get("legacyMoves", [])}),
        },
        "family": {
            "id": family.get("id"),
            "parent_species_id": family.get("parent"),
            "evolution_species_ids": list(family.get("evolutions", [])),
            "evolution_candy_cost": None,
            "special_requirements": None,
        },
        "transformation": {
            "kind": kind,
            "eligible": kind is not None,
        },
        "shadow_eligible": "shadoweligible" in lowered_tags,
        "released": bool(item.get("released", False)),
        "source_tags": sorted(set(tags)),
        "source_level_cap": item.get("levelCap"),
        "source_level_floor": item.get("levelFloor"),
        "transformations": [],
        "dynamax_eligibility": None,
        "gigantamax_eligibility": None,
    }
    return entry


def knowledge_schema() -> dict[str, Any]:
    entry = {
        "type": "object",
        "required": [
            "dex", "species_id", "display_name", "base_name", "form_label", "form_key",
            "form_aliases", "base_stats", "types", "buddy_distance_km", "second_charged_move_cost",
            "moves", "family", "transformation", "shadow_eligible", "released", "source_tags",
            "source_level_cap", "source_level_floor", "transformations", "dynamax_eligibility",
            "gigantamax_eligibility",
        ],
        "properties": {
            "dex": {"type": "integer", "minimum": 1},
            "species_id": {"type": "string", "minLength": 1},
            "display_name": {"type": "string", "minLength": 1},
            "base_name": {"type": "string", "minLength": 1},
            "form_label": {"type": "string", "minLength": 1},
            "form_key": {"type": "string", "minLength": 1},
            "form_aliases": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "base_stats": {
                "type": "object",
                "required": ["attack", "defense", "stamina"],
                "properties": {key: {"type": "integer", "minimum": 1} for key in ("attack", "defense", "stamina")},
                "additionalProperties": False,
            },
            "types": {"type": "array", "minItems": 1, "maxItems": 2, "items": {"type": "string"}},
            "buddy_distance_km": {"type": ["integer", "number", "null"], "minimum": 0},
            "second_charged_move_cost": {"type": "object"},
            "moves": {"type": "object"},
            "family": {"type": "object"},
            "transformation": {"type": "object"},
            "shadow_eligible": {"type": "boolean"},
            "released": {"type": "boolean"},
            "source_tags": {"type": "array", "items": {"type": "string"}},
            "source_level_cap": {"type": ["integer", "number", "null"]},
            "source_level_floor": {"type": ["integer", "number", "null"]},
            "transformations": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
            "dynamax_eligibility": {"type": ["boolean", "null"]},
            "gigantamax_eligibility": {"type": ["boolean", "null"]},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://stevenfarless.github.io/pokemon-go-collection/knowledge/pokemon-go.schema.json",
        "title": "Versioned Pokémon GO knowledge snapshot",
        "type": "object",
        "required": ["schema_version", "dataset_version", "classification", "source", "coverage", "mechanics", "entries"],
        "properties": {
            "schema_version": {"type": "string", "const": KNOWLEDGE_SCHEMA_VERSION},
            "dataset_version": {"type": "string", "minLength": 1},
            "classification": {"type": "string", "const": "Verified community data"},
            "source": {"type": "object"},
            "coverage": {"type": "object"},
            "mechanics": {"type": "object"},
            "entries": {"type": "array", "minItems": 1, "items": entry},
        },
        "additionalProperties": False,
    }


def index_schema() -> dict[str, Any]:
    entry = {
        "type": "object",
        "required": ["dex", "species_id", "display_name", "form_key", "family_id", "types", "transformation_kind"],
        "properties": {
            "dex": {"type": "integer", "minimum": 1},
            "species_id": {"type": "string", "minLength": 1},
            "display_name": {"type": "string", "minLength": 1},
            "form_key": {"type": "string", "minLength": 1},
            "family_id": {"type": ["string", "null"]},
            "types": {"type": "array", "items": {"type": "string"}},
            "transformation_kind": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://stevenfarless.github.io/pokemon-go-collection/knowledge/species-index.schema.json",
        "title": "Compact Pokémon GO species/form index",
        "type": "object",
        "required": ["schema_version", "dataset_version", "classification", "source_commit", "entry_count", "dex_count", "entries"],
        "properties": {
            "schema_version": {"type": "string", "const": INDEX_SCHEMA_VERSION},
            "dataset_version": {"type": "string", "minLength": 1},
            "classification": {"type": "string", "const": "Verified community data"},
            "source_commit": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "entry_count": {"type": "integer", "minimum": 1},
            "dex_count": {"type": "integer", "minimum": 1},
            "entries": {"type": "array", "minItems": 1, "items": entry},
        },
        "additionalProperties": False,
    }


def build_snapshot(lock: Mapping[str, Any], pokemon_source: list[Mapping[str, Any]], mechanics_source: str) -> tuple[dict[str, Any], dict[str, Any]]:
    source = lock["source"]
    entries = [entry for item in pokemon_source if (entry := _normalize_entry(item)) is not None]
    if not entries:
        raise ValueError("Pinned PvPoke source produced no usable Pokémon entries")
    entries.sort(key=lambda item: (item["dex"], item["species_id"]))

    transformations_by_dex: dict[int, list[str]] = defaultdict(list)
    for entry in entries:
        if entry["transformation"]["kind"] is not None:
            transformations_by_dex[entry["dex"]].append(entry["species_id"])
    for entry in entries:
        if entry["transformation"]["kind"] is None:
            entry["transformations"] = sorted(set(transformations_by_dex.get(entry["dex"], [])))

    cpms = _extract_cpms(mechanics_source)
    snapshot = {
        "schema_version": KNOWLEDGE_SCHEMA_VERSION,
        "dataset_version": lock["dataset_version"],
        "classification": lock["classification"],
        "source": {
            "name": source["name"],
            "repository": source["repository"],
            "commit": source["commit"],
            "commit_date": source["commit_date"],
            "license": source["license"],
            "pokemon_path": source["pokemon_path"],
            "mechanics_path": source["mechanics_path"],
            "attribution_file": "knowledge/PVPOKE-LICENSE.txt",
        },
        "coverage": {
            "species_forms": "snapshot from pinned PvPoke Pokémon game master; shadow duplicate rows excluded",
            "base_stats_and_types": "available when present in pinned source",
            "evolution_family_relationships": "available when present in pinned source",
            "evolution_candy_and_special_requirements": "unknown; not provided by pinned source and not guessed",
            "buddy_distance": "available when present in pinned source",
            "move_pools": "versioned snapshot only; not a current rotating-meta assertion",
            "second_charged_move_stardust": "available from PvPoke thirdMoveCost when present",
            "second_charged_move_candy": "unknown; not provided by pinned source and not guessed",
            "cp_level_inputs": "base stats plus pinned PvPoke CP multiplier table",
            "shadow_purified_cost_rules": "unknown; not provided by pinned source and not guessed",
            "mega_primal": "represented by pinned transformation entries/tags",
            "dynamax_gigantamax": "unknown unless a future pinned source adds explicit reliable fields",
        },
        "mechanics": {
            "cp_formula": "floor((base_attack+attack_iv)*sqrt(base_defense+defense_iv)*sqrt(base_stamina+stamina_iv)*cpm^2/10)",
            "hp_formula": "max(10,floor((base_stamina+stamina_iv)*cpm))",
            "ordinary_level_cap": 50,
            "cp_multiplier_levels": cpms,
        },
        "entries": entries,
    }
    index_entries = [
        {
            "dex": entry["dex"],
            "species_id": entry["species_id"],
            "display_name": entry["display_name"],
            "form_key": entry["form_key"],
            "family_id": entry["family"]["id"],
            "types": entry["types"],
            "transformation_kind": entry["transformation"]["kind"],
        }
        for entry in entries
    ]
    index = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "dataset_version": lock["dataset_version"],
        "classification": lock["classification"],
        "source_commit": source["commit"],
        "entry_count": len(index_entries),
        "dex_count": len({entry["dex"] for entry in entries}),
        "entries": index_entries,
    }
    return snapshot, index


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def sync(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    lock_path = root / "knowledge" / "source-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    source = lock["source"]
    commit = str(source["commit"])
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("knowledge/source-lock.json must pin a full 40-character upstream commit")

    pokemon_raw = _read_url(_raw_url(source["repository"], commit, source["pokemon_path"]))
    mechanics_raw = _read_url(_raw_url(source["repository"], commit, source["mechanics_path"]))
    pokemon_source = json.loads(pokemon_raw.decode("utf-8"))
    if not isinstance(pokemon_source, list):
        raise ValueError("Pinned PvPoke Pokémon source is not a JSON array")

    snapshot, index = build_snapshot(lock, pokemon_source, mechanics_raw.decode("utf-8"))
    knowledge_contract = knowledge_schema()
    index_contract = index_schema()
    Draft202012Validator.check_schema(knowledge_contract)
    Draft202012Validator.check_schema(index_contract)
    errors = list(Draft202012Validator(knowledge_contract).iter_errors(snapshot))
    if errors:
        raise ValueError(f"Generated knowledge snapshot fails schema: {errors[0].message}")
    errors = list(Draft202012Validator(index_contract).iter_errors(index))
    if errors:
        raise ValueError(f"Generated knowledge index fails schema: {errors[0].message}")

    _write_json(root / "knowledge" / "pokemon-go.json", snapshot)
    _write_json(root / "knowledge" / "pokemon-go.schema.json", knowledge_contract)
    _write_json(root / "knowledge" / "species-index.json", index)
    _write_json(root / "knowledge" / "species-index.schema.json", index_contract)
    return snapshot, index


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize the pinned Pokémon GO knowledge snapshot")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    snapshot, index = sync(args.root.resolve())
    print(
        f"Synchronized {index['entry_count']} species/form entries across {index['dex_count']} Pokédex numbers "
        f"from {snapshot['source']['name']} commit {snapshot['source']['commit'][:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
