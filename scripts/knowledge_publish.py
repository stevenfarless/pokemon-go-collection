"""Publish the committed Pokémon GO knowledge snapshot as static public resources."""

from __future__ import annotations

import shutil
from pathlib import Path

try:
    from . import manifest_registry
except ImportError:
    import manifest_registry

PUBLIC_KNOWLEDGE_FILES = (
    "pokemon-go.json",
    "pokemon-go.schema.json",
    "species-index.json",
    "species-index.schema.json",
    "glossary.json",
    "glossary.schema.json",
    "PVPOKE-LICENSE.txt",
)


def publish_repository_knowledge(repository_root: Path, output_dir: Path) -> None:
    source_dir = repository_root / "knowledge"
    target_dir = output_dir / "data" / "knowledge"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    for filename in PUBLIC_KNOWLEDGE_FILES:
        source = source_dir / filename
        if not source.is_file():
            raise ValueError(
                f"Committed Pokémon GO knowledge resource is missing: knowledge/{filename}. "
                "Run scripts/sync_knowledge.py."
            )
        shutil.copyfile(source, target_dir / filename)

    manifest_registry._SCHEMA_MAP["data/knowledge/glossary.json"] = "data/knowledge/glossary.schema.json"
    manifest_registry._STABLE_NAMES.update(
        {
            "data/knowledge/glossary.json": "pokemon_go_glossary",
            "data/knowledge/glossary.schema.json": "pokemon_go_glossary_schema",
        }
    )
