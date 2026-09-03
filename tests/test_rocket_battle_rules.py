from scripts.rocket_battle_rules import shield_rule


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
