#!/usr/bin/env python3
"""Build the complete canonical Pokémon GO collection site."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from . import foundation_build
    from .collection_resource_contracts import publish_collection_resource_schemas
    from .collection_resources import (
        publish_assistant_context,
        publish_derived_views,
        publish_history,
        publish_species_family_resources,
        publish_static_api,
    )
    from .collection_shards import publish_collection_shards
    from .finalize_dashboard import finalize
    from .public_contracts import publish_public_schemas
except ImportError:
    import foundation_build
    from collection_resource_contracts import publish_collection_resource_schemas
    from collection_resources import (
        publish_assistant_context,
        publish_derived_views,
        publish_history,
        publish_species_family_resources,
        publish_static_api,
    )
    from collection_shards import publish_collection_shards
    from finalize_dashboard import finalize
    from public_contracts import publish_public_schemas


def _write_llm_bootstrap(output_dir: Path, manifest: dict[str, Any], shard_index: dict[str, Any]) -> None:
    """Publish a tiny, stable entry point that tells machine clients how to retrieve this build."""
    bootstrap = {
        "schema_version": "1.1.0",
        "build_id": manifest["build_id"],
        "source_file": manifest["source_file"],
        "export_timestamp": manifest["export_timestamp"],
        "normalized_record_count": manifest["normalized_record_count"],
        "retrieval": {
            "start_here": "data/llm-bootstrap.json",
            "freshness": "data/build-manifest.json",
            "assistant_context": "data/assistant-context.md",
            "summary": "data/collection-summary.json",
            "species_index": "data/species-index.json",
            "family_index": "data/family-index.json",
            "views_index": "data/views-index.json",
            "shard_index": "data/pokemon-index.json",
            "canonical_dataset": "data/pokemon.json",
            "original_export": "data/latest-export.csv",
            "recommended_strategy": "Verify the manifest, prefer species/family/view resources for narrow questions, then use bounded shards for genuine collection-wide scans. Fetch pokemon.json only when complete retrieval is practical.",
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
    manifest = finalize(repository_root, output_dir, manifest)

    # Shared upstream resources for #57 and #62 are published before machine retrieval
    # documentation (#59). History (#63) is generated before the final registry so all
    # retained snapshots are integrity-checked. The versioned API (#65) is copied only
    # after the authoritative manifest is final, avoiding a stale manifest alias.
    publish_species_family_resources(output_dir, manifest)
    publish_derived_views(output_dir, manifest)
    shard_index = publish_collection_shards(output_dir, manifest)
    publish_history(repository_root, output_dir, manifest)
    publish_public_schemas(output_dir)
    publish_collection_resource_schemas(output_dir)
    _write_llm_bootstrap(output_dir, manifest, shard_index)
    publish_assistant_context(output_dir, manifest)

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
        f"{manifest['source_record_count']} source rows with selective species/family resources, "
        f"derived views, bounded history, and the static v1 API into {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
