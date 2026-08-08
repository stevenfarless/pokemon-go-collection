#!/usr/bin/env python3
"""Build the complete canonical Pokémon GO collection site."""

from __future__ import annotations

import argparse
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


def build(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    """Run the single production build and finalize canonical dashboard resources."""
    manifest = foundation_build.build(repository_root, output_dir)
    manifest = finalize(repository_root, output_dir, manifest)
    publish_public_schemas(output_dir)
    shard_index = publish_collection_shards(output_dir, manifest)

    llms_path = output_dir / "llms.txt"
    llms = llms_path.read_text(encoding="utf-8")
    llms += (
        "\nSelective collection retrieval:\n"
        "- /data/pokemon-index.json is the compact discovery document for bounded collection shards.\n"
        "- Follow only the shard paths listed by that index; every shard belongs to the same build and stays under the declared hard byte limit.\n"
        "- Concatenating shard records in index order reconstructs the canonical /data/pokemon.json record sequence exactly.\n"
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
