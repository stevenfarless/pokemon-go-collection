#!/usr/bin/env python3
"""Build the complete canonical Pokémon GO collection site."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from . import foundation_build
    from .collection_shards import publish_collection_shards
    from .finalize_dashboard import finalize
    from .public_contracts import publish_public_schemas
except ImportError:
    import foundation_build
    from collection_shards import publish_collection_shards
    from finalize_dashboard import finalize
    from public_contracts import publish_public_schemas


def _write_llm_bootstrap(output_dir: Path, manifest: dict[str, Any], shard_index: dict[str, Any]) -> None:
    """Publish a tiny, stable entry point that tells machine clients how to retrieve this build."""
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
            "recommended_strategy": "Read pokemon-index.json, then fetch only listed shards needed for the question. Use pokemon.json only when a client can reliably retrieve the complete canonical payload.",
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
    publish_public_schemas(output_dir)
    shard_index = publish_collection_shards(output_dir, manifest)
    _write_llm_bootstrap(output_dir, manifest, shard_index)

    llms_path = output_dir / "llms.txt"
    llms = llms_path.read_text(encoding="utf-8")
    llms += (
        "\nMachine/LLM retrieval contract:\n"
        "- Start with /data/llm-bootstrap.json. It is the small, stable machine entry point for the current build.\n"
        "- Verify /data/build-manifest.json before making ownership or investment conclusions.\n"
        "- Prefer /data/pokemon-index.json plus its bounded shards over downloading /data/pokemon.json in one request.\n"
        "- /data/pokemon-index.json is the compact discovery document for bounded collection shards.\n"
        "- Follow only shard paths listed by that index; every shard belongs to the same build and stays under the declared hard byte limit.\n"
        "- Concatenating shard records in index order reconstructs the canonical /data/pokemon.json record sequence exactly.\n"
        "- If a client cannot retrieve pokemon.json because of response-size, parsing, caching, or transport limits, this is not evidence that the collection is unavailable; fall back to the shard index.\n"
        "- Do not substitute an older export when the bootstrap, manifest, index, and shards agree on the current build_id.\n"
        f"- Current build shard count: {shard_index['shard_count']}; hard maximum per shard: {shard_index['strategy']['hard_max_bytes']} bytes.\n"
    )
    llms_path.write_text(llms, encoding="utf-8", newline="\n")
    return foundation_build.finalize_foundation(output_dir, manifest)


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
        f"{manifest['source_record_count']} source rows with the canonical dashboard, "
        f"Data Health, Insights, and bounded retrieval shards into {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
