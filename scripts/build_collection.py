#!/usr/bin/env python3
"""Build the collection using the constrained archive and hardened site assets."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Callable

try:
    from . import build_site as legacy
except ImportError:  # Direct execution: python scripts/build_collection.py
    import build_site as legacy


EXTRA_HEAD_ASSETS = (
    '  <link rel="stylesheet" href="assets/stability.css">\n'
    '  <script defer src="assets/hardening.js"></script>\n'
)


def discover_exports(repository_root: Path) -> list[legacy.ExportFile]:
    """Return valid timestamped exports located strictly under exports/."""
    archive_root = repository_root / "exports"
    exports: list[legacy.ExportFile] = []
    if not archive_root.is_dir():
        return exports

    for path in archive_root.rglob("*.csv"):
        relative_directories = path.relative_to(archive_root).parts[:-1]
        if any(part.startswith(".") for part in relative_directories):
            continue
        parsed = legacy.parse_export_filename(path)
        if parsed is not None:
            exports.append(parsed)

    return sorted(exports, key=lambda item: (item.timestamp, item.path.as_posix()))


def inject_hardened_assets(output_dir: Path, site_dir: Path) -> None:
    """Copy supplemental assets and reference them from generated HTML."""
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(site_dir / "hardening.js", assets_dir / "hardening.js")
    shutil.copy2(site_dir / "stability.css", assets_dir / "stability.css")

    for filename in ("index.html", "404.html"):
        path = output_dir / filename
        source = path.read_text(encoding="utf-8")
        if 'href="assets/stability.css"' not in source:
            source = source.replace("</head>", EXTRA_HEAD_ASSETS + "</head>")
        path.write_text(source, encoding="utf-8", newline="\n")


def update_generated_manifests(output_dir: Path, manifest: dict[str, Any]) -> None:
    """Keep every published manifest copy consistent with this entry point."""
    manifest["generator"] = "scripts/build_collection.py"

    build_manifest = output_dir / "data" / "build-manifest.json"
    build_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    payload_path = output_dir / "data" / "pokemon.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["manifest"] = manifest
    payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    """Build through the existing normalizer with archive discovery constrained."""
    original_discovery: Callable[[Path], list[legacy.ExportFile]] = legacy.discover_exports
    legacy.discover_exports = discover_exports
    try:
        manifest = legacy.build(repository_root, output_dir)
    finally:
        legacy.discover_exports = original_discovery

    inject_hardened_assets(output_dir, repository_root / "site")
    update_generated_manifests(output_dir, manifest)
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
        f"Built {manifest['pokemon_count']} Pokémon from "
        f"{manifest['source_file']} into {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
