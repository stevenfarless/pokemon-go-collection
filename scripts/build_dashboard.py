#!/usr/bin/env python3
"""Build the complete canonical Pokémon GO collection site."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

try:
    from . import foundation_build
    from .finalize_dashboard import finalize
    from .public_contracts import publish_public_schemas
except ImportError:
    import foundation_build
    from finalize_dashboard import finalize
    from public_contracts import publish_public_schemas


def build(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    """Run the single production build and finalize canonical dashboard resources."""
    manifest = foundation_build.build(repository_root, output_dir)
    manifest = finalize(repository_root, output_dir, manifest)
    publish_public_schemas(output_dir)
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
        f"Data Health, and Insights into {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
