"""Reviewed Team GO Rocket battle rules that are safe to use in planning.

These facts are manually reviewed from current source pages. Timing, opponent level
scaling, and opponent move assignments stay unresolved until separately verified.
"""

from __future__ import annotations

from typing import Any, Mapping

SHIELD_RULES_VERSION = "1.0.0"
SHIELD_RULES_REVIEWED_AT = "2026-09-03"
SHIELD_RULE_SOURCES = {
    "grunt": "https://pokemongohub.net/post/guide/team-go-rocket-battle-guide/",
    "leader": "https://pokemongohub.net/post/guide/rocket-leader-arlo-counters/",
    "giovanni": "https://pokemongohub.net/post/guide/rocket-boss-giovanni-counters/",
}
REQUIRED_BATTLE_INPUTS = (
    "rocket_opponent_move_assignments",
    "rocket_opponent_level_scaling",
    "rocket_battle_timing",
    "damage_and_survivability",
)


def encounter_class(encounter: Mapping[str, Any]) -> str | None:
    """Return the Rocket opponent class only when the identity markers agree."""
    classes: set[str] = set()
    if encounter.get("grunt_type"):
        classes.add("grunt")
    if str(encounter.get("boss") or "").casefold() == "giovanni":
        classes.add("giovanni")
    if encounter.get("leader"):
        classes.add("leader")
    return next(iter(classes)) if len(classes) == 1 else None


def shield_rule(encounter: Mapping[str, Any]) -> dict[str, Any]:
    """Return reviewed shield behavior without inferring unresolved battle mechanics."""
    opponent_class = encounter_class(encounter)
    if opponent_class is None:
        return {
            "state": "unverified-opponent-class",
            "verified": False,
            "opponent_class": None,
            "shield_count": None,
            "shield_trigger": None,
            "source_reference": None,
            "reviewed_at": SHIELD_RULES_REVIEWED_AT,
            "rules_version": SHIELD_RULES_VERSION,
        }

    if opponent_class == "grunt":
        shield_count = 0
        trigger = "none"
    else:
        shield_count = 2
        trigger = "player-first-two-charged-attacks"

    return {
        "state": "verified-community-evidence",
        "verified": True,
        "opponent_class": opponent_class,
        "shield_count": shield_count,
        "shield_trigger": trigger,
        "source_reference": SHIELD_RULE_SOURCES[opponent_class],
        "reviewed_at": SHIELD_RULES_REVIEWED_AT,
        "rules_version": SHIELD_RULES_VERSION,
    }


def battle_input_gate(encounter: Mapping[str, Any]) -> dict[str, Any]:
    """Expose verified Rocket rules and the exact inputs still blocking ranking."""
    shields = shield_rule(encounter)
    missing = list(REQUIRED_BATTLE_INPUTS)
    if not shields["verified"]:
        missing.insert(0, "rocket_shield_behavior")

    return {
        "state": "blocked-missing-battle-inputs",
        "recommendation_allowed": False,
        "verified_rules": {"shields": shields},
        "missing_inputs": missing,
    }


__all__ = [
    "REQUIRED_BATTLE_INPUTS",
    "SHIELD_RULES_REVIEWED_AT",
    "SHIELD_RULES_VERSION",
    "battle_input_gate",
    "encounter_class",
    "shield_rule",
]
