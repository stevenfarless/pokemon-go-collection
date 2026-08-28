"""Publish private two-player Trade Matcher and local Trainer Resource Vault contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

try:
    from . import manifest_registry
except ImportError:
    import manifest_registry

LAB_VERSION = "1.0.0"
TRADE_VERSION = "1.0.0"
RESOURCE_VERSION = "1.0.0"
BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"

RESOURCE_TYPES = [
    {"id": "stardust", "label": "Stardust", "scope": "global", "scarcity": "high"},
    {"id": "rare_candy", "label": "Rare Candy", "scope": "global", "scarcity": "high"},
    {"id": "rare_candy_xl", "label": "Rare Candy XL", "scope": "global", "scarcity": "very-high"},
    {"id": "fast_tm", "label": "Fast TM", "scope": "global", "scarcity": "normal"},
    {"id": "charged_tm", "label": "Charged TM", "scope": "global", "scarcity": "normal"},
    {"id": "elite_fast_tm", "label": "Elite Fast TM", "scope": "global", "scarcity": "very-high"},
    {"id": "elite_charged_tm", "label": "Elite Charged TM", "scope": "global", "scarcity": "very-high"},
    {"id": "max_particles", "label": "Max Particles", "scope": "global", "scarcity": "high"},
    {"id": "silver_bottle_cap", "label": "Silver Bottle Cap", "scope": "global", "scarcity": "very-high", "expiration_supported": True},
    {"id": "gold_bottle_cap", "label": "Gold Bottle Cap", "scope": "global", "scarcity": "very-high", "expiration_supported": True},
    {"id": "raid_pass", "label": "Raid Pass", "scope": "global", "scarcity": "normal"},
    {"id": "premium_battle_pass", "label": "Premium Battle Pass", "scope": "global", "scarcity": "high"},
    {"id": "remote_raid_pass", "label": "Remote Raid Pass", "scope": "global", "scarcity": "high"},
    {"id": "species_candy", "label": "Species Candy", "scope": "species", "scarcity": "contextual"},
    {"id": "species_candy_xl", "label": "Species Candy XL", "scope": "species", "scarcity": "high"},
    {"id": "mega_energy", "label": "Mega Energy", "scope": "species", "scarcity": "contextual"},
    {"id": "incubator", "label": "Incubator", "scope": "optional", "scarcity": "contextual"},
]


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def build_trade_contract(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": TRADE_VERSION,
        "lab_version": LAB_VERSION,
        "build_id": manifest["build_id"],
        "title": "Private two-player Trade Matcher",
        "inputs": {
            "player_a": {"resource": "data/pokemon.json", "identity": "canonical exact owned record IDs"},
            "player_b": {
                "source": "browser-selected Poke Genie CSV",
                "preflight_contract": "data/preflight-contract.json",
                "identity": "ephemeral guest-row-N only",
                "persistence": "none",
            },
            "knowledge": "data/knowledge/species-index.json",
        },
        "privacy": {
            "guest_bytes_leave_browser": False,
            "guest_rows_persisted": False,
            "guest_rows_cached": False,
            "guest_rows_published": False,
            "clear_session_discards_guest": True,
        },
        "matching": {
            "possible_mutual_wins_first": True,
            "surplus_threshold": 2,
            "exact_player_a_records": True,
            "player_b_collector_unknowns": ["shiny", "costume", "background", "dynamax", "gigantamax", "favorite", "trade_history"],
            "unknown_blocks_expendable_claim": True,
            "special_trade": "May be flagged only from explicit supported species/category evidence; eligibility and cost must still be confirmed in Pokémon GO.",
            "lucky": "No Lucky outcome is guaranteed.",
            "stardust": "No exact trade Stardust cost is calculated without complete current friendship/history inputs.",
            "filters": {
                "scope": "current in-memory guest comparison only",
                "goal": "case-insensitive species/form text within a proposed pair",
                "family": "versioned knowledge family id",
                "rarity": "explicit source-tag categories only; unsupported classifications remain unknown",
                "manual_exclusions_persisted": False,
            },
        },
        "handoff": {
            "action_packs": "action-packs.html",
            "player_a": "narrow exact-owned locator when representable",
            "player_b": "species/form review helper; guest rows have no canonical record ID",
        },
    }


def build_resource_contract(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RESOURCE_VERSION,
        "lab_version": LAB_VERSION,
        "build_id": manifest["build_id"],
        "title": "Trainer Resource Vault",
        "storage": {
            "key": "pokemon-go-collection:resource-vault:v1",
            "schema_version": 1,
            "local_only": True,
            "unified_backup": True,
            "bounded_history": 12,
        },
        "resources": RESOURCE_TYPES,
        "semantics": {
            "missing_balance": "unknown, never zero",
            "reserve": "amount intentionally unavailable to ordinary plans",
            "commitment": "named local reservation that participates in conflict detection",
            "plan": "what-if cost only; never claims the in-game balance changed",
            "allocation": "deterministic priority/order evaluation across selected plans",
        },
        "safety": {
            "infer_balances_from_collection": False,
            "mutate_canonical_collection": False,
            "double_spend_silent": False,
            "scarce_resources": ["rare_candy_xl", "elite_fast_tm", "elite_charged_tm", "silver_bottle_cap", "gold_bottle_cap"],
            "scarce_resource_warning_required": True,
        },
        "consumers": ["resource-optimizer", "decision-card", "move-lab", "mega-primal-lab", "max-battle-lab", "hyper-training-planner"],
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
        "trade-resource-labs-index.schema.json": _schema(
            "trade-resource-labs-index",
            ["schema_version", "build_id", "labs"],
            {"schema_version": string, "build_id": build, "labs": {"type": "object"}},
        ),
        "trade-matcher-contract.schema.json": _schema(
            "trade-matcher-contract",
            ["schema_version", "build_id", "inputs", "privacy", "matching", "handoff"],
            {"schema_version": string, "build_id": build, "inputs": {"type": "object"}, "privacy": {"type": "object"}, "matching": {"type": "object"}, "handoff": {"type": "object"}},
        ),
        "resource-vault-contract.schema.json": _schema(
            "resource-vault-contract",
            ["schema_version", "build_id", "storage", "resources", "semantics", "safety"],
            {"schema_version": string, "build_id": build, "storage": {"type": "object"}, "resources": {"type": "array"}, "semantics": {"type": "object"}, "safety": {"type": "object"}},
        ),
    }


def _register_contracts() -> None:
    manifest_registry._SCHEMA_MAP.update({
        "data/trade-resource-labs/index.json": "data/trade-resource-labs-index.schema.json",
        "data/trade-matcher-contract.json": "data/trade-matcher-contract.schema.json",
        "data/resource-vault-contract.json": "data/resource-vault-contract.schema.json",
    })
    manifest_registry._STABLE_NAMES.update({
        "data/trade-resource-labs/index.json": "trade_resource_labs_index",
        "data/trade-matcher-contract.json": "trade_matcher_contract",
        "data/resource-vault-contract.json": "resource_vault_contract",
        "data/trade-resource-labs-index.schema.json": "trade_resource_labs_index_schema",
        "data/trade-matcher-contract.schema.json": "trade_matcher_contract_schema",
        "data/resource-vault-contract.schema.json": "resource_vault_contract_schema",
    })


def _page(output_dir: Path, filename: str, title: str, mount_id: str, description: str, body: str) -> None:
    html = f'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title><link rel="stylesheet" href="assets/trade-resource-labs.css" data-trade-resource-style></head>
<body><main class="trade-resource-page"><header class="trade-resource-header"><p><a href="tools.html">Tools</a> · <a href="index.html">Collection</a> · <a href="trade-matcher.html">Trade Matcher</a> · <a href="resource-vault.html">Resource Vault</a> · <a href="action-packs.html">Action Packs</a></p><h1>{title}</h1><p>{description}</p></header>{body}<div id="{mount_id}" aria-live="polite"></div></main><script defer src="assets/trade-resource-labs.js" data-trade-resource-script></script></body></html>'''
    (output_dir / filename).write_text(html, encoding="utf-8", newline="\n")


def _install_tools_links(output_dir: Path) -> None:
    path = output_dir / "tools.html"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    if 'id="trade-resource-labs"' in source:
        return
    block = '''\n    <section id="trade-resource-labs" class="planner-card" aria-labelledby="trade-resource-labs-heading">
      <header><div><p class="eyebrow">#147/#148</p><h2 id="trade-resource-labs-heading">Trade and resource labs</h2></div></header>
      <p>Compare a guest Poke Genie export privately in this browser, or track scarce resources, reserves, commitments, and what-if plans without changing the canonical collection.</p>
      <p><a href="trade-matcher.html">Open private Trade Matcher</a> · <a href="resource-vault.html">Open Trainer Resource Vault</a></p>
    </section>\n'''
    marker = "  </main>"
    if marker not in source:
        raise ValueError("Generated tools page is missing its main closing tag")
    source = source.replace(marker, block + marker, 1)
    if 'data-trade-resource-tools' not in source:
        body_marker = "</body>"
        if body_marker not in source:
            raise ValueError("Generated tools page is missing its body closing tag")
        source = source.replace(body_marker, '  <script defer src="assets/trade-resource-labs.js" data-trade-resource-tools></script>\n</body>', 1)
    path.write_text(source, encoding="utf-8", newline="\n")


def publish(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    del repository_root
    _register_contracts()
    trade = build_trade_contract(manifest)
    vault = build_resource_contract(manifest)
    _write(output_dir / "data" / "trade-matcher-contract.json", trade)
    _write(output_dir / "data" / "resource-vault-contract.json", vault)
    index = {
        "schema_version": LAB_VERSION,
        "build_id": manifest["build_id"],
        "labs": {
            "trade_matcher": {"issue": 147, "page": "trade-matcher.html", "contract": "data/trade-matcher-contract.json"},
            "resource_vault": {"issue": 148, "page": "resource-vault.html", "contract": "data/resource-vault-contract.json"},
        },
    }
    _write(output_dir / "data" / "trade-resource-labs" / "index.json", index)
    for filename, schema in schemas().items():
        Draft202012Validator.check_schema(schema)
        _write(output_dir / "data" / filename, schema)

    trade_controls = '''<section class="trl-card" aria-labelledby="guest-heading"><h2 id="guest-heading">Player B guest export</h2><p class="trl-note">Selected CSV bytes stay in memory in this tab. They are not stored, cached, or uploaded.</p><label>Guest Poke Genie CSV <input id="trade-guest-file" type="file" accept=".csv,text/csv"></label><div class="trl-actions"><button id="trade-clear-guest" type="button">Clear guest session</button><button id="trade-export-shortlist" type="button" disabled>Export shortlist</button></div><p id="trade-guest-status" role="status">Choose a guest CSV to begin.</p></section><script defer src="assets/trade-matcher-filters.js" data-trade-matcher-filters></script>'''
    vault_controls = '''<section class="trl-card" aria-labelledby="vault-edit-heading"><h2 id="vault-edit-heading">Fast resource entry</h2><p class="trl-note">Blank means unknown, not zero. Values exist only in this browser and participate in the unified local-data backup.</p><div id="resource-fast-grid" class="trl-grid"></div><div class="trl-actions"><button id="resource-save" type="button">Save local vault</button><button id="resource-add-plan" type="button">Add what-if plan</button><button id="resource-snapshot" type="button">Save balance snapshot</button></div><p id="resource-status" role="status"></p></section>'''
    _page(output_dir, "trade-matcher.html", "Private two-player Trade Matcher", "trade-matcher-root", "Compare Player A's canonical collection with a guest Poke Genie CSV entirely in-browser. Suggestions are review-only and never promise trade cost, Lucky results, or post-trade IVs.", trade_controls)
    _page(output_dir, "resource-vault.html", "Trainer Resource Vault", "resource-vault-root", "Track only the scarce resources that materially affect plans. Missing balances remain unknown, reserves win, and competing plans cannot silently spend the same budget twice.", vault_controls)
    _install_tools_links(output_dir)

    llms = output_dir / "llms.txt"
    if llms.is_file():
        with llms.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "\nTrade and resource labs:\n"
                "- /trade-matcher.html uses /data/preflight-contract.json plus a browser-selected guest Poke Genie CSV. Guest rows remain ephemeral and are never part of the canonical API.\n"
                "- /data/trade-matcher-contract.json documents exact Player A IDs, guest uncertainty, privacy, review filters, and non-guaranteed trade/Lucky/cost semantics.\n"
                "- /resource-vault.html stores optional scarce-resource balances, reserves, commitments, and what-if plans only in browser-local state. Missing balances mean unknown, not zero.\n"
                "- /data/resource-vault-contract.json is the shared resource-budget contract for planning consumers.\n"
            )
    return index


__all__ = ["LAB_VERSION", "TRADE_VERSION", "RESOURCE_VERSION", "RESOURCE_TYPES", "build_trade_contract", "build_resource_contract", "schemas", "publish"]