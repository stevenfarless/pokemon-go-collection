"""Publish the safety-first Storage Cleanup Lab and reviewed Pokémon GO Search Builder."""

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
CLEANUP_VERSION = "1.0.0"
SEARCH_VERSION = "1.0.0"
BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _load_registry(repository_root: Path) -> dict[str, Any]:
    path = repository_root / "knowledge" / "search-operator-registry.json"
    if not path.is_file():
        raise ValueError("Missing reviewed Pokémon GO search operator registry")
    registry = json.loads(path.read_text(encoding="utf-8"))
    _validate_registry(registry)
    return registry


def _validate_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("authority") != "Official":
        raise ValueError("Search operator registry must be grounded in an Official source")
    source = registry.get("source") or {}
    if source.get("id") != "inventory-search" or not str(source.get("url") or "").startswith("https://niantic.helpshift.com/"):
        raise ValueError("Search operator registry must identify the reviewed official inventory-search source")
    boolean = registry.get("boolean") or {}
    if boolean.get("grouping_supported") is not False:
        raise ValueError("Undocumented parenthesized grouping must remain unsupported")
    if "&" not in (boolean.get("and") or []) or "!" != boolean.get("not"):
        raise ValueError("Search registry is missing documented AND/NOT semantics")
    operators = registry.get("operators") or []
    ids = [str(item.get("id") or "") for item in operators]
    if len(ids) != len(set(ids)) or not all(ids):
        raise ValueError("Search operator IDs must be non-empty and unique")
    required = {"cp", "hp", "dynamax", "gigantamax", "fusion", "hypertraining", "appraisal", "attribute-appraisal", "shiny", "costume", "background", "tradeevolve"}
    missing = sorted(required.difference(ids))
    if missing:
        raise ValueError("Search operator registry is missing reviewed operators: " + ", ".join(missing))
    fixtures = registry.get("semantic_fixtures")
    if not isinstance(fixtures, list) or len(fixtures) < 8:
        raise ValueError("Search operator registry requires a meaningful semantic fixture set before Verified exact is allowed")
    valid_ids = set(ids)
    for index, fixture in enumerate(fixtures, start=1):
        if not isinstance(fixture, Mapping) or not str(fixture.get("expression") or "").strip():
            raise ValueError(f"Search semantic fixture {index} has no expression")
        fixture_ids = fixture.get("operators")
        joins = fixture.get("joins")
        negated = fixture.get("negated")
        if not isinstance(fixture_ids, list) or not fixture_ids or any(str(value) not in valid_ids for value in fixture_ids):
            raise ValueError(f"Search semantic fixture {index} references an unknown operator")
        if not isinstance(joins, list) or not isinstance(negated, list) or len(negated) != len(fixture_ids):
            raise ValueError(f"Search semantic fixture {index} has inconsistent expected semantics")
        if len(joins) != max(0, len(fixture_ids) - 1):
            raise ValueError(f"Search semantic fixture {index} has an inconsistent join count")


def build_search_contract(manifest: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SEARCH_VERSION,
        "lab_version": LAB_VERSION,
        "build_id": manifest["build_id"],
        "title": "Current official Pokémon GO Search Builder",
        "registry": "data/search-operator-registry.json",
        "source": registry["source"],
        "reviewed_at": registry["reviewed_at"],
        "semantics": {
            "flat_boolean_only": True,
            "parenthesized_grouping": "unsupported because the reviewed official source does not document it",
            "unknown_operator": "unknown operator is invalid; never silently dropped",
            "free_text": "valid but interpretation may be approximate because bare text can overlap species names, nicknames, types, regions, and other terms",
            "verified_exact": "requires every token to match the reviewed registry and every repository semantic fixture to pass at runtime",
        },
        "local_templates": {
            "storage_key": "pokemon-go-collection:search-templates:v1",
            "schema_version": 1,
            "unified_backup": True,
        },
        "consumers": ["action-packs", "storage-cleanup", "collection-search-handoff"],
    }


