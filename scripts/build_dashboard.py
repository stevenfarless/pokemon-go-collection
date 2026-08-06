#!/usr/bin/env python3
"""Build the complete canonical Pokémon GO collection site."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

try:
    from . import build_release
    from .finalize_dashboard import finalize
except ImportError:
    import build_release
    from finalize_dashboard import finalize


def build(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    """Run the single production build and finalize canonical dashboard resources."""
    manifest = build_release.build(repository_root, output_dir)
    return finalize(repository_root, output_dir, manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "dist").resolve()
    manifest = build(root, output)
    print(
        f"Built {manifest['pokemon_count']} Pokémon with the canonical dashboard, "
        f"Data Health, and Insights into {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
