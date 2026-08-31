#!/usr/bin/env python3
"""Build a pinned trainer-battle mechanics snapshot for Rocket planning.

The snapshot is derived only from the repository's reviewed PvPoke source lock.
It preserves move/type mechanics as versioned inputs and deliberately does not
import authored rankings, current meta, or opponent-specific recommendations.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

SCHEMA_VERSION = "1.0.0"
USER_AGENT = "pokemon-go-collection-rocket-mechanics-sync/1.0"
EXPECTED_TYPES = {
    "normal", "fighting", "flying", "poison", "ground", "rock", "bug", "ghost",
    "steel", "fire", "water", "grass", "electric", "psychic", "ice", "dragon",
    "dark", "fairy",
}


def _raw_url(repo: str, commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"


def _read_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _constant(source: str, name: str) -> float:
    pattern = rf"\b{name}\s*=\s*([-+]?(?:\d*\.\d+|\d+\.?\d*))\s*;"
    match = re.search(pattern, source)
    if not match:
        raise ValueError(f"Pinned DamageCalculator source no longer exposes {name}")
    return float(match.group(1))


def extract_multipliers(source: str) -> dict[str, float]:
    return {
        "same_type_attack_bonus": _constant(source, "sameTypeBonus"),
        "super_effective": _constant(source, "typeEffectivenessBonus"),
        "resisted": _constant(source, "typeEffectivenessPenalty"),
        "double_resisted": _constant(source, "typeEffectivenessDoublePenalty"),
        "shadow_attack_bonus": _constant(source, "shadowBonus"),
        "trainer_battle_bonus": _constant(source, "trainerBattleBonus"),
    }


def _quoted_values(source: str) -> list[str]:
    return [value.casefold() for value in re.findall(r'["\']([A-Za-z]+)["\']', source)]


def extract_type_traits(source: str) -> dict[str, dict[str, list[str]]]:
    cases = re.findall(
        r'case\s+["\']([a-z]+)["\']\s*:\s*traits\s*=\s*\{(.*?)\}\s*;\s*break\s*;',
        source,
        flags=re.DOTALL | re.IGNORECASE,
    )
    traits: dict[str, dict[str, list[str]]] = {}
    for type_name, body in cases:
        fields: dict[str, list[str]] = {}
        for field in ("resistances", "weaknesses", "immunities"):
            match = re.search(rf"\b{field}\s*:\s*\[(.*?)\]", body, flags=re.DOTALL)
            if not match:
                raise ValueError(f"Pinned type table is missing {field} for {type_name}")
            fields[field] = _quoted_values(match.group(1))
        traits[type_name.casefold()] = fields
    if set(traits) != EXPECTED_TYPES:
        missing = sorted(EXPECTED_TYPES - set(traits))
        extra = sorted(set(traits) - EXPECTED_TYPES)
        raise ValueError(f"Pinned type table changed unexpectedly: missing={missing}, extra={extra}")
    return dict(sorted(traits.items()))


def normalize_move(item: Mapping[str, Any]) -> dict[str, Any] | None:
    move_id = str(item.get("moveId") or "").strip()
    name = str(item.get("name") or "").strip()
    move_type = str(item.get("type") or "").casefold().strip()
    required_numeric = ("power", "energy", "energyGain", "cooldown", "turns")
    if not move_id or not name or move_type not in EXPECTED_TYPES:
        return None
    if not all(isinstance(item.get(key), (int, float)) for key in required_numeric):
        return None
    move = {
        "move_id": move_id,
        "name": name,
        "type": move_type,
        "power": float(item["power"]),
        "energy": float(item["energy"]),
        "energy_gain": float(item["energyGain"]),
        "cooldown_ms": int(item["cooldown"]),
        "turns": int(item["turns"]),
    }
    if item.get("archetype") not in (None, ""):
        move["archetype"] = str(item["archetype"])
    if isinstance(item.get("buffs"), list):
        move["buffs"] = list(item["buffs"])
        move["buff_target"] = item.get("buffTarget")
        chance = item.get("buffApplyChance")
        try:
            move["buff_apply_chance"] = float(chance)
        except (TypeError, ValueError):
            move["buff_apply_chance"] = None
    return move


def build_snapshot(
    lock: Mapping[str, Any],
    moves_source: list[Mapping[str, Any]],
    damage_source: str,
) -> dict[str, Any]:
    source = lock["source"]
    moves = [move for item in moves_source if (move := normalize_move(item)) is not None]
    moves.sort(key=lambda item: item["move_id"])
    if len(moves) < 100:
        raise ValueError(f"Pinned move table is unexpectedly small: {len(moves)} moves")
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": lock["dataset_version"],
        "classification": lock["classification"],
        "source": {
            "name": source["name"],
            "repository": source["repository"],
            "commit": source["commit"],
            "commit_date": source["commit_date"],
            "license": source["license"],
            "moves_path": source["moves_path"],
            "damage_calculator_path": source["damage_calculator_path"],
            "attribution_file": "knowledge/PVPOKE-LICENSE.txt",
        },
        "scope": {
            "battle_mode": "trainer-battle mechanics used as normalized Rocket planning inputs",
            "current_meta": false,
            "authored_rankings": false,
            "opponent_levels_or_moves": false,
            "exact_win_or_survivability_claims": false,
        },
        "multipliers": extract_multipliers(damage_source),
        "type_traits": extract_type_traits(damage_source),
        "moves": moves,
    }


def schema() -> dict[str, Any]:
    numeric = {"type": "number", "minimum": 0}
    type_traits = {
        "type": "object",
        "required": ["resistances", "weaknesses", "immunities"],
        "properties": {
            key: {"type": "array", "items": {"type": "string"}, "uniqueItems": True}
            for key in ("resistances", "weaknesses", "immunities")
        },
        "additionalProperties": false,
    }
    move = {
        "type": "object",
        "required": ["move_id", "name", "type", "power", "energy", "energy_gain", "cooldown_ms", "turns"],
        "properties": {
            "move_id": {"type": "string", "minLength": 1},
            "name": {"type": "string", "minLength": 1},
            "type": {"type": "string", "enum": sorted(EXPECTED_TYPES)},
            "power": numeric,
            "energy": numeric,
            "energy_gain": numeric,
            "cooldown_ms": {"type": "integer", "minimum": 0},
            "turns": {"type": "integer", "minimum": 1},
            "archetype": {"type": "string"},
            "buffs": {"type": "array", "items": {"type": "number"}},
            "buff_target": {"type": ["string", "null"]},
            "buff_apply_chance": {"type": ["number", "null"]},
        },
        "additionalProperties": false,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://stevenfarless.github.io/pokemon-go-collection/knowledge/rocket-battle-mechanics.schema.json",
        "title": "Pinned trainer-battle mechanics for Team GO Rocket planning",
        "type": "object",
        "required": ["schema_version", "dataset_version", "classification", "source", "scope", "multipliers", "type_traits", "moves"],
        "properties": {
            "schema_version": {"type": "string", "const": SCHEMA_VERSION},
            "dataset_version": {"type": "string", "minLength": 1},
            "classification": {"type": "string", "const": "Verified community data"},
            "source": {"type": "object"},
            "scope": {"type": "object"},
            "multipliers": {"type": "object"},
            "type_traits": {
                "type": "object",
                "required": sorted(EXPECTED_TYPES),
                "properties": {name: type_traits for name in sorted(EXPECTED_TYPES)},
                "additionalProperties": false,
            },
            "moves": {"type": "array", "minItems": 100, "items": move},
        },
        "additionalProperties": false,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def sync(root: Path) -> dict[str, Any]:
    lock = json.loads((root / "knowledge" / "source-lock.json").read_text(encoding="utf-8"))
    source = lock["source"]
    commit = str(source["commit"])
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("knowledge/source-lock.json must pin a full 40-character upstream commit")
    for key in ("moves_path", "damage_calculator_path"):
        if not source.get(key):
            raise ValueError(f"knowledge/source-lock.json is missing source.{key}")

    moves_raw = _read_url(_raw_url(source["repository"], commit, source["moves_path"]))
    damage_raw = _read_url(_raw_url(source["repository"], commit, source["damage_calculator_path"]))
    moves_source = json.loads(moves_raw.decode("utf-8"))
    if not isinstance(moves_source, list):
        raise ValueError("Pinned PvPoke moves source is not a JSON array")

    payload = build_snapshot(lock, moves_source, damage_raw.decode("utf-8"))
    contract = schema()
    Draft202012Validator.check_schema(contract)
    errors = list(Draft202012Validator(contract).iter_errors(payload))
    if errors:
        raise ValueError(f"Generated Rocket battle mechanics fail schema: {errors[0].message}")
    _write_json(root / "knowledge" / "rocket-battle-mechanics.json", payload)
    _write_json(root / "knowledge" / "rocket-battle-mechanics.schema.json", contract)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize pinned Rocket battle mechanics")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    payload = sync(args.root.resolve())
    print(
        f"Synchronized {len(payload['moves'])} trainer-battle moves and {len(payload['type_traits'])} defensive types "
        f"from {payload['source']['name']} commit {payload['source']['commit'][:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