def build_cleanup_contract(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": CLEANUP_VERSION,
        "lab_version": LAB_VERSION,
        "build_id": manifest["build_id"],
        "title": "Safety-first Storage Cleanup Lab",
        "inputs": {
            "owned": "data/pokemon.json",
            "decisions": "data/decisions/records.json",
            "local_enrichment": "pokemon-go-collection:enrichment:v1",
            "local_annotations": "pokemon-go-collection:annotations:v2",
            "search_registry": "data/search-operator-registry.json",
        },
        "tiers": [
            {"id": "conservative", "meaning": "No supported protection and no unresolved collector-state uncertainty."},
            {"id": "balanced", "meaning": "No hard protection, but stale/incomplete evidence or other review uncertainty remains."},
            {"id": "aggressive", "meaning": "No hard protection, but unsupported or unknown collector-state facts require manual in-game confirmation."},
            {"id": "protected", "meaning": "At least one supported protection/blocker is present; do not present as a cleanup candidate."},
        ],
        "protections": [
            "hundo", "nundo", "user IV threshold", "strong PvP candidate", "Shadow", "Purified", "Lucky", "Favorite",
            "second Charged Move", "unusual form", "known shiny", "known costume", "known background", "known Dynamax/Gigantamax",
            "trade reservation", "legacy/special-move review", "manual Keep/Trade/Build labels", "single-copy keeper within a duplicate group",
            "decision-card protect/block state",
        ],
        "uncertainty": [
            "unknown shiny/costume/background/Max/trade-reservation/legacy-move state", "incomplete scan", "stale scan",
            "exact record identity is not representable in Pokémon GO inventory search", "arbitrary IV percentage thresholds are not exactly representable",
        ],
        "safety": {
            "automatic_transfer": False,
            "automatic_transfer_safe_state": False,
            "missing_data_is_expendability": False,
            "manual_approval_required": True,
            "search_handoff_is_locator_only_unless_every_requested_condition_is_exact": True,
        },
        "local_review_state": {
            "storage_key": "pokemon-go-collection:storage-cleanup:v1",
            "schema_version": 1,
            "unified_backup": True,
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
        "storage-search-labs-index.schema.json": _schema(
            "storage-search-labs-index", ["schema_version", "build_id", "labs"],
            {"schema_version": string, "build_id": build, "labs": {"type": "object"}},
        ),
        "search-builder-contract.schema.json": _schema(
            "search-builder-contract", ["schema_version", "build_id", "registry", "source", "semantics", "local_templates"],
            {"schema_version": string, "build_id": build, "registry": string, "source": {"type": "object"}, "semantics": {"type": "object"}, "local_templates": {"type": "object"}},
        ),
        "storage-cleanup-contract.schema.json": _schema(
            "storage-cleanup-contract", ["schema_version", "build_id", "inputs", "tiers", "protections", "safety"],
            {"schema_version": string, "build_id": build, "inputs": {"type": "object"}, "tiers": {"type": "array"}, "protections": {"type": "array"}, "safety": {"type": "object"}},
        ),
        "search-operator-registry.schema.json": _schema(
            "search-operator-registry", ["schema_version", "reviewed_at", "authority", "source", "boolean", "operators", "semantic_fixtures"],
            {"schema_version": string, "reviewed_at": string, "authority": {"const": "Official"}, "source": {"type": "object"}, "boolean": {"type": "object"}, "operators": {"type": "array", "minItems": 20}, "semantic_fixtures": {"type": "array", "minItems": 8}},
        ),
    }


def _register_contracts() -> None:
    manifest_registry._SCHEMA_MAP.update({
        "data/storage-search-labs/index.json": "data/storage-search-labs-index.schema.json",
        "data/search-builder-contract.json": "data/search-builder-contract.schema.json",
        "data/storage-cleanup-contract.json": "data/storage-cleanup-contract.schema.json",
        "data/search-operator-registry.json": "data/search-operator-registry.schema.json",
    })
    manifest_registry._STABLE_NAMES.update({
        "data/storage-search-labs/index.json": "storage_search_labs_index",
        "data/search-builder-contract.json": "search_builder_contract",
        "data/storage-cleanup-contract.json": "storage_cleanup_contract",
        "data/search-operator-registry.json": "search_operator_registry",
        "data/storage-search-labs-index.schema.json": "storage_search_labs_index_schema",
        "data/search-builder-contract.schema.json": "search_builder_contract_schema",
        "data/storage-cleanup-contract.schema.json": "storage_cleanup_contract_schema",
        "data/search-operator-registry.schema.json": "search_operator_registry_schema",
    })


def _page(output_dir: Path, filename: str, title: str, mount_id: str, description: str, controls: str) -> None:
    html = f'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title><link rel="stylesheet" href="assets/storage-search-labs.css" data-storage-search-style></head>
<body><main class="ssl-page"><header class="ssl-header"><p><a href="tools.html">Tools</a> · <a href="index.html">Collection</a> · <a href="storage-cleanup.html">Storage Cleanup</a> · <a href="search-builder.html">Search Builder</a> · <a href="action-packs.html">Action Packs</a></p><h1>{title}</h1><p>{description}</p></header>{controls}<div id="{mount_id}" aria-live="polite"></div></main><script defer src="assets/storage-search-labs.js" data-storage-search-script></script></body></html>'''
    (output_dir / filename).write_text(html, encoding="utf-8", newline="\n")


def _install_tools_links(output_dir: Path) -> None:
    path = output_dir / "tools.html"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    if 'id="storage-search-labs"' not in source:
        block = '''\n    <section id="storage-search-labs" class="planner-card" aria-labelledby="storage-search-labs-heading">
      <header><div><p class="eyebrow">#149/#150</p><h2 id="storage-search-labs-heading">Storage Cleanup and Pokémon GO Search Builder</h2></div></header>
      <p>Find review candidates without converting uncertainty into transfer safety, and build current official Pokémon GO inventory searches from one reviewed operator registry.</p>
      <p><a href="storage-cleanup.html">Open Storage Cleanup Lab</a> · <a href="search-builder.html">Open Search Builder</a></p>
    </section>\n'''
        marker = "  </main>"
        if marker not in source:
            raise ValueError("Generated tools page is missing its main closing tag")
        source = source.replace(marker, block + marker, 1)
    if 'data-storage-search-backup' not in source:
        storage_script = '  <script defer src="assets/storage-search-backup.js" data-storage-search-backup></script>\n'
        trade_script = '  <script defer src="assets/trade-resource-labs.js" data-trade-resource-tools></script>\n'
        if trade_script in source:
            source = source.replace(trade_script, storage_script + trade_script, 1)
        elif "</body>" in source:
            source = source.replace("</body>", storage_script + "</body>", 1)
        else:
            raise ValueError("Generated tools page is missing its body closing tag")
    path.write_text(source, encoding="utf-8", newline="\n")


def publish(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    _register_contracts()
    registry = _load_registry(repository_root)
    search = build_search_contract(manifest, registry)
    cleanup = build_cleanup_contract(manifest)
    _write(output_dir / "data" / "search-operator-registry.json", registry)
    _write(output_dir / "data" / "search-builder-contract.json", search)
    _write(output_dir / "data" / "storage-cleanup-contract.json", cleanup)
    index = {
        "schema_version": LAB_VERSION,
        "build_id": manifest["build_id"],
        "labs": {
            "storage_cleanup": {"issue": 149, "page": "storage-cleanup.html", "contract": "data/storage-cleanup-contract.json"},
            "search_builder": {"issue": 150, "page": "search-builder.html", "contract": "data/search-builder-contract.json", "registry": "data/search-operator-registry.json"},
        },
    }
    _write(output_dir / "data" / "storage-search-labs" / "index.json", index)
    for filename, schema in schemas().items():
        Draft202012Validator.check_schema(schema)
        _write(output_dir / "data" / filename, schema)

    cleanup_controls = '''<section class="ssl-card" aria-labelledby="cleanup-controls-heading"><h2 id="cleanup-controls-heading">Cleanup target</h2><div class="ssl-grid"><label>Slots needed <input id="cleanup-slots" type="number" min="1" max="1000" value="50" inputmode="numeric"></label><label>Protect IV at or above <input id="cleanup-iv-threshold" type="number" min="0" max="100" step="0.1" value="90" inputmode="decimal"></label><label>Review aggressiveness <select id="cleanup-aggressiveness"><option value="conservative">Conservative only</option><option value="balanced">Through balanced</option><option value="aggressive">Include aggressive manual review</option></select></label></div><div class="ssl-actions"><button id="cleanup-run" type="button">Build review queue</button><button id="cleanup-copy-batches" type="button" disabled>Copy approved search batches</button></div><p class="ssl-note">Nothing on this page is an automatic transfer recommendation. Approving means only “include in my in-game verification queue.”</p><p id="cleanup-status" role="status"></p></section>'''
    search_controls = '''<section class="ssl-card" aria-labelledby="search-controls-heading"><h2 id="search-controls-heading">Build or inspect a search</h2><div class="ssl-grid"><label>Official operator <select id="search-operator"></select></label><label>Value <input id="search-value" type="text" autocomplete="off" placeholder="e.g. 300, Pikachu, dragon"></label><label><input id="search-negated" type="checkbox"> Exclude with !</label><label>Join next term with <select id="search-join"><option value="&">AND (&amp;)</option><option value="|">OR (|)</option></select></label></div><div class="ssl-actions"><button id="search-add-term" type="button">Add term</button><button id="search-copy" type="button">Copy search</button></div><label>Raw Pokémon GO search <textarea id="search-raw" rows="4" spellcheck="false"></textarea></label><div class="ssl-actions"><input id="search-template-name" type="text" placeholder="Template name" aria-label="Template name"><button id="search-save-template" type="button">Save local template</button></div><div id="search-template-list"></div><p id="search-status" role="status"></p></section>'''
    _page(output_dir, "storage-cleanup.html", "Safety-first Storage Cleanup Lab", "storage-cleanup-root", "Choose how much space you need. The lab ranks duplicate review candidates in explicit risk tiers, keeps every supported protection visible, and requires manual Pokémon GO verification before any transfer.", cleanup_controls)
    _page(output_dir, "search-builder.html", "Current Pokémon GO Search Builder", "search-builder-root", "Build and inspect inventory searches from the reviewed official operator contract. Unsupported syntax is reported rather than silently simplified.", search_controls)
    _install_tools_links(output_dir)

    llms = output_dir / "llms.txt"
    if llms.is_file():
        with llms.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "\nStorage cleanup and Pokémon GO search:\n"
                "- /storage-cleanup.html ranks duplicate review candidates only; it never emits an automatic transfer-safe state. Unknown collector attributes reduce confidence.\n"
                "- /search-builder.html and /data/search-operator-registry.json define the single reviewed current official Pokémon GO inventory-search contract used by cleanup handoffs.\n"
                "- Verified exact status is gated on repository semantic fixtures; a failing or missing fixture set fails closed.\n"
                "- Parenthesized Boolean grouping is intentionally unsupported because the reviewed official inventory-search source documents flat operators but not parentheses.\n"
                "- Saved search templates and local cleanup review decisions participate in unified browser-local backup/restore.\n"
            )
    return index


__all__ = ["LAB_VERSION", "CLEANUP_VERSION", "SEARCH_VERSION", "build_search_contract", "build_cleanup_contract", "schemas", "publish"]
