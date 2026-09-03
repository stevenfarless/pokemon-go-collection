from scripts.rocket_battle_rules import battle_input_gate, shield_rule


def test_grunts_do_not_use_shields():
    rule = shield_rule({"grunt_type": "Fire"})

    assert rule["verified"] is True
    assert rule["opponent_class"] == "grunt"
    assert rule["shield_count"] == 0
    assert rule["shield_trigger"] == "none"
    assert rule["source_reference"].endswith("/team-go-rocket-battle-guide/")


def test_leaders_use_two_shields_on_first_two_charged_attacks():
    rule = shield_rule({"leader": "Arlo"})

    assert rule["verified"] is True
    assert rule["opponent_class"] == "leader"
    assert rule["shield_count"] == 2
    assert rule["shield_trigger"] == "player-first-two-charged-attacks"
    assert rule["source_reference"].endswith("/rocket-leader-arlo-counters/")


def test_giovanni_uses_two_shields_on_first_two_charged_attacks():
    rule = shield_rule({"boss": "Giovanni"})

    assert rule["verified"] is True
    assert rule["opponent_class"] == "giovanni"
    assert rule["shield_count"] == 2
    assert rule["shield_trigger"] == "player-first-two-charged-attacks"
    assert rule["source_reference"].endswith("/rocket-boss-giovanni-counters/")


def test_unknown_opponent_class_fails_closed():
    rule = shield_rule({"encounter_id": "unknown"})

    assert rule["verified"] is False
    assert rule["state"] == "unverified-opponent-class"
    assert rule["shield_count"] is None
    assert rule["shield_trigger"] is None


def test_conflicting_opponent_markers_fail_closed():
    rule = shield_rule({"grunt_type": "Fire", "leader": "Arlo"})

    assert rule["verified"] is False
    assert rule["state"] == "unverified-opponent-class"
    assert rule["opponent_class"] is None
    assert rule["shield_count"] is None


def test_verified_shields_are_removed_from_missing_battle_inputs():
    gate = battle_input_gate({"leader": "Arlo"})

    assert gate["recommendation_allowed"] is False
    assert gate["verified_rules"]["shields"]["verified"] is True
    assert "rocket_shield_behavior" not in gate["missing_inputs"]
    assert gate["missing_inputs"] == [
        "rocket_opponent_move_assignments",
        "rocket_opponent_level_scaling",
        "rocket_battle_timing",
        "damage_and_survivability",
    ]


def test_unknown_opponent_keeps_shields_in_missing_battle_inputs():
    gate = battle_input_gate({"encounter_id": "unknown"})

    assert gate["recommendation_allowed"] is False
    assert gate["verified_rules"]["shields"]["verified"] is False
    assert gate["missing_inputs"][0] == "rocket_shield_behavior"


def test_conflicting_opponent_markers_keep_shields_blocked():
    gate = battle_input_gate({"boss": "Giovanni", "leader": "Arlo"})

    assert gate["recommendation_allowed"] is False
    assert gate["verified_rules"]["shields"]["verified"] is False
    assert gate["missing_inputs"][0] == "rocket_shield_behavior"
