"""Compatibility adapter for versioned CP multiplier knowledge.

The knowledge sync publishes list entries as {level, multiplier}. Early player-lab
consumers also accepted an older {level, cpm} shape. Install one tolerant reader so
Evolution, Hyper Training, and Raid Readiness use the same pinned CP inputs.
"""

from __future__ import annotations

from typing import Any, Mapping


def cpm_for_level(mechanics: Mapping[str, Any], level: float) -> float | None:
    values = mechanics.get("cp_multiplier_levels")
    if isinstance(values, Mapping):
        keys = (str(level), f"{level:.1f}", str(int(level)) if float(level).is_integer() else "")
        for key in keys:
            if key and isinstance(values.get(key), (int, float)):
                return float(values[key])
    if isinstance(values, list):
        for item in values:
            if isinstance(item, Mapping):
                try:
                    matches = float(item.get("level", -1)) == float(level)
                except (TypeError, ValueError):
                    matches = False
                if not matches:
                    continue
                value = item.get("multiplier")
                if not isinstance(value, (int, float)):
                    value = item.get("cpm")
                if isinstance(value, (int, float)):
                    return float(value)
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                try:
                    if float(item[0]) == float(level) and isinstance(item[1], (int, float)):
                        return float(item[1])
                except (TypeError, ValueError):
                    continue
    return None


def install(player_labs_module: Any) -> None:
    """Install the shared reader into the existing player-lab calculation boundary."""
    player_labs_module._cpm_for_level = cpm_for_level


__all__ = ["cpm_for_level", "install"]
