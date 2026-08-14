"""Deterministic collection decision-support resources for issues #64, #66, #67, and #73.

All outputs in this module are derived from the normalized owned collection, the
versioned repository-local species/mechanics snapshot, and Poke Genie fields already
present in the export.  They intentionally do not embed current PvP/raid/event meta
claims and never emit destructive Pokémon GO actions.
"""

from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .collection_intelligence import missing_scan_reasons
except ImportError:
    from collection_intelligence import missing_scan_reasons

DECISION_SUPPORT_VERSION = "1.0.0"
RECOMMENDATION_SCHEMA_VERSION = "1.0.0"
CANDIDATE_SCHEMA_VERSION = "1.0.0"
INVESTMENT_MODEL_VERSION = "1.0.0"
REASONING_ENGINE_VERSION = "1.0.0"
HIGH_PVP_PERCENTILE = 95.0
HIGH_PVP_BUILD_DUST = 100_000
HIGH_PVP_BUILD_CANDY = 100
HIGH_SECOND_MOVE_DUST = 75_000


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _record_id(record: Mapping[str, Any]) -> str:
    return str(record.get("identity", {}).get("record_id") or "")


def _form_key(value: Any) -> str:
    text = "" if value is None else str(value).strip().casefold()
    if text in {"", "normal", "none", "ordinary"}:
        return "normal"
    aliases = {
        "alolan": "alola",
        "galarian": "galar",
        "hisuian": "hisui",
        "paldean": "paldea",
    }
    text = aliases.get(text, text)
    text = re.sub(r"\bforme?\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return aliases.get(text, text or "normal")


def _knowledge_maps(knowledge: Mapping[str, Any]) -> tuple[dict[tuple[int, str], dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    exact: dict[tuple[int, str], dict[str, Any]] = {}
    by_dex: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for raw in knowledge.get("entries", []):
        entry = dict(raw)
        dex = int(entry["dex"])
        exact[(dex, str(entry.get("form_key") or "normal"))] = entry
        by_dex[dex].append(entry)
    return exact, by_dex


def _knowledge_for(record: Mapping[str, Any], exact: Mapping[tuple[int, str], dict[str, Any]], by_dex: Mapping[int, list[dict[str, Any]]]) -> dict[str, Any] | None:
    dex = int(record["pokemon_number"])
    form = _form_key(record.get("form"))
    if (dex, form) in exact:
        return exact[(dex, form)]
    if (dex, "normal") in exact:
        return exact[(dex, "normal")]
    candidates = by_dex.get(dex, [])
    non_transformed = [item for item in candidates if not item.get("transformation", {}).get("eligible")]
    if len(non_transformed) == 1:
        return non_transformed[0]
    return candidates[0] if len(candidates) == 1 else None


def _knowledge_context(output_dir: Path) -> tuple[dict[str, Any], dict[tuple[int, str], dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    knowledge = _load(output_dir / "data" / "knowledge" / "pokemon-go.json")
    exact, by_dex = _knowledge_maps(knowledge)
    return knowledge, exact, by_dex


def _warning_codes(record: Mapping[str, Any]) -> list[str]:
    warnings = [f"missing_{reason.replace('-', '_')}" for reason in missing_scan_reasons(dict(record))]
    pvp = record.get("pvp", {})
    if all(pvp.get(league, {}).get("rank_percent") is None for league in ("great", "ultra", "little")):
        warnings.append("missing_poke_genie_pvp_rankings")
    return sorted(set(warnings))


def _record_ref(record: Mapping[str, Any], *, reasons: Iterable[str] = (), warnings: Iterable[str] = (), inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "record_id": _record_id(record),
        "pokemon_number": record["pokemon_number"],
        "name": record["name"],
        "form": record.get("form"),
        "cp": record.get("cp"),
        "reasons": sorted(set(reasons)),
        "warnings": sorted(set(warnings)),
        "inputs": dict(inputs or {}),
    }


def _queue_payload(manifest: Mapping[str, Any], queue: str, definition: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": RECOMMENDATION_SCHEMA_VERSION,
        "decision_support_version": DECISION_SUPPORT_VERSION,
        "build_id": manifest["build_id"],
        "queue": queue,
        "definition": definition,
        "record_count": len(records),
        "records": records,
        "safety": {
            "automatic_action": False,
            "irreversible_actions": "review-only",
            "current_meta_embedded": False,
        },
    }


def _pvp_inputs(record: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for league in ("great", "ultra", "little"):
        entry = record.get("pvp", {}).get(league, {})
        if entry.get("rank_percent") is None:
            continue
        result[league] = {
            "rank_percent": entry.get("rank_percent"),
            "rank_number": entry.get("rank_number"),
            "stat_product": entry.get("stat_product"),
            "dust_cost": entry.get("dust_cost"),
            "candy_cost": entry.get("candy_cost"),
            "evolution_name": entry.get("evolution_name"),
            "evolution_form": entry.get("evolution_form"),
        }
    return result


def publish_recommendation_queues(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Publish #64 explainable review queues using only collection facts."""
    records = _load(output_dir / "data" / "pokemon.json")["records"]
    quality = _load(output_dir / "data" / "scan-quality-report.json")
    knowledge, exact, by_dex = _knowledge_context(output_dir)
    recommendations_dir = output_dir / "data" / "recommendations"
    shutil.rmtree(recommendations_dir, ignore_errors=True)
    recommendations_dir.mkdir(parents=True, exist_ok=True)

    quality_by_id: dict[str, list[str]] = defaultdict(list)
    for finding in quality.get("findings", []):
        record_id = finding.get("record_id")
        if record_id and finding.get("suggested_action") in {"rescan", "review"}:
            quality_by_id[str(record_id)].append(str(finding.get("reason_code") or "scan_quality_finding"))

    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(int(record["pokemon_number"]), _form_key(record.get("form")))].append(record)

    queues: dict[str, tuple[str, list[dict[str, Any]]]] = {
        "rescan": ("Records with missing or scan-quality evidence that should be reviewed or rescanned before consequential decisions.", []),
        "pvp-candidates": (f"Owned records with a Poke Genie league percentile of at least {HIGH_PVP_PERCENTILE:g}, or explicitly marked for PvP use. This is IV/build data, not current meta strength.", []),
        "raid-investment-inputs": ("High-IV or Shadow owned records with known moves that may be joined to fresh raid data later. Inclusion is not a raid-strength claim.", []),
        "evolution-review": ("Owned records with an evolution target represented by Poke Genie or the versioned species-family snapshot.", []),
        "duplicate-review": ("Owned species/form groups with more than one canonical record. Duplicate status alone is never a transfer recommendation.", []),
        "resource-review": ("Owned records with large known Poke Genie build costs or large known second-move Stardust costs that merit resource review.", []),
    }

    for record in records:
        record_id = _record_id(record)
        scan_reasons = missing_scan_reasons(record)
        quality_reasons = quality_by_id.get(record_id, [])
        if scan_reasons or quality_reasons:
            queues["rescan"][1].append(_record_ref(
                record,
                reasons=[*(f"missing_{value.replace('-', '_')}" for value in scan_reasons), *quality_reasons],
                warnings=_warning_codes(record),
                inputs={"scan_quality_reasons": quality_reasons},
            ))

        pvp = _pvp_inputs(record)
        high_leagues = [league for league, value in pvp.items() if (value.get("rank_percent") or 0) >= HIGH_PVP_PERCENTILE]
        marked = bool(record.get("status", {}).get("marked_for_pvp"))
        if high_leagues or marked:
            reasons = [f"high_pvp_percentile_{league}" for league in high_leagues]
            if marked:
                reasons.append("marked_for_pvp_use")
            queues["pvp-candidates"][1].append(_record_ref(record, reasons=reasons, warnings=_warning_codes(record), inputs={"pvp": pvp}))

        iv_percent = record.get("ivs", {}).get("average_percent")
        shadow = record.get("status", {}).get("shadow_purified") == "shadow"
        moves = record.get("moves", {})
        if moves.get("fast") and moves.get("charged") and ((iv_percent is not None and iv_percent >= 90) or shadow):
            reasons = (["high_iv_percent"] if iv_percent is not None and iv_percent >= 90 else []) + (["shadow"] if shadow else [])
            known = _knowledge_for(record, exact, by_dex)
            queues["raid-investment-inputs"][1].append(_record_ref(
                record,
                reasons=reasons,
                warnings=_warning_codes(record),
                inputs={
                    "iv_percent": iv_percent,
                    "moves": {"fast": moves.get("fast"), "charged": moves.get("charged"), "charged_second": moves.get("charged_second")},
                    "types": known.get("types") if known else None,
                    "base_attack": known.get("base_stats", {}).get("attack") if known else None,
                    "knowledge_dataset_version": knowledge.get("dataset_version"),
                },
            ))

        known = _knowledge_for(record, exact, by_dex)
        evolution_ids = list(known.get("family", {}).get("evolution_species_ids", [])) if known else []
        pvp_evolutions = sorted({value.get("evolution_name") for value in pvp.values() if value.get("evolution_name")})
        if evolution_ids or pvp_evolutions:
            queues["evolution-review"][1].append(_record_ref(
                record,
                reasons=["versioned_family_evolution_available"] if evolution_ids else ["poke_genie_evolution_target"],
                warnings=_warning_codes(record),
                inputs={"family_evolution_species_ids": evolution_ids, "poke_genie_evolution_names": pvp_evolutions},
            ))

        group = grouped[(int(record["pokemon_number"]), _form_key(record.get("form")))]
        if len(group) > 1:
            queues["duplicate-review"][1].append(_record_ref(
                record,
                reasons=["duplicate_species_form"],
                warnings=_warning_codes(record),
                inputs={"group_count": len(group), "group_record_ids": [_record_id(item) for item in group]},
            ))

        costly: list[str] = []
        for league, value in pvp.items():
            if value.get("dust_cost") is not None and value["dust_cost"] >= HIGH_PVP_BUILD_DUST:
                costly.append(f"high_build_cost_{league}_stardust")
            if value.get("candy_cost") is not None and value["candy_cost"] >= HIGH_PVP_BUILD_CANDY:
                costly.append(f"high_build_cost_{league}_candy")
        second_move_dust = known.get("second_charged_move_cost", {}).get("stardust") if known else None
        if second_move_dust is not None and second_move_dust >= HIGH_SECOND_MOVE_DUST and not moves.get("charged_second"):
            costly.append("high_second_move_stardust_cost")
        if costly:
            queues["resource-review"][1].append(_record_ref(
                record,
                reasons=costly,
                warnings=_warning_codes(record),
                inputs={"pvp": pvp, "second_charged_move_stardust": second_move_dust},
            ))

    index_entries = []
    for name, (definition, items) in queues.items():
        items.sort(key=lambda item: (item["pokemon_number"], item["name"].casefold(), -(item.get("cp") or 0), item["record_id"]))
        payload = _queue_payload(manifest, name, definition, items)
        path = recommendations_dir / f"{name}.json"
        _write(path, payload)
        index_entries.append({
            "name": name,
            "path": f"data/recommendations/{name}.json",
            "record_count": len(items),
            "definition": definition,
        })

    index = {
        "schema_version": RECOMMENDATION_SCHEMA_VERSION,
        "decision_support_version": DECISION_SUPPORT_VERSION,
        "build_id": manifest["build_id"],
        "current_meta_embedded": False,
        "queue_count": len(index_entries),
        "queues": index_entries,
    }
    _write(recommendations_dir / "index.json", index)
    return index


def _candidate(record: Mapping[str, Any], *, feed: str, knowledge: Mapping[str, Any] | None, eligibility: Mapping[str, Any], warnings: Iterable[str] = (), extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    item = {
        "record_id": _record_id(record),
        "pokemon_number": record["pokemon_number"],
        "name": record["name"],
        "form": record.get("form"),
        "feed": feed,
        "cp": record.get("cp"),
        "hp": record.get("hp"),
        "level": record.get("level"),
        "ivs": record.get("ivs"),
        "moves": record.get("moves"),
        "status": record.get("status"),
        "eligibility": dict(eligibility),
        "warnings": sorted(set(warnings)),
        "knowledge": {
            "species_id": knowledge.get("species_id"),
            "types": knowledge.get("types"),
            "base_stats": knowledge.get("base_stats"),
        } if knowledge else None,
    }
    if extra:
        item.update(extra)
    return item


def _candidate_payload(manifest: Mapping[str, Any], feed: str, definition: str, candidates: list[dict[str, Any]], *, status: str = "available", unavailable_reason: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "decision_support_version": DECISION_SUPPORT_VERSION,
        "build_id": manifest["build_id"],
        "feed": feed,
        "status": status,
        "definition": definition,
        "unavailable_reason": unavailable_reason,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "current_meta_embedded": False,
    }


def publish_candidate_feeds(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Publish #66 owned-Pokémon candidate inputs for future team builders."""
    records = _load(output_dir / "data" / "pokemon.json")["records"]
    knowledge, exact, by_dex = _knowledge_context(output_dir)
    candidates_dir = output_dir / "data" / "candidates"
    shutil.rmtree(candidates_dir, ignore_errors=True)
    candidates_dir.mkdir(parents=True, exist_ok=True)

    feeds: dict[str, tuple[str, list[dict[str, Any]], str, str | None]] = {}
    for league in ("great", "ultra", "little"):
        definition = f"Owned records with Poke Genie {league.title()} League IV/build data. This feed does not rank current meta strength."
        items: list[dict[str, Any]] = []
        for record in records:
            pvp = record.get("pvp", {}).get(league, {})
            if pvp.get("rank_percent") is None:
                continue
            known = _knowledge_for(record, exact, by_dex)
            items.append(_candidate(
                record,
                feed=f"{league}-league",
                knowledge=known,
                eligibility={"league": league, "basis": "poke_genie_rank_present", "eligible_input": True},
                warnings=_warning_codes(record),
                extra={"pvp": dict(pvp)},
            ))
        items.sort(key=lambda item: (-(item.get("pvp", {}).get("rank_percent") or 0), item.get("pvp", {}).get("rank_number") or 999999, -(item.get("cp") or 0), item["record_id"]))
        feeds[f"{league}-league"] = (definition, items, "available", None)

    master: list[dict[str, Any]] = []
    for record in records:
        ivs = record.get("ivs", {})
        level = record.get("level", {})
        exact_ivs = all(ivs.get(key) is not None for key in ("attack", "defense", "stamina"))
        known_level = level.get("minimum") is not None and level.get("maximum") is not None
        if not (exact_ivs and known_level):
            continue
        known = _knowledge_for(record, exact, by_dex)
        master.append(_candidate(
            record,
            feed="master-league",
            knowledge=known,
            eligibility={"league": "master", "basis": "uncapped_complete_iv_inventory_input", "eligible_input": True},
            warnings=_warning_codes(record),
            extra={"pvp": None, "ranking_basis": "owned_iv_total_then_cp_only"},
        ))
    master.sort(key=lambda item: (-(item.get("ivs", {}).get("total") or -1), -(item.get("cp") or 0), item["record_id"]))
    feeds["master-league"] = ("Owned records with complete exact IV and level data for uncapped-league comparison. Current Master League/cup relevance is external data.", master, "available", None)

    raid: list[dict[str, Any]] = []
    rocket: list[dict[str, Any]] = []
    mega: list[dict[str, Any]] = []
    transform_targets_by_dex: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for dex, entries in by_dex.items():
        for entry in entries:
            kind = entry.get("transformation", {}).get("kind")
            if kind in {"mega", "primal"}:
                transform_targets_by_dex[dex].append({"species_id": entry.get("species_id"), "display_name": entry.get("display_name"), "kind": kind})

    for record in records:
        known = _knowledge_for(record, exact, by_dex)
        moves = record.get("moves", {})
        scan_warnings = _warning_codes(record)
        if moves.get("fast") and moves.get("charged"):
            raid.append(_candidate(
                record,
                feed="raid-attacker-inputs",
                knowledge=known,
                eligibility={"basis": "owned_record_with_known_moves", "eligible_input": True},
                warnings=scan_warnings,
                extra={"strength_ranking": None, "strength_ranking_status": "requires_fresh_external_simulation_or_rankings"},
            ))
            rocket.append(_candidate(
                record,
                feed="rocket-battle-inputs",
                knowledge=known,
                eligibility={"basis": "owned_record_with_known_moves", "eligible_input": True},
                warnings=scan_warnings,
                extra={"rocket_matchup_rank": None, "rocket_matchup_rank_status": "requires_fresh_external_lineup_and_battle_data"},
            ))
        targets = transform_targets_by_dex.get(int(record["pokemon_number"]), [])
        if targets:
            mega.append(_candidate(
                record,
                feed="mega-candidates",
                knowledge=known,
                eligibility={"basis": "versioned_same_dex_transformation_mapping", "eligible_input": True},
                warnings=scan_warnings,
                extra={"transformation_targets": targets},
            ))

    raid.sort(key=lambda item: (-(((item.get("knowledge") or {}).get("base_stats") or {}).get("attack") or 0), -(item.get("cp") or 0), item["record_id"]))
    rocket.sort(key=lambda item: (-(item.get("cp") or 0), item["record_id"]))
    mega.sort(key=lambda item: (item["pokemon_number"], -(item.get("cp") or 0), item["record_id"]))
    feeds["raid-attacker-inputs"] = ("Owned records with known fast and charged moves plus stable species facts, intended for joining to fresh raid data.", raid, "available", None)
    feeds["rocket-battle-inputs"] = ("Owned records with known moves intended for joining to fresh Rocket lineups and battle data.", rocket, "available", None)
    feeds["mega-candidates"] = ("Owned base records whose Pokédex number has a Mega or Primal transformation in the versioned species snapshot.", mega, "available", None)
    feeds["dynamax-candidates"] = ("Dynamax ownership inputs when a reliable owned-status field exists.", [], "unavailable", "The normalized Poke Genie collection does not reliably encode owned Dynamax status.")
    feeds["gigantamax-candidates"] = ("Gigantamax ownership inputs when a reliable owned-status field exists.", [], "unavailable", "The normalized Poke Genie collection does not reliably encode owned Gigantamax status.")

    index_entries = []
    for name, (definition, items, status, unavailable_reason) in feeds.items():
        payload = _candidate_payload(manifest, name, definition, items, status=status, unavailable_reason=unavailable_reason)
        _write(candidates_dir / f"{name}.json", payload)
        index_entries.append({"name": name, "path": f"data/candidates/{name}.json", "status": status, "candidate_count": len(items), "definition": definition, "unavailable_reason": unavailable_reason})

    index = {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "decision_support_version": DECISION_SUPPORT_VERSION,
        "build_id": manifest["build_id"],
        "knowledge_dataset_version": knowledge.get("dataset_version"),
        "feed_count": len(index_entries),
        "feeds": index_entries,
        "current_meta_embedded": False,
    }
    _write(candidates_dir / "index.json", index)
    return index


def _pvp_build_costs(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    builds: list[dict[str, Any]] = []
    for league in ("great", "ultra", "little"):
        pvp = record.get("pvp", {}).get(league, {})
        if pvp.get("rank_percent") is None:
            continue
        builds.append({
            "league": league,
            "target_evolution_name": pvp.get("evolution_name"),
            "target_evolution_form": pvp.get("evolution_form"),
            "rank_percent": pvp.get("rank_percent"),
            "rank_number": pvp.get("rank_number"),
            "stardust_cost": pvp.get("dust_cost"),
            "regular_candy_cost": pvp.get("candy_cost"),
            "xl_candy_cost": None,
            "xl_candy_cost_status": "not_provided_by_poke_genie_export",
            "basis": "poke_genie_export",
            "basis_version": "source-export-field",
        })
    return builds


def build_investment_inputs(record: Mapping[str, Any], knowledge: Mapping[str, Any] | None, *, knowledge_dataset_version: str | None) -> dict[str, Any]:
    """Create #67 observed/calculated cost inputs for one canonical record."""
    moves = record.get("moves", {})
    second_move = knowledge.get("second_charged_move_cost", {}) if knowledge else {}
    family = knowledge.get("family", {}) if knowledge else {}
    return {
        "record_id": _record_id(record),
        "pokemon_number": record["pokemon_number"],
        "name": record["name"],
        "form": record.get("form"),
        "observed": {
            "cp": record.get("cp"),
            "level": record.get("level"),
            "moves": moves,
            "second_charged_move_unlocked": bool(moves.get("charged_second")),
            "status": record.get("status"),
            "ivs": record.get("ivs"),
        },
        "derived": {
            "pvp_builds": _pvp_build_costs(record),
            "second_charged_move": {
                "already_unlocked": bool(moves.get("charged_second")),
                "listed_stardust_cost": second_move.get("stardust"),
                "listed_regular_candy_cost": second_move.get("candy"),
                "regular_candy_cost_status": second_move.get("candy_status") or ("unavailable" if knowledge else "knowledge_join_unavailable"),
                "basis": "versioned_species_mechanics_snapshot" if knowledge else "unavailable",
                "basis_version": knowledge_dataset_version if knowledge else None,
            },
            "evolution": {
                "evolution_species_ids": list(family.get("evolution_species_ids", [])),
                "regular_candy_cost": family.get("evolution_candy_cost"),
                "special_requirements": family.get("special_requirements"),
                "basis": "versioned_species_mechanics_snapshot" if knowledge else "unavailable",
                "basis_version": knowledge_dataset_version if knowledge else None,
            },
            "arbitrary_power_up_cost": None,
            "arbitrary_power_up_cost_status": "not_calculated_without_a_versioned_power_up_cost_table",
            "elite_tm_recommendation": None,
            "elite_tm_recommendation_status": "intentionally_not_derived_from_static_cost_data",
        },
        "warnings": _warning_codes(record) + (["knowledge_join_unavailable"] if knowledge is None else []),
        "model": {
            "version": INVESTMENT_MODEL_VERSION,
            "observed_source": "normalized_poke_genie_export",
            "calculated_values": "Only direct Poke Genie target-build fields and versioned species/mechanics facts are exposed; unavailable inputs remain null.",
        },
    }


def publish_investment_inputs(output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Publish #67 collection-aware investment planner inputs."""
    records = _load(output_dir / "data" / "pokemon.json")["records"]
    knowledge, exact, by_dex = _knowledge_context(output_dir)
    investments_dir = output_dir / "data" / "investments"
    shutil.rmtree(investments_dir, ignore_errors=True)
    investments_dir.mkdir(parents=True, exist_ok=True)

    items = [
        build_investment_inputs(record, _knowledge_for(record, exact, by_dex), knowledge_dataset_version=knowledge.get("dataset_version"))
        for record in records
    ]
    items.sort(key=lambda item: (item["pokemon_number"], item["name"].casefold(), item["record_id"]))
    payload = {
        "schema_version": "1.0.0",
        "model_version": INVESTMENT_MODEL_VERSION,
        "build_id": manifest["build_id"],
        "knowledge_dataset_version": knowledge.get("dataset_version"),
        "record_count": len(items),
        "records": items,
        "limitations": [
            "Player Stardust/Candy/XL balances are not present in the Poke Genie export and are never estimated.",
            "XL Candy and arbitrary power-up costs remain unavailable unless a versioned source supplies the necessary inputs.",
            "Cost data is not a recommendation to spend resources or use an Elite TM.",
        ],
    }
    _write(investments_dir / "records.json", payload)
    index = {
        "schema_version": "1.0.0",
        "model_version": INVESTMENT_MODEL_VERSION,
        "build_id": manifest["build_id"],
        "record_count": len(items),
        "records": "data/investments/records.json",
        "basis": ["normalized_poke_genie_export", "versioned_species_mechanics_snapshot"],
    }
    _write(investments_dir / "index.json", index)
    return index


RULES = [
    {
        "id": "rescan_before_decision",
        "version": "1",
        "action_class": "rescan",
        "description": "Request a rescan/review when required exact scan inputs are incomplete.",
        "irreversible": False,
    },
    {
        "id": "owned_pvp_rank_leader",
        "version": "1",
        "action_class": "compare",
        "description": "Identify the highest Poke Genie IV percentile among owned copies of the same species/form for a league.",
        "irreversible": False,
    },
    {
        "id": "lowest_known_build_cost",
        "version": "1",
        "action_class": "compare",
        "description": "Identify the lowest known Poke Genie Stardust/Candy target-build cost among comparable owned copies.",
        "irreversible": False,
    },
    {
        "id": "owned_copy_dominance",
        "version": "1",
        "action_class": "compare",
        "description": "Flag a copy as lower priority only when another owned copy has at least as high a PvP percentile and no greater known build costs, with one strict improvement.",
        "irreversible": False,
    },
    {
        "id": "conflicting_objectives",
        "version": "1",
        "action_class": "review",
        "description": "Require review when the highest IV rank and cheapest known build are different owned copies.",
        "irreversible": False,
    },
    {
        "id": "evolution_review_available",
        "version": "1",
        "action_class": "review",
        "description": "Expose versioned evolution branches without automatically evolving a record.",
        "irreversible": False,
    },
    {
        "id": "current_meta_required",
        "version": "1",
        "action_class": "review",
        "description": "Block current-meta conclusions unless a separate external-data snapshot is fresh and authoritative enough for the requested claim.",
        "irreversible": False,
    },
]


def _known_cost(build: Mapping[str, Any]) -> tuple[int, int] | None:
    dust = build.get("stardust_cost")
    candy = build.get("regular_candy_cost")
    if dust is None or candy is None:
        return None
    return int(dust), int(candy)


def _dominates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_rank = left.get("rank_percent")
    right_rank = right.get("rank_percent")
    left_cost = _known_cost(left)
    right_cost = _known_cost(right)
    if left_rank is None or right_rank is None or left_cost is None or right_cost is None:
        return False
    no_worse = left_rank >= right_rank and left_cost[0] <= right_cost[0] and left_cost[1] <= right_cost[1]
    strictly_better = left_rank > right_rank or left_cost[0] < right_cost[0] or left_cost[1] < right_cost[1]
    return bool(no_worse and strictly_better)


def build_reasoning_results(
    records: list[dict[str, Any]],
    investment_records: list[dict[str, Any]],
    *,
    build_id: str,
    external_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run #73 deterministic, traceable collection rules."""
    investments = {item["record_id"]: item for item in investment_records}
    groups: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[(int(record["pokemon_number"]), _form_key(record.get("form")))].append(record)

    external_state = str((external_context or {}).get("overall_freshness") or "unavailable")
    results: list[dict[str, Any]] = []
    for record in records:
        record_id = _record_id(record)
        inv = investments[record_id]
        recommendations: list[dict[str, Any]] = []
        missing = [f"missing_{item.replace('-', '_')}" for item in missing_scan_reasons(record)]
        if missing:
            recommendations.append({
                "action_class": "rescan",
                "recommendation": "review_or_rescan_before_consequential_decision",
                "rules_triggered": ["rescan_before_decision"],
                "inputs_used": {"missing_scan_inputs": missing},
                "assumptions": [],
                "missing_information": missing,
                "warnings": ["Irreversible collection actions should remain blocked until required scan facts are available."],
                "confidence": "high",
            })

        group = groups[(int(record["pokemon_number"]), _form_key(record.get("form")))]
        for league in ("great", "ultra", "little"):
            comparable: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for other in group:
                other_inv = investments[_record_id(other)]
                build = next((item for item in other_inv["derived"]["pvp_builds"] if item["league"] == league), None)
                if build is not None:
                    comparable.append((other, build))
            current_build = next((item for item in inv["derived"]["pvp_builds"] if item["league"] == league), None)
            if current_build is None or not comparable:
                continue

            ranked = [item for item in comparable if item[1].get("rank_percent") is not None]
            best_rank = max((item[1]["rank_percent"] for item in ranked), default=None)
            rank_leaders = [item for item in ranked if item[1].get("rank_percent") == best_rank]
            known_cost = [item for item in comparable if _known_cost(item[1]) is not None]
            cheapest_cost = min((_known_cost(item[1]) for item in known_cost), default=None)
            cheapest = [item for item in known_cost if _known_cost(item[1]) == cheapest_cost] if cheapest_cost is not None else []

            if best_rank is not None and current_build.get("rank_percent") == best_rank:
                recommendations.append({
                    "action_class": "compare",
                    "recommendation": f"owned_{league}_pvp_rank_leader",
                    "rules_triggered": ["owned_pvp_rank_leader"],
                    "inputs_used": {"league": league, "rank_percent": best_rank, "compared_record_ids": [_record_id(item[0]) for item in comparable]},
                    "assumptions": ["Poke Genie percentile is used only as an IV/build metric, not current meta strength."],
                    "missing_information": [],
                    "warnings": [],
                    "confidence": "high",
                })
            if cheapest_cost is not None and _known_cost(current_build) == cheapest_cost:
                recommendations.append({
                    "action_class": "compare",
                    "recommendation": f"lowest_known_{league}_build_cost",
                    "rules_triggered": ["lowest_known_build_cost"],
                    "inputs_used": {"league": league, "stardust_cost": cheapest_cost[0], "regular_candy_cost": cheapest_cost[1]},
                    "assumptions": ["Only Poke Genie exported target-build costs are compared."],
                    "missing_information": ["xl_candy_cost"],
                    "warnings": [],
                    "confidence": "high",
                })

            dominators = [other for other, build in comparable if _record_id(other) != record_id and _dominates(build, current_build)]
            if dominators:
                recommendations.append({
                    "action_class": "compare",
                    "recommendation": "lower_priority_than_an_owned_copy_for_known_pvp_rank_and_cost_inputs",
                    "rules_triggered": ["owned_copy_dominance"],
                    "inputs_used": {"league": league, "dominating_record_ids": [_record_id(item) for item in dominators]},
                    "assumptions": ["Dominance is limited to Poke Genie percentile and known Stardust/Candy build costs."],
                    "missing_information": ["current_meta_strength", "team_fit", "breakpoints_bulkpoints", "xl_candy_cost"],
                    "warnings": ["This comparison is not a transfer recommendation."],
                    "confidence": "medium",
                })

            rank_ids = {_record_id(item[0]) for item in rank_leaders}
            cheap_ids = {_record_id(item[0]) for item in cheapest}
            if rank_ids and cheap_ids and rank_ids.isdisjoint(cheap_ids) and record_id in rank_ids | cheap_ids:
                recommendations.append({
                    "action_class": "review",
                    "recommendation": "conflicting_rank_and_cost_objectives",
                    "rules_triggered": ["conflicting_objectives"],
                    "inputs_used": {"league": league, "rank_leader_ids": sorted(rank_ids), "lowest_cost_ids": sorted(cheap_ids)},
                    "assumptions": [],
                    "missing_information": ["user_priority_between_rank_and_cost"],
                    "warnings": ["No deterministic winner exists until the objective is specified."],
                    "confidence": "high",
                })

        evolution = inv["derived"]["evolution"]
        if evolution.get("evolution_species_ids"):
            recommendations.append({
                "action_class": "review",
                "recommendation": "evolution_options_available_for_review",
                "rules_triggered": ["evolution_review_available"],
                "inputs_used": {"evolution_species_ids": evolution["evolution_species_ids"]},
                "assumptions": [],
                "missing_information": ["evolution_candy_cost"] if evolution.get("regular_candy_cost") is None else [],
                "warnings": ["Evolution is irreversible; this rule only exposes branches."],
                "confidence": "high",
            })

        recommendations.append({
            "action_class": "review",
            "recommendation": "current_meta_conclusion_blocked" if external_state != "fresh" else "fresh_external_framework_available_but_no_meta_rule_selected",
            "rules_triggered": ["current_meta_required"],
            "inputs_used": {"external_freshness": external_state},
            "assumptions": [],
            "missing_information": ["fresh_current_game_dataset"] if external_state != "fresh" else ["use_case_specific_external_dataset"],
            "warnings": ["Current PvP, raid, event, move-availability, and Rocket claims require an explicitly sourced freshness-checked dataset."],
            "confidence": "high",
        })

        results.append({
            "record_id": record_id,
            "pokemon_number": record["pokemon_number"],
            "name": record["name"],
            "form": record.get("form"),
            "recommendations": recommendations,
            "irreversible_actions_blocked": ["transfer", "purify", "elite_tm", "evolve", "power_up_spend"],
            "source_versions": {
                "reasoning_engine": REASONING_ENGINE_VERSION,
                "investment_model": INVESTMENT_MODEL_VERSION,
                "build_id": build_id,
            },
        })

    results.sort(key=lambda item: (item["pokemon_number"], item["name"].casefold(), item["record_id"]))
    return {
        "schema_version": "1.0.0",
        "engine_version": REASONING_ENGINE_VERSION,
        "build_id": build_id,
        "external_freshness": external_state,
        "record_count": len(results),
        "records": results,
        "safety": {
            "destructive_actions_emitted": False,
            "irreversible_spend_commands_emitted": False,
            "current_meta_requires_external_freshness": True,
        },
    }


def publish_reasoning(output_dir: Path, manifest: Mapping[str, Any], *, external_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    records = _load(output_dir / "data" / "pokemon.json")["records"]
    investment_payload = _load(output_dir / "data" / "investments" / "records.json")
    reasoning_dir = output_dir / "data" / "reasoning"
    shutil.rmtree(reasoning_dir, ignore_errors=True)
    reasoning_dir.mkdir(parents=True, exist_ok=True)
    rules = {
        "schema_version": "1.0.0",
        "engine_version": REASONING_ENGINE_VERSION,
        "rules": RULES,
        "forbidden_automatic_actions": ["transfer", "purify", "elite_tm", "evolve", "power_up_spend"],
    }
    results = build_reasoning_results(records, investment_payload["records"], build_id=str(manifest["build_id"]), external_context=external_context)
    _write(reasoning_dir / "rules.json", rules)
    _write(reasoning_dir / "records.json", results)
    index = {
        "schema_version": "1.0.0",
        "engine_version": REASONING_ENGINE_VERSION,
        "build_id": manifest["build_id"],
        "rules": "data/reasoning/rules.json",
        "records": "data/reasoning/records.json",
        "record_count": results["record_count"],
        "deterministic": True,
        "llm_required": False,
    }
    _write(reasoning_dir / "index.json", index)
    return index


def publish_decision_support(output_dir: Path, manifest: Mapping[str, Any], *, external_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Publish #64, #66, #67, then #73 in dependency order."""
    recommendation_index = publish_recommendation_queues(output_dir, manifest)
    candidate_index = publish_candidate_feeds(output_dir, manifest)
    investment_index = publish_investment_inputs(output_dir, manifest)
    reasoning_index = publish_reasoning(output_dir, manifest, external_context=external_context)
    return {
        "recommendations": recommendation_index,
        "candidates": candidate_index,
        "investments": investment_index,
        "reasoning": reasoning_index,
    }
