"""Publish owned-only PvP and Team GO Rocket battle-lab resources.

This module advances issues #143 and #144 without inventing current battle facts.
Owned-record comparisons are deterministic from the canonical collection. Current
PvP meta and Rocket lineup claims are available only through fresh external snapshots.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from . import manifest_registry
except ImportError:
    import manifest_registry

BATTLE_LABS_VERSION = "1.0.0"
PVP_MODEL_VERSION = "1.0.0"
ROCKET_MODEL_VERSION = "1.0.0"
BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"
PVP_CATEGORIES = ("pvp", "pvp-meta", "gbl", "cups", "pvp-rankings")
ROCKET_CATEGORIES = ("rocket", "team-go-rocket", "rocket-lineups")


def _load(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _fresh_snapshot_payloads(output_dir: Path, categories: Iterable[str]) -> list[dict[str, Any]]:
    wanted = {str(item).casefold() for item in categories}
    index = _load(output_dir / "data" / "external" / "index.json", {}) or {}
    results: list[dict[str, Any]] = []
    for item in index.get("snapshots") or []:
        category = str(item.get("data_category") or "").casefold()
        freshness = item.get("freshness") or {}
        path = str(item.get("path") or "")
        if category not in wanted or freshness.get("state") != "fresh" or not path:
            continue
        payload = _load(output_dir / path, {}) or {}
        if (payload.get("freshness") or {}).get("state") != "fresh":
            continue
        results.append({"index": dict(item), "payload": payload})
    return results


def _evidence(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for wrapped in items:
        item = wrapped.get("index") or {}
        output.append({
            "provider": item.get("provider"),
            "data_category": item.get("data_category"),
            "dataset_timestamp": item.get("dataset_timestamp"),
            "source_reference": item.get("source_reference"),
            "authority": item.get("authority"),
            "validity": item.get("validity"),
            "path": item.get("path"),
        })
    return output


def _feed(output_dir: Path, name: str) -> dict[str, Any]:
    return _load(output_dir / "data" / "candidates" / f"{name}.json", {}) or {}


def build_pvp_battle_lab(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    feeds = {}
    for league in ("great", "ultra", "little", "master"):
        payload = _feed(output_dir, f"{league}-league")
        feeds[league] = {
            "path": f"data/candidates/{league}-league.json",
            "status": payload.get("status", "unavailable"),
            "candidate_count": int(payload.get("candidate_count") or 0),
        }

    fresh = _fresh_snapshot_payloads(output_dir, PVP_CATEGORIES)
    if fresh:
        current = {
            "state": "fresh-source-available",
            "reason": "Fresh current PvP evidence is available. Matchup simulation still requires a normalized battle-stat/matchup contract before wins or losses may be claimed.",
            "evidence": _evidence(fresh),
        }
    else:
        current = {
            "state": "blocked",
            "reason": "No fresh current PvP meta/cup snapshot is available. Current-meta wins, losses, team threats, breakpoints, and investment conclusions are blocked.",
            "evidence": [],
        }

    return {
        "schema_version": BATTLE_LABS_VERSION,
        "model_version": PVP_MODEL_VERSION,
        "build_id": manifest["build_id"],
        "title": "Advanced PvP Battle Lab",
        "owned_candidate_feeds": feeds,
        "current_simulation": current,
        "comparison_contract": {
            "state": "available",
            "exact_owned_record_mapping": True,
            "deterministic": True,
            "inputs": ["Poke Genie league rank percent", "rank number", "stat product", "known build cost", "exact IVs", "known moves", "canonical record ID"],
            "rank_one_warning": "PvP IV Rank 1 is not universally best. Rank/stat product are comparison inputs, not universal matchup superiority.",
            "cmp": "CMP is reported only when an explicit comparable Attack stat is present. Attack IV alone is never substituted for battle Attack.",
            "matchup_results": "Wins/losses/ties remain unavailable until fresh current meta plus normalized battle mechanics and move stats are present.",
        },
        "simulation_defaults": {
            "shields": 1,
            "starting_energy": 0,
            "starting_hp_percent": 100,
            "baiting": "model-default",
            "attack_stage": 0,
            "defense_stage": 0,
        },
        "safety": {
            "current_meta_requires_fresh_external_data": True,
            "speculative_changes_drive_default_investment": False,
            "automatic_account_action": False,
            "expensive_recommendations_require_cost_and_alternatives": True,
        },
        "provenance": {
            "owned_data": "normalized Poke Genie export",
            "current_data_contract": "data/external/index.json",
            "candidate_contract": "data/candidates/index.json",
        },
    }


def _walk_rocket_facts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, Mapping):
        keys = {str(key).casefold() for key in value}
        encounter_markers = {
            "encounter_id", "phrase", "grunt_phrase", "leader", "boss", "slots",
            "lineup", "lineups", "counter_species_dexes", "shadow_encounter",
        }
        if keys.intersection(encounter_markers) and (keys.intersection({"slots", "lineup", "lineups", "counter_species_dexes", "shadow_encounter"})):
            yield dict(value)
        for child in value.values():
            yield from _walk_rocket_facts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_rocket_facts(child)


def _normalize_rocket_encounter(raw: Mapping[str, Any], *, source_index: Mapping[str, Any]) -> dict[str, Any]:
    counter_dexes = []
    for value in raw.get("counter_species_dexes") or []:
        try:
            counter_dexes.append(int(value))
        except (TypeError, ValueError):
            continue
    return {
        "encounter_id": str(raw.get("encounter_id") or raw.get("id") or ""),
        "phrase": raw.get("phrase") or raw.get("grunt_phrase"),
        "leader": raw.get("leader"),
        "boss": raw.get("boss"),
        "slots": raw.get("slots") or raw.get("lineup") or raw.get("lineups"),
        "shadow_encounter": raw.get("shadow_encounter"),
        "counter_species_dexes": counter_dexes,
        "counter_mapping_state": "source-backed" if counter_dexes else "unavailable",
        "source": {
            "provider": source_index.get("provider"),
            "dataset_timestamp": source_index.get("dataset_timestamp"),
            "source_reference": source_index.get("source_reference"),
            "authority": source_index.get("authority"),
        },
    }


def build_rocket_planner(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    candidate_feed = _feed(output_dir, "rocket-battle-inputs")
    fresh = _fresh_snapshot_payloads(output_dir, ROCKET_CATEGORIES)
    encounters: list[dict[str, Any]] = []
    seen: set[str] = set()
    for wrapped in fresh:
        source_index = wrapped["index"]
        for fact in _walk_rocket_facts((wrapped["payload"] or {}).get("facts") or []):
            normalized = _normalize_rocket_encounter(fact, source_index=source_index)
            identity = normalized["encounter_id"] or json.dumps(
                [normalized.get("phrase"), normalized.get("leader"), normalized.get("boss"), normalized.get("slots")],
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            if identity in seen:
                continue
            seen.add(identity)
            encounters.append(normalized)

    if not fresh:
        state, reason = "blocked", "No fresh Team GO Rocket lineup snapshot is available. The planner refuses to recommend a party from old or missing rotation data."
    elif not encounters:
        state, reason = "blocked", "Fresh Rocket evidence exists, but it does not expose a supported branching-lineup contract. Party recommendations remain blocked."
    else:
        state, reason = "fresh", None

    return {
        "schema_version": BATTLE_LABS_VERSION,
        "model_version": ROCKET_MODEL_VERSION,
        "build_id": manifest["build_id"],
        "title": "Team GO Rocket Battle Planner",
        "current_lineups": {
            "state": state,
            "reason": reason,
            "encounter_count": len(encounters),
            "encounters": encounters,
            "evidence": _evidence(fresh),
        },
        "owned_candidates": {
            "path": "data/candidates/rocket-battle-inputs.json",
            "status": candidate_feed.get("status", "unavailable"),
            "candidate_count": int(candidate_feed.get("candidate_count") or 0),
            "exact_owned_record_mapping": True,
        },
        "recommendation_contract": {
            "stale_lineup_advice_blocks": True,
            "source_backed_counter_order_required": True,
            "exact_owned_records_only": True,
            "branching_slots_must_remain_visible": True,
            "fast_attack_pressure": "unavailable unless the current source supplies normalized move/battle timing inputs",
            "shield_consumption": "unavailable unless the current source supplies normalized move/battle timing inputs",
            "fallback": "When source-backed counter ordering is absent, show owned readiness inventory without calling it a matchup recommendation.",
        },
        "handoffs": {
            "action_packs": "action-packs.html",
            "move_lab": "move-lab.html",
            "decision_workspace": "index.html",
        },
        "safety": {
            "reported_or_datamined_is_confirmed": False,
            "automatic_account_action": False,
            "expired_rotation_can_drive_advice": False,
        },
    }


def _schema(name: str, required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE_ID + name + ".schema.json",
        "type": "object",
        "required": required,
        "properties": properties,
        "additionalProperties": True,
    }


def schemas() -> dict[str, dict[str, Any]]:
    string = {"type": "string"}
    build = {"type": "string", "pattern": "^[0-9a-f]{12}$"}
    return {
        "battle-labs-index.schema.json": _schema(
            "battle-labs-index",
            ["schema_version", "build_id", "labs"],
            {"schema_version": string, "build_id": build, "labs": {"type": "object"}},
        ),
        "pvp-battle-lab.schema.json": _schema(
            "pvp-battle-lab",
            ["schema_version", "model_version", "build_id", "owned_candidate_feeds", "current_simulation", "comparison_contract"],
            {"schema_version": string, "model_version": string, "build_id": build, "owned_candidate_feeds": {"type": "object"}, "current_simulation": {"type": "object"}, "comparison_contract": {"type": "object"}},
        ),
        "rocket-planner.schema.json": _schema(
            "rocket-planner",
            ["schema_version", "model_version", "build_id", "current_lineups", "owned_candidates", "recommendation_contract"],
            {"schema_version": string, "model_version": string, "build_id": build, "current_lineups": {"type": "object"}, "owned_candidates": {"type": "object"}, "recommendation_contract": {"type": "object"}},
        ),
    }


def _register_contracts() -> None:
    mapping = {
        "data/battle-labs/index.json": "data/battle-labs-index.schema.json",
        "data/pvp-battle-lab.json": "data/pvp-battle-lab.schema.json",
        "data/rocket-planner.json": "data/rocket-planner.schema.json",
    }
    manifest_registry._SCHEMA_MAP.update(mapping)
    manifest_registry._STABLE_NAMES.update({
        "data/battle-labs/index.json": "battle_labs_index",
        "data/pvp-battle-lab.json": "pvp_battle_lab",
        "data/rocket-planner.json": "rocket_planner",
        "data/battle-labs-index.schema.json": "battle_labs_index_schema",
        "data/pvp-battle-lab.schema.json": "pvp_battle_lab_schema",
        "data/rocket-planner.schema.json": "rocket_planner_schema",
    })


def _page(output_dir: Path, filename: str, title: str, mount_id: str, description: str) -> None:
    html = f'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title><link rel="stylesheet" href="assets/battle-labs.css" data-battle-labs-style></head>
<body><main class="battle-lab-page"><header class="battle-lab-header"><p><a href="tools.html">Tools</a> · <a href="index.html">Collection</a> · <a href="pvp-battle-lab.html">PvP Battle Lab</a> · <a href="rocket-planner.html">Rocket Planner</a> · <a href="action-packs.html">Action Packs</a></p><h1>{title}</h1><p>{description}</p></header><div id="{mount_id}"><p role="status">Loading…</p></div></main><script defer src="assets/battle-labs.js" data-battle-labs-script></script></body></html>'''
    (output_dir / filename).write_text(html, encoding="utf-8", newline="\n")


def _install_tools_links(output_dir: Path) -> None:
    path = output_dir / "tools.html"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    if 'id="advanced-battle-labs"' in source:
        return
    block = '''\n    <section id="advanced-battle-labs" class="planner-card" aria-labelledby="advanced-battle-labs-heading">
      <header><div><p class="eyebrow">#143/#144</p><h2 id="advanced-battle-labs-heading">Advanced battle labs</h2></div></header>
      <p>Compare exact owned PvP builds without treating IV Rank 1 as universally best, and open the freshness-gated Team GO Rocket planner. Current matchup and Rocket rotation advice fail closed when required current data is missing or stale.</p>
      <p><a href="pvp-battle-lab.html">Open PvP Battle Lab</a> · <a href="rocket-planner.html">Open Team GO Rocket Planner</a></p>
    </section>\n'''
    marker = "  </main>"
    if marker not in source:
        raise ValueError("Generated tools page is missing its main closing tag")
    path.write_text(source.replace(marker, block + marker, 1), encoding="utf-8", newline="\n")


def publish(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    del repository_root
    _register_contracts()
    pvp = build_pvp_battle_lab(output_dir, manifest)
    rocket = build_rocket_planner(output_dir, manifest)
    _write(output_dir / "data" / "pvp-battle-lab.json", pvp)
    _write(output_dir / "data" / "rocket-planner.json", rocket)
    index = {
        "schema_version": BATTLE_LABS_VERSION,
        "build_id": manifest["build_id"],
        "labs": {
            "pvp": {"data": "data/pvp-battle-lab.json", "page": "pvp-battle-lab.html", "issue": 143},
            "rocket": {"data": "data/rocket-planner.json", "page": "rocket-planner.html", "issue": 144},
        },
    }
    _write(output_dir / "data" / "battle-labs" / "index.json", index)
    for name, schema in schemas().items():
        _write(output_dir / "data" / name, schema)

    _page(
        output_dir,
        "pvp-battle-lab.html",
        "Advanced PvP Battle Lab",
        "pvp-battle-lab-root",
        "Owned-record comparison first. Current matchup simulation remains freshness and evidence gated.",
    )
    _page(
        output_dir,
        "rocket-planner.html",
        "Team GO Rocket Battle Planner",
        "rocket-planner-root",
        "Fresh current lineups are mandatory before the planner will present rotation-specific party advice.",
    )
    _install_tools_links(output_dir)

    llms_path = output_dir / "llms.txt"
    if llms_path.is_file():
        with llms_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "\nAdvanced battle labs:\n"
                "- /data/pvp-battle-lab.json and /pvp-battle-lab.html compare exact owned PvP candidates. Rank/stat product are not universal matchup claims; current simulations block without fresh current data and normalized battle inputs.\n"
                "- /data/rocket-planner.json and /rocket-planner.html require fresh Team GO Rocket rotation evidence. Missing or stale lineup data produces no rotation-specific party recommendation.\n"
            )
    return index


__all__ = [
    "BATTLE_LABS_VERSION",
    "PVP_MODEL_VERSION",
    "ROCKET_MODEL_VERSION",
    "build_pvp_battle_lab",
    "build_rocket_planner",
    "publish",
    "schemas",
]
