#!/usr/bin/env python3
"""Build the complete canonical Pokémon GO collection site."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from . import foundation_build, platform_publish, privacy_profiles
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
    from .public_contracts import publish_public_schemas
except ImportError:
    import foundation_build
    import platform_publish
    import privacy_profiles
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
            "recommended_strategy": "Read data/assistant-context.md plus the manifest first. Prefer species/family resources for owned-record questions, recommendations/candidates/investments/reasoning for decision-support questions, and bounded pokemon-index shards only for collection-wide scans. Treat data/external/index.json freshness as mandatory for current-game claims.",
        },
        "shards": {
            "count": shard_index["shard_count"],
            "hard_max_bytes": shard_index["strategy"]["hard_max_bytes"],
            "index": "data/pokemon-index.json",
        },
    }
    path = output_dir / "data" / "llm-bootstrap.json"
    path.write_text(json.dumps(bootstrap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


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
    publish_external_framework(repository_root, output_dir, manifest)
    publish_planning(repository_root, output_dir, manifest)

    publish_public_schemas(output_dir)
    publish_collection_resource_schemas(output_dir)
    publish_decision_support_schemas(output_dir)
    publish_privacy_schema(output_dir)
    _write_llm_bootstrap(output_dir, manifest, shard_index)
    publish_assistant_context(output_dir, manifest)

    manifest = platform_publish.publish_platform(repository_root, output_dir, manifest)
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
        f"deterministic decision support, local planning tools, bounded history, "
        f"browser diagnostics, privacy audit, and external-data freshness contracts into {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
