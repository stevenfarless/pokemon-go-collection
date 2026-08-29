from __future__ import annotations

import unittest

from scripts import trade_rules


class TradeRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = trade_rules.load_registry()

    def test_remote_trade_fails_closed_on_unknown_required_facts(self) -> None:
        result = trade_rules.evaluate_trade("remote", {}, {}, registry=self.registry)
        self.assertEqual(result["state"], "unknown")
        self.assertIn("forever_friend", result["unknowns"])
        self.assertIn("remote_trade_available", result["unknowns"])
        self.assertFalse(result["special_trade"])
        self.assertIsNone(result["exact_stardust_cost"])
        self.assertTrue(result["requires_game_confirmation"])

    def test_remote_trade_blocks_current_official_exclusions(self) -> None:
        pokemon = {key: False for key in self.registry["modes"]["remote"]["hard_blockers"]}
        pokemon["current_buddy"] = True
        friend = {
            "forever_friend": True,
            "remote_trade_available": True,
            "remote_trades_completed_today": 0,
            "lucky_friend": True,
        }
        result = trade_rules.evaluate_trade("remote", pokemon, friend, registry=self.registry)
        self.assertEqual(result["state"], "blocked")
        self.assertIn("current_buddy", result["blockers"])
        self.assertTrue(result["lucky"])
        self.assertFalse(result["post_trade_stats_guaranteed"])

    def test_remote_trade_enforces_daily_limit(self) -> None:
        pokemon = {key: False for key in self.registry["modes"]["remote"]["hard_blockers"]}
        friend = {
            "forever_friend": True,
            "remote_trade_available": True,
            "remote_trades_completed_today": 1,
        }
        result = trade_rules.evaluate_trade("remote", pokemon, friend, registry=self.registry)
        self.assertEqual(result["state"], "blocked")
        self.assertIn("remote_daily_limit_reached", result["blockers"])

    def test_in_person_special_trade_classification_is_separate_from_eligibility(self) -> None:
        pokemon = {key: False for key in self.registry["modes"]["in_person"]["hard_blockers"]}
        pokemon.update({key: False for key in self.registry["modes"]["in_person"]["special_trade_categories"]})
        pokemon["shiny"] = True
        result = trade_rules.evaluate_trade("in_person", pokemon, trainer={"level": 10}, registry=self.registry)
        self.assertEqual(result["state"], "eligible")
        self.assertTrue(result["special_trade"])

    def test_friendship_registry_contains_forever_friend_and_remote_trade_rules(self) -> None:
        milestones = {item["id"]: item["points"] for item in self.registry["friendship"]["milestones"]}
        remote = self.registry["friendship"]["remote_trade"]
        self.assertEqual(milestones["forever"], 180)
        self.assertEqual(remote["subsequent_unlock_points"], 90)
        self.assertEqual(remote["completed_per_day_limit"], 1)
        self.assertEqual(remote["step_response_window_hours"], 48)


if __name__ == "__main__":
    unittest.main()
