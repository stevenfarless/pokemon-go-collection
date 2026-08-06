#!/usr/bin/env python3
"""Build the dashboard and add compact clickable summary shortcuts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

try:
    from . import build_release
except ImportError:  # Direct execution
    import build_release

SUMMARY_STYLE = """
.summary-preset{display:inline-flex;align-items:baseline;gap:.25rem;min-height:0;padding:.16rem .28rem;border:0;border-radius:.38rem;background:transparent;color:var(--muted);font-size:.8rem;white-space:nowrap}
.summary-preset strong{color:var(--text);font-size:.95rem}
.summary-preset:hover{background:var(--surface);color:var(--text)}
.summary-preset:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
""".strip()

SUMMARY_MARKUP = """<section class="compact-stats" aria-label="Collection summary shortcuts">
      <button type="button" class="summary-preset" data-summary-preset="all" title="Show the entire collection"><strong id="total-count">{{POKEMON_COUNT}}</strong><span>total</span></button>
      <button type="button" class="summary-preset" data-summary-preset="species" title="Group all Pokémon by species and form"><strong id="species-count">…</strong><span>species/forms</span></button>
      <button type="button" class="summary-preset" data-summary-preset="hundos" title="Show only hundos"><strong id="hundo-count">…</strong><span>hundos</span></button>
      <button type="button" class="summary-preset" data-summary-preset="shadows" title="Show only Shadow Pokémon"><strong id="shadow-count">…</strong><span>shadows</span></button>
      <button type="button" class="summary-preset" data-summary-preset="lucky" title="Show only Lucky Pokémon"><strong id="lucky-count">…</strong><span>lucky</span></button>
      <button type="button" class="summary-preset" data-summary-preset="max-cp" title="Show Pokémon at the collection's maximum CP"><strong id="highest-cp">…</strong><span>max CP</span></button>
    </section>
    <p id="summary-shortcut-status" class="visually-hidden" aria-live="polite"></p>"""

SUMMARY_PATTERN = re.compile(
    r'<section class="compact-stats" aria-label="Collection summary">.*?</section>',
    re.DOTALL,
)


def _hash_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def _write_json(path: Path, payload: Any, *, compact: bool = False) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
        ) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _replace_html(
    output_dir: Path,
    old_asset: str,
    new_asset: str,
    pokemon_count: int,
) -> None:
    markup = SUMMARY_MARKUP.replace("{{POKEMON_COUNT}}", f"{pokemon_count:,}")
    for filename in ("index.html", "404.html"):
        path = output_dir / filename
        source = path.read_text(encoding="utf-8")
        source, count = SUMMARY_PATTERN.subn(markup, source, count=1)
        if count != 1:
            raise ValueError(f"Generated {filename} is missing the collection summary section")
        if old_asset not in source:
            raise ValueError(f"Generated {filename} does not reference {old_asset}")
        source = source.replace(old_asset, new_asset)
        source = source.replace("</head>", f"  <style data-summary-presets>{SUMMARY_STYLE}</style>\n</head>", 1)
        path.write_text(source, encoding="utf-8", newline="\n")


def add_summary_shortcuts(
    repository_root: Path,
    output_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    old_asset = manifest["assets"]["accessibility"]
    old_path = output_dir / old_asset
    source = old_path.read_text(encoding="utf-8")
    shortcuts = (repository_root / "site" / "summary-presets.js").read_text(encoding="utf-8")
    combined = f"{source.rstrip()}\n\n{shortcuts.rstrip()}\n"
    new_asset = f"assets/accessibility.{_hash_text(combined)}.js"
    (output_dir / new_asset).write_text(combined, encoding="utf-8", newline="\n")
    if new_asset != old_asset:
        old_path.unlink()

    _replace_html(output_dir, old_asset, new_asset, manifest["pokemon_count"])
    manifest["assets"]["accessibility"] = new_asset

    manifest_path = output_dir / "data" / "build-manifest.json"
    payload_path = output_dir / "data" / "pokemon.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["manifest"] = manifest
    _write_json(payload_path, payload, compact=True)
    _write_json(manifest_path, manifest)
    return manifest


def build(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    manifest = build_release.build(repository_root, output_dir)
    return add_summary_shortcuts(repository_root, output_dir, manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "dist").resolve()
    manifest = build(root, output)
    print(f"Built {manifest['pokemon_count']} Pokémon with clickable summary shortcuts into {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
