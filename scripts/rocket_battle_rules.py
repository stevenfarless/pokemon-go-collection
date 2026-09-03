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


def encounter_class(encounter: Mapping[str, Any]) -> str | None:
    """Return the Rocket opponent class when it can be identified safely."""
    if encounter.get("grunt_type"):
        return "grunt"
    if str(encounter.get("boss") or "").casefold() == "giovanni":
        return "giovanni"
    if encounter.get("leader"):
        return "leader"
    return None


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
