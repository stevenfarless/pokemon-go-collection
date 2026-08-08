#!/usr/bin/env python3
"""Validate a staged Pages build before promotion or rollback."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .validate_generated import validate_generated
except ImportError:
    from validate_generated import validate_generated


_REQUIRED_PAGES = ("index.html", "404.html", "insights.html", "manifest.webmanifest", "sw.js")
_STATIC_ASSETS = {"assets/app-icon.svg"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def inspect_staged_build(output_dir: Path, *, expected_build_id: str | None = None) -> dict[str, Any]:
    """Return promotion metadata after proving the staged directory is internally complete."""
    output_dir = output_dir.resolve()
    if not output_dir.is_dir():
        raise ValueError(f"Staged build directory does not exist: {output_dir}")

    validate_generated(output_dir)

    for relative in _REQUIRED_PAGES:
        path = output_dir / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Staged build is missing required Pages resource: {relative}")

    manifest_path = output_dir / "data" / "build-manifest.json"
    manifest = _load_json(manifest_path)
    build_id = str(manifest.get("build_id") or "")
    if not build_id:
        raise ValueError("Staged manifest has no build_id")
    if expected_build_id is not None and build_id != expected_build_id:
        raise ValueError(
            f"Rollback build ID mismatch: expected {expected_build_id}, staged artifact contains {build_id}"
        )

    declared_assets = {str(value) for value in manifest.get("assets", {}).values()}
    allowed_assets = declared_assets | _STATIC_ASSETS
    actual_assets = {
        path.relative_to(output_dir).as_posix()
        for path in (output_dir / "assets").iterdir()
        if path.is_file()
    }
    unexpected_assets = sorted(actual_assets - allowed_assets)
    missing_assets = sorted(declared_assets - actual_assets)
    if missing_assets:
        raise ValueError(f"Staged build is missing declared assets: {missing_assets}")
    if unexpected_assets:
        raise ValueError(
            "Staged build contains undeclared/stale assets that could create a mixed deployment: "
            + ", ".join(unexpected_assets)
        )

    for relative in declared_assets:
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"Manifest asset path is unsafe: {relative}")

    count = int(manifest.get("normalized_record_count", manifest.get("pokemon_count", 0)))
    if count <= 0:
        raise ValueError("Staged build has no canonical Pokémon records")

    metadata = {
        "build_id": build_id,
        "source_file": manifest.get("source_file"),
        "source_sha256": manifest.get("source_sha256"),
        "generated_at_utc": manifest.get("generated_at_utc"),
        "pokemon_count": count,
        "resource_count": len(manifest.get("resources", {})),
        "asset_count": len(declared_assets),
    }
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a staged collection before Pages promotion")
    parser.add_argument("--output", type=Path, default=Path("staging"))
    parser.add_argument("--expected-build-id", default=None)
    parser.add_argument("--metadata-output", type=Path, default=None)
    args = parser.parse_args()

    metadata = inspect_staged_build(
        args.output,
        expected_build_id=args.expected_build_id,
    )
    if args.metadata_output is not None:
        args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
        args.metadata_output.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    print(
        "Promotion guard passed: "
        f"build={metadata['build_id']} source={metadata['source_file']} "
        f"records={metadata['pokemon_count']} resources={metadata['resource_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
