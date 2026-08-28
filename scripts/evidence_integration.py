"""Publish and globally inject the shared browser evidence component."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from . import finalize_dashboard
except ImportError:
    import finalize_dashboard

ASSET_KEY = "evidence"
ASSET_SOURCE = "site/evidence.js"
ASSET_PATTERN = r"^assets/evidence\.[0-9a-f]{12}\.js$"
PRECACHE_RESOURCES = (
    "data/evidence-contract.json",
    "data/evidence.schema.json",
    "data/evidence-index.json",
    "data/evidence-index.schema.json",
)


def _publish_js(repository_root: Path, output_dir: Path) -> str:
    source = (repository_root / ASSET_SOURCE).read_text(encoding="utf-8")
    filename = f"evidence.{finalize_dashboard.content_hash(source)}.js"
    target = output_dir / "assets" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8", newline="\n")
    return f"assets/{filename}"


def _inject(output_dir: Path, asset_path: str) -> None:
    markup = (
        f'  <script defer src="{asset_path}" '
        'data-platform-script="evidence"></script>\n'
    )
    for path in sorted(output_dir.glob("*.html")):
        source = path.read_text(encoding="utf-8")
        if 'data-platform-script="evidence"' in source:
            continue
        if "</body>" not in source:
            raise ValueError(f"{path.name} has no body closing tag for evidence injection")
        path.write_text(
            source.replace("</body>", markup + "</body>", 1),
            encoding="utf-8",
            newline="\n",
        )


def _patch_manifest_schema(schema: dict[str, Any], manifest: dict[str, Any]) -> None:
    properties = schema.setdefault("properties", {})
    assets = properties.setdefault("assets", {"type": "object"})
    required = assets.setdefault("required", [])
    asset_properties = assets.setdefault("properties", {})
    if ASSET_KEY not in required:
        required.append(ASSET_KEY)
    asset_properties[ASSET_KEY] = {"type": "string", "pattern": ASSET_PATTERN}
    assets["additionalProperties"] = False

    canonical = properties.get("canonical_pipeline")
    if isinstance(canonical, dict):
        canonical_properties = canonical.setdefault("properties", {})
        canonical_properties["script_sources"] = {
            "type": "array",
            "const": manifest["canonical_pipeline"]["script_sources"],
        }


def _sync_manifest_contracts(output_dir: Path, manifest: dict[str, Any]) -> None:
    manifest_schema_path = output_dir / "data" / "build-manifest.schema.json"
    payload_schema_path = output_dir / "data" / "schema.json"
    manifest_schema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))
    payload_schema = json.loads(payload_schema_path.read_text(encoding="utf-8"))
    _patch_manifest_schema(manifest_schema, manifest)
    _patch_manifest_schema(payload_schema["$defs"]["manifest"], manifest)
    finalize_dashboard.write_json(manifest_schema_path, manifest_schema)
    finalize_dashboard.write_json(payload_schema_path, payload_schema)

    pokemon_path = output_dir / "data" / "pokemon.json"
    pokemon = json.loads(pokemon_path.read_text(encoding="utf-8"))
    pokemon["manifest"] = manifest
    finalize_dashboard.write_json(pokemon_path, pokemon, compact=True)
    finalize_dashboard.write_json(output_dir / "data" / "build-manifest.json", manifest)


def _extend_precache(output_dir: Path, asset_path: str) -> None:
    path = output_dir / "sw.js"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    match = re.search(r"const PRECACHE = (\[[^\n]*\]);", source)
    if not match:
        raise ValueError("Generated service worker has no parseable PRECACHE array")
    values = json.loads(match.group(1))
    for value in (*PRECACHE_RESOURCES, asset_path):
        if value not in values:
            values.append(value)
    replacement = f"const PRECACHE = {json.dumps(values, ensure_ascii=False)};"
    path.write_text(
        source[: match.start()] + replacement + source[match.end() :],
        encoding="utf-8",
        newline="\n",
    )


def publish(
    repository_root: Path,
    output_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Install the evidence component after platform publication and resync contracts."""
    asset_path = _publish_js(repository_root, output_dir)
    manifest.setdefault("assets", {})[ASSET_KEY] = asset_path
    scripts = manifest.setdefault("canonical_pipeline", {}).setdefault(
        "script_sources", []
    )
    if ASSET_SOURCE not in scripts:
        scripts.append(ASSET_SOURCE)

    _inject(output_dir, asset_path)
    _sync_manifest_contracts(output_dir, manifest)
    _extend_precache(output_dir, asset_path)

    llms_path = output_dir / "llms.txt"
    if llms_path.is_file():
        with llms_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "\nTrust and evidence contract:\n"
                "- /data/evidence-contract.json defines shared evidence kinds, "
                "freshness, confidence, prerequisite, and remediation semantics.\n"
                "- /data/evidence-index.json maps consequential cards/pages to the "
                "same typed evidence objects used by the browser component.\n"
                "- Freshness and confidence are separate; unknown is never false or zero.\n"
                "- Official current facts and simulations use different textual and "
                "machine semantics, not color alone.\n"
            )
    return {"asset": asset_path, "resources": list(PRECACHE_RESOURCES)}


__all__ = ["ASSET_KEY", "ASSET_SOURCE", "ASSET_PATTERN", "publish"]
