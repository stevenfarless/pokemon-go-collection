"""Cross-feature integration for player labs and existing Action Packs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PRESET_BY_PACK = {
    "rescan-incomplete": "cleanup",
    "duplicate-review": "cleanup",
    "pvp-party": "pvp",
    "raid-max-party": "raid",
    "evolution-review": "general",
    "evolve-current-move-window": "general",
    "remove-frustration": "general",
    "trade-review": "trade",
    "locate-exact": "general",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def integrate(output_dir: Path) -> None:
    """Add reversible cross-links without changing existing rule semantics."""
    packs_path = output_dir / "data" / "action-packs" / "index.json"
    if packs_path.is_file():
        packs = _load(packs_path)
        for pack in packs.get("packs") or []:
            preset_id = PRESET_BY_PACK.get(str(pack.get("id") or ""))
            if preset_id:
                pack["naming_preset_recommendation"] = {
                    "preset_id": preset_id,
                    "route": f"naming-studio.html?preset={preset_id}",
                    "scope": "optional browser-local naming workflow; no in-game rename automation",
                }
        _write(packs_path, packs)

    moves_path = output_dir / "data" / "move-lab.json"
    if moves_path.is_file():
        moves = _load(moves_path)
        for record in moves.get("records") or []:
            record_id = str(record.get("record_id") or "")
            if record_id:
                record["action_pack"] = f"action-packs.html?pack=locate-exact&record={record_id}"
        _write(moves_path, moves)
