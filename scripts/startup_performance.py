"""Collection-page startup optimizations applied to generated assets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

COLLECTION_VIEW_SCHEMA_VERSION = "1.0.0"
PVP_FIELDS = (
    "rank_percent",
    "rank_number",
    "stat_product",
    "dust_cost",
    "candy_cost",
    "evolution_name",
    "evolution_form",
    "status",
)
PLATFORM_INLINE_STYLE_KEYS = (
    "design_system_styles",
    "platform_styles",
    "product_experience_styles",
)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def _pick(value: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {key: source.get(key) for key in keys}


def _compact_pvp(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        league: _pick(source.get(league), PVP_FIELDS)
        for league in ("great", "ultra", "little")
    }


def compact_record(record: dict[str, Any]) -> dict[str, Any]:
    """Keep exactly the fields consumed by Collection filtering, sorting, and row/card rendering."""
    return {
        "pokemon_number": record.get("pokemon_number"),
        "name": record.get("name"),
        "form": record.get("form"),
        "gender": record.get("gender"),
        "cp": record.get("cp"),
        "hp": record.get("hp"),
        "ivs": _pick(
            record.get("ivs"),
            ("average_percent", "total", "attack", "defense", "stamina", "is_hundo", "is_nundo"),
        ),
        "level": _pick(record.get("level"), ("minimum", "maximum")),
        "moves": _pick(record.get("moves"), ("fast", "charged", "charged_second")),
        "status": _pick(record.get("status"), ("shadow_purified", "lucky", "favorite", "marked_for_pvp")),
        "pvp": _compact_pvp(record.get("pvp")),
        "dates": _pick(record.get("dates"), ("catch", "scan", "original_scan")),
        "size": _pick(record.get("size"), ("weight", "height")),
        "dust": record.get("dust"),
    }


def _replace_required(source: str, old: str, new: str, *, description: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"Expected exactly one {description}; found {count}")
    return source.replace(old, new, 1)


def prepare(output_dir: Path, manifest: dict[str, Any]) -> str:
    """Publish a compact Collection startup payload and retarget the generated app to it."""
    canonical_path = output_dir / "data" / "pokemon.json"
    payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("Canonical collection payload is missing records for startup optimization")

    compact_payload = {
        "schema_version": COLLECTION_VIEW_SCHEMA_VERSION,
        "build_id": manifest["build_id"],
        "source_file": manifest["source_file"],
        "record_count": len(records),
        "records": [compact_record(record) for record in records],
    }
    compact_text = json.dumps(compact_payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    compact_name = f"collection-startup.{_content_hash(compact_text)}.json"
    compact_relative = f"data/{compact_name}"
    (output_dir / compact_relative).write_text(compact_text, encoding="utf-8", newline="\n")

    old_app_relative = str(manifest["assets"]["app"])
    old_app_path = output_dir / old_app_relative
    app_source = old_app_path.read_text(encoding="utf-8")
    versioned_fetch = f'fetch("data/pokemon.json?v={manifest["build_id"]}")'
    unversioned_fetch = 'fetch("data/pokemon.json")'
    if versioned_fetch in app_source:
        app_source = _replace_required(
            app_source,
            versioned_fetch,
            f'fetch("{compact_relative}")',
            description="versioned canonical Collection startup fetch",
        )
    elif unversioned_fetch in app_source:
        app_source = _replace_required(
            app_source,
            unversioned_fetch,
            f'fetch("{compact_relative}")',
            description="canonical Collection startup fetch",
        )
    else:
        raise ValueError("Generated Collection app no longer contains the canonical startup fetch")

    app_name = f"app.{_content_hash(app_source)}.js"
    new_app_relative = f"assets/{app_name}"
    new_app_path = output_dir / new_app_relative
    new_app_path.write_text(app_source, encoding="utf-8", newline="\n")
    if new_app_path != old_app_path:
        old_app_path.unlink()

    for filename in ("index.html", "404.html"):
        path = output_dir / filename
        source = path.read_text(encoding="utf-8")
        source = _replace_required(
            source,
            old_app_relative,
            new_app_relative,
            description=f"{filename} Collection app reference",
        )
        path.write_text(source, encoding="utf-8", newline="\n")

    manifest["assets"]["app"] = new_app_relative
    return compact_relative


def finalize(output_dir: Path, manifest: dict[str, Any]) -> None:
    """Remove Collection-page-only render blocking and scripts that have no Collection mount."""
    path = output_dir / "index.html"
    source = path.read_text(encoding="utf-8")

    for key in PLATFORM_INLINE_STYLE_KEYS:
        relative = str(manifest["assets"][key])
        css = (output_dir / relative).read_text(encoding="utf-8").strip()
        link = f'<link rel="stylesheet" href="{relative}" data-platform-style="{key}">'
        replacement = f'<style data-platform-style="{key}" data-startup-inline-css>{css}</style>'
        source = _replace_required(source, link, replacement, description=f"{key} stylesheet link")

    workflow_style = str(manifest["assets"]["action_workflows_styles"])
    workflow_style_link = (
        f'<link rel="stylesheet" href="{workflow_style}" '
        'data-platform-style="action_workflows_styles">'
    )
    source = _replace_required(
        source,
        workflow_style_link,
        "",
        description="Collection action-workflows stylesheet link",
    )

    workflow_script = str(manifest["assets"]["action_workflows"])
    workflow_script_tag = (
        f'<script defer src="{workflow_script}" '
        'data-platform-script="action_workflows"></script>'
    )
    source = _replace_required(
        source,
        workflow_script_tag,
        "",
        description="Collection action-workflows script tag",
    )

    path.write_text(source, encoding="utf-8", newline="\n")


__all__ = [
    "COLLECTION_VIEW_SCHEMA_VERSION",
    "PVP_FIELDS",
    "PLATFORM_INLINE_STYLE_KEYS",
    "compact_record",
    "prepare",
    "finalize",
]
