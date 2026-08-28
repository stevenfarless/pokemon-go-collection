#!/usr/bin/env python3
"""Build the complete canonical Pokémon GO collection site."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from . import (
        action_workflows,
        advanced_labs,
        battle_labs,
        cpm_compat,
        current_data_coverage,
        event_calendar,
        event_calendar_integration,
        evidence_contract,
        evidence_integration,
        foundation_build,
        lab_asset_pipeline,
        mechanics_registry,
        opportunity_special_labs,
        platform_publish,
        player_labs,
        player_labs_integration,
        privacy_profiles,
        product_experience,
        storage_search_labs,
        trade_resource_labs,
    )
    from .collection_resource_contracts import publish_collection_resource_schemas
    from .collection_resources import (
        publish_assistant_context,
        publish_derived_views,
        publish_history,
        publish_species_family_resources,
        publish_static_api,
    )
    from .collection_shards import publish_collection_shards
    from .decision_support import publish_decision_support
    from .decision_support_contracts import publish_decision_support_schemas
    from .external_game_data import publish_external_framework
    from .finalize_dashboard import finalize
    from .planning_publish import publish_planning
    from .privacy_contracts import publish_privacy_schema
    from .product_experience_contracts import publish_product_schemas
    from .public_contracts import publish_public_schemas
except ImportError:
    import action_workflows
    import advanced_labs
    import battle_labs
    import cpm_compat
    import current_data_coverage
    import event_calendar
    import event_calendar_integration
    import evidence_contract
    import evidence_integration
    import foundation_build
    import lab_asset_pipeline
    import mechanics_registry
    import opportunity_special_labs
    import platform_publish
    import player_labs
    import player_labs_integration
    import privacy_profiles
    import product_experience
    import storage_search_labs
    import trade_resource_labs
    from collection_resource_contracts import publish_collection_resource_schemas
    from collection_resources import (
        publish_assistant_context,
        publish_derived_views,
        publish_history,
        publish_species_family_resources,
        publish_static_api,
    )
    from collection_shards import publish_collection_shards
    from decision_support import publish_decision_support
    from decision_support_contracts import publish_decision_support_schemas
    from external_game_data import publish_external_framework
    from finalize_dashboard import finalize
    from planning_publish import publish_planning
    from privacy_contracts import publish_privacy_schema
    from product_experience_contracts import publish_product_schemas
    from public_contracts import publish_public_schemas


def _write_llm_bootstrap(output_dir: Path, manifest: dict[str, Any], shard_index: dict[str, Any]) -> None:
    bootstrap = {
        "schema_version": "1.0.0",
        "build_id": manifest["build_id"],
        "source_file": manifest["source_file"],
        "export_timestamp": manifest["export_timestamp"],
        "normalized_record_count": manifest["normalized_record_count"],
        "retrieval": {
            "start_here": "data/llm-bootstrap.json",
            "freshness": "data/build-manifest.json",
            "summary": "data/collection-summary.json",
            "discovery": "data/pokemon-index.json",
            "canonical_dataset": "data/pokemon.json",
            "original_export": "data/latest-export.csv",
            "recommended_strategy": (
                "Read data/assistant-context.md plus the manifest first. Prefer species/family "
                "resources for owned-record questions, recommendations/candidates/investments/"
                "reasoning/decisions for decision-support questions, data/player-labs/index.json "
                "for naming, collection-gap, roster-readiness, evolution, or move-planning "
                "workflows, data/advanced-labs/index.json for Mega, Max, Hyper Training, buddy, "
                "or raid-readiness workflows, data/battle-labs/index.json for PvP or Team GO "
                "Rocket battle planning, data/opportunity-special-labs/index.json for current "
                "acquisition paths or Fusion/Adventure Effect planning, data/trade-resource-labs/"
                "index.json for private guest trade matching or scarce-resource planning, "
                "data/storage-search-labs/index.json for storage cleanup review or Pokémon GO "
                "search construction, data/event-calendar.json for freshness-gated event/deadline "
                "planning, and data/evidence-index.json for trust, freshness, confidence, "
                "prerequisite, and uncertainty semantics. Treat data/mechanics/index.json coverage "
                "and data/external/index.json freshness/category coverage as mandatory prerequisites "
                "for current-game claims."
            ),
        },
        "shards": {
            "count": shard_index["shard_count"],
            "hard_max_bytes": shard_index["strategy"]["hard_max_bytes"],
            "index": "data/pokemon-index.json",
        },
    }
    path = output_dir / "data" / "llm-bootstrap.json"
    path.write_text(
        json.dumps(bootstrap, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    """Run the single production build and finalize canonical dashboard resources."""
    manifest = foundation_build.build(repository_root, output_dir)
    privacy_profile = privacy_profiles.prepare_privacy(output_dir)
    manifest = finalize(repository_root, output_dir, manifest)

    shard_index = publish_collection_shards(output_dir, manifest)
    publish_species_family_resources(output_dir, manifest)
    publish_derived_views(output_dir, manifest)
    publish_history(repository_root, output_dir, manifest)

    publish_decision_support(output_dir, manifest)
    current_data_coverage.install()
    publish_external_framework(repository_root, output_dir, manifest)
    current_data_coverage.publish_metadata(output_dir)
    mechanics_registry.publish(repository_root, output_dir, manifest)
    publish_planning(repository_root, output_dir, manifest)
    product_experience.publish(repository_root, output_dir, manifest)
    action_workflows.publish(output_dir, manifest)
    cpm_compat.install(player_labs)
    player_labs.publish(repository_root, output_dir, manifest)
    player_labs_integration.integrate(output_dir)
    advanced_labs.publish(repository_root, output_dir, manifest)
    battle_labs.publish(repository_root, output_dir, manifest)
    opportunity_special_labs.publish(repository_root, output_dir, manifest)
    trade_resource_labs.publish(repository_root, output_dir, manifest)
    storage_search_labs.publish(repository_root, output_dir, manifest)
    event_calendar.publish(repository_root, output_dir, manifest)
    event_calendar_integration.integrate(output_dir)
    lab_asset_pipeline.prepare(repository_root, output_dir, manifest)
    evidence_contract.publish(output_dir)

    publish_public_schemas(output_dir)
    publish_collection_resource_schemas(output_dir)
    publish_decision_support_schemas(output_dir)
    publish_product_schemas(output_dir)
    current_data_coverage.patch_external_schema(output_dir)
    publish_privacy_schema(output_dir)
    _write_llm_bootstrap(output_dir, manifest, shard_index)
    publish_assistant_context(output_dir, manifest)

    manifest = platform_publish.publish_platform(repository_root, output_dir, manifest)
    evidence_integration.publish(repository_root, output_dir, manifest)
    event_calendar_integration.finalize_service_worker(output_dir)
    privacy_profiles.finalize_privacy(output_dir, privacy_profile)
    manifest = foundation_build.finalize_foundation(output_dir, manifest)
    publish_static_api(output_dir, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "dist").resolve()
    manifest = build(root, output)
    print(
        f"Built {manifest['normalized_record_count']} canonical Pokémon from "
        f"{manifest['source_record_count']} source rows with selective resources, "
        f"deterministic decision support, local planning tools, Today, global search, "
        f"species reference, exact decisions, Action Packs, change timeline, scan preflight, "
        f"Naming Studio, Gap Radar, Roster Readiness, Evolution Lab, Move Lab, "
        f"Mega/Primal Lab, Max Battle Lab, Hyper Training, Buddy Queue, Raid Readiness, "
        f"PvP Battle Lab, Rocket Planner, Opportunity Finder, Special Mechanics Lab, "
        f"private Trade Matcher, Trainer Resource Vault, Storage Cleanup Lab, Search Builder, "
        f"Event Calendar, shared evidence contract, browser diagnostics, mechanics coverage, "
        f"privacy audit, and external-data freshness contracts into {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
