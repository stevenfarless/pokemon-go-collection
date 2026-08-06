#!/usr/bin/env python3
"""Build the dashboard with summary shortcuts and a public trainer profile."""

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

SITE_TITLE = "Fuddledumpy’s Pokémon GO Collection"
FRIEND_CODE_DISPLAY = "2252 2231 2780"
FRIEND_CODE_DIGITS = "225222312780"
META_DESCRIPTION = (
    "Browse Fuddledumpy’s searchable Pokémon GO collection and add "
    "Friend Code 2252 2231 2780."
)

SUMMARY_STYLE = """
.summary-preset{display:inline-flex;align-items:baseline;gap:.25rem;min-height:0;padding:.16rem .28rem;border:0;border-radius:.38rem;background:transparent;color:var(--muted);font-size:.8rem;white-space:nowrap}
.summary-preset strong{color:var(--text);font-size:.95rem}
.summary-preset:hover{background:var(--surface);color:var(--text)}
.summary-preset:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
""".strip()

TRAINER_STYLE = """
.brand{min-width:0;flex:1}
.brand h1{overflow-wrap:anywhere}
.trainer-contact{display:flex;align-items:center;flex-wrap:wrap;gap:.25rem .45rem;margin-top:.22rem;color:var(--muted);font-size:.82rem}
.friend-code-value{color:var(--text);font-variant-numeric:tabular-nums;letter-spacing:.045em;font-weight:750;white-space:nowrap}
.copy-friend-code{min-height:1.75rem;padding:.16rem .48rem;border-radius:999px;background:transparent;color:var(--accent);font-size:.72rem;font-weight:750}
.copy-friend-code:hover{background:var(--surface)}
.copy-friend-code[data-copied="true"]{background:var(--accent);color:var(--accent-text)}
.friend-code-status{min-width:3rem;color:var(--accent);font-size:.72rem}
.data-menu{flex:0 0 auto}
@media(max-width:650px){.site-header{align-items:flex-start}.brand h1{max-width:20ch;font-size:clamp(1.1rem,6vw,1.4rem)}.trainer-contact{gap:.22rem .38rem}.friend-code-status{flex-basis:100%;min-height:0}}
""".strip()

TRAINER_SCRIPT = r"""
(() => {
  const button = document.getElementById("copy-friend-code");
  const status = document.getElementById("friend-code-status");
  if (!button || !status) return;

  async function copyText(text) {
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return;
      } catch {
        // Fall through to the selection-based copy method.
      }
    }

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    textarea.style.pointerEvents = "none";
    document.body.append(textarea);
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);
    const copied = document.execCommand("copy");
    textarea.remove();
    if (!copied) throw new Error("Copy command failed");
  }

  button.addEventListener("click", async () => {
    const code = button.dataset.friendCode || "";
    try {
      await copyText(code);
      status.textContent = "Copied";
      button.dataset.copied = "true";
      window.clearTimeout(button.friendCodeStatusTimer);
      button.friendCodeStatusTimer = window.setTimeout(() => {
        status.textContent = "";
        delete button.dataset.copied;
      }, 2500);
    } catch {
      status.textContent = "Copy failed";
      delete button.dataset.copied;
    }
  });
})();
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

TRAINER_MARKUP = f"""<div class="brand">
      <h1>{SITE_TITLE}</h1>
      <div class="trainer-contact" aria-label="Trainer Friend Code">
        <span>Friend Code:</span>
        <span class="friend-code-value">{FRIEND_CODE_DISPLAY}</span>
        <button
          id="copy-friend-code"
          class="copy-friend-code"
          type="button"
          data-friend-code="{FRIEND_CODE_DIGITS}"
          aria-label="Copy Friend Code {FRIEND_CODE_DISPLAY}"
          aria-describedby="friend-code-status"
        >Copy</button>
        <span id="friend-code-status" class="friend-code-status" role="status" aria-live="polite"></span>
      </div>
      <p>{{{{COLLECTION_SOURCE}}}}</p>
    </div>"""

SOCIAL_META = f"""  <meta property="og:title" content="{SITE_TITLE}">
  <meta property="og:description" content="{META_DESCRIPTION}">
  <meta property="og:type" content="website">"""

SUMMARY_PATTERN = re.compile(
    r'<section class="compact-stats" aria-label="Collection summary">.*?</section>',
    re.DOTALL,
)
TITLE_PATTERN = re.compile(r"<title>.*?</title>", re.DOTALL)
DESCRIPTION_PATTERN = re.compile(r'<meta name="description" content="[^"]*">')
BRAND_PATTERN = re.compile(
    r'<div class="brand">\s*<h1>Pokémon GO Collection</h1>\s*<p>(.*?)</p>\s*</div>',
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


def _personalize_html(source: str, filename: str) -> str:
    source, title_count = TITLE_PATTERN.subn(f"<title>{SITE_TITLE}</title>", source, count=1)
    if title_count != 1:
        raise ValueError(f"Generated {filename} is missing the document title")

    description = f'<meta name="description" content="{META_DESCRIPTION}">'
    source, description_count = DESCRIPTION_PATTERN.subn(
        f"{description}\n{SOCIAL_META}",
        source,
        count=1,
    )
    if description_count != 1:
        raise ValueError(f"Generated {filename} is missing the meta description")

    def replace_brand(match: re.Match[str]) -> str:
        collection_source = match.group(1).strip()
        return TRAINER_MARKUP.replace("{{COLLECTION_SOURCE}}", collection_source)

    source, brand_count = BRAND_PATTERN.subn(replace_brand, source, count=1)
    if brand_count != 1:
        raise ValueError(f"Generated {filename} is missing the standard brand header")

    return source


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
        source = _personalize_html(source, filename)
        source = source.replace(
            "</head>",
            (
                f"  <style data-summary-presets>{SUMMARY_STYLE}</style>\n"
                f"  <style data-trainer-profile>{TRAINER_STYLE}</style>\n"
                "</head>"
            ),
            1,
        )
        source = source.replace(
            "</body>",
            f"  <script data-trainer-profile>\n{TRAINER_SCRIPT}\n  </script>\n</body>",
            1,
        )
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
    print(
        f"Built {manifest['pokemon_count']} Pokémon with clickable summary shortcuts "
        f"and the {SITE_TITLE} trainer profile into {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
