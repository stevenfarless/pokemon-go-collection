"""Evaluate reviewed Pokémon GO trade rules from a versioned local registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "trade-rules.v1.json"


def load_registry(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or REGISTRY_PATH).read_text(encoding="utf-8"))


def _known_bool(values: Mapping[str, Any], key: str) -> bool | None:
    value = values.get(key)
    return value if isinstance(value, bool) else None


def evaluate_trade(
    mode: str,
    pokemon: Mapping[str, Any],
    friend: Mapping[str, Any] | None = None,
    trainer: Mapping[str, Any] | None = None,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rules = dict(registry or load_registry())
    mode_rules = (rules.get("modes") or {}).get(mode)
    if mode_rules is None:
        raise ValueError(f"Unsupported trade mode: {mode}")

    friend = dict(friend or {})
    trainer = dict(trainer or {})
    blockers: list[str] = []
    unknowns: list[str] = []

    minimum = mode_rules.get("trainer_min_level")
    if minimum is not None:
        level = trainer.get("level")
        if level is None:
            unknowns.append("trainer_level")
        elif int(level) < int(minimum):
            blockers.append("trainer_level_below_minimum")

    if mode_rules.get("requires_forever_friend"):
        value = _known_bool(friend, "forever_friend")
        if value is None:
            unknowns.append("forever_friend")
        elif value is False:
            blockers.append("not_forever_friends")

    if mode_rules.get("requires_available_remote_trade"):
        value = _known_bool(friend, "remote_trade_available")
        if value is None:
            unknowns.append("remote_trade_available")
        elif value is False:
            blockers.append("no_remote_trade_available")

    if mode == "remote":
        count = friend.get("remote_trades_completed_today")
        if count is None:
            unknowns.append("remote_trades_completed_today")
        elif int(count) >= int(rules["friendship"]["remote_trade"]["completed_per_day_limit"]):
            blockers.append("remote_daily_limit_reached")

    for key in mode_rules.get("hard_blockers") or []:
        value = _known_bool(pokemon, key)
        if value is None:
            unknowns.append(key)
        elif value:
            blockers.append(key)

    state = "blocked" if blockers else "unknown" if unknowns else "eligible"
    special = False if mode == "remote" else any(
        _known_bool(pokemon, key) is True for key in mode_rules.get("special_trade_categories") or []
    )

    return {
        "state": state,
        "mode": mode,
        "blockers": sorted(set(blockers)),
        "unknowns": sorted(set(unknowns)),
        "special_trade": special,
        "lucky": _known_bool(friend, "lucky_friend") is True,
        "post_trade_stats_guaranteed": False,
        "exact_stardust_cost": None,
        "requires_game_confirmation": True,
        "reviewed_at": rules.get("reviewed_at"),
    }


__all__ = ["REGISTRY_PATH", "load_registry", "evaluate_trade"]
