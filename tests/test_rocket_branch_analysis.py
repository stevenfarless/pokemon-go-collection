from __future__ import annotations

import unittest

from scripts import rocket_branch_analysis


class RocketBranchAnalysisTests(unittest.TestCase):
    def test_complete_branch_summary_uses_floor_ceiling_and_worst_case(self) -> None:
        coverage = [
            {
                "slot": 2,
                "opponent_dex": 143,
                "best_effectiveness_multiplier": 1.6,
                "worst_case_same_type_attack_multiplier": 1.0,
            },
            {
                "slot": 2,
                "opponent_dex": 248,
                "best_effectiveness_multiplier": 2.56,
                "worst_case_same_type_attack_multiplier": 0.625,
            },
        ]

        result = rocket_branch_analysis.summarize_branch_coverage(coverage)

        self.assertEqual(len(result), 1)
        slot = result[0]
        self.assertEqual(slot["possibility_count"], 2)
        self.assertEqual(slot["opponent_dexes"], [143, 248])
        self.assertEqual(slot["offensive_state"], "available")
        self.assertEqual(slot["offensive_floor_multiplier"], 1.6)
        self.assertEqual(slot["offensive_ceiling_multiplier"], 2.56)
        self.assertEqual(slot["defensive_same_type_state"], "available")
        self.assertEqual(slot["defensive_worst_case_same_type_multiplier"], 1.0)

    def test_partial_branch_does_not_emit_incomplete_aggregate(self) -> None:
        coverage = [
            {
                "slot": 1,
                "opponent_dex": 19,
                "best_effectiveness_multiplier": 1.6,
                "worst_case_same_type_attack_multiplier": 1.0,
            },
            {
                "slot": 1,
                "opponent_dex": 20,
                "best_effectiveness_multiplier": None,
                "worst_case_same_type_attack_multiplier": None,
            },
        ]

        slot = rocket_branch_analysis.summarize_branch_coverage(coverage)[0]

        self.assertEqual(slot["offensive_known_count"], 1)
        self.assertEqual(slot["offensive_state"], "partial")
        self.assertIsNone(slot["offensive_floor_multiplier"])
        self.assertIsNone(slot["offensive_ceiling_multiplier"])
        self.assertEqual(slot["defensive_same_type_known_count"], 1)
        self.assertEqual(slot["defensive_same_type_state"], "partial")
        self.assertIsNone(slot["defensive_worst_case_same_type_multiplier"])

    def test_wrapper_preserves_recommendation_gate(self) -> None:
        original = rocket_branch_analysis.rocket_matchup.analyze_owned_matchup
        rocket_branch_analysis.rocket_matchup.analyze_owned_matchup = lambda candidate, matchup_context, mechanics: {
            "coverage": [
                {
                    "slot": 1,
                    "opponent_dex": 143,
                    "best_effectiveness_multiplier": 1.6,
                    "worst_case_same_type_attack_multiplier": 1.0,
                }
            ],
            "recommendation": {"state": "blocked-missing-rocket-battle-inputs"},
        }
        try:
            result = rocket_branch_analysis.analyze_owned_branch_matchup({}, {}, {})
        finally:
            rocket_branch_analysis.rocket_matchup.analyze_owned_matchup = original

        self.assertEqual(result["recommendation"]["state"], "blocked-missing-rocket-battle-inputs")
        self.assertEqual(result["branch_analysis"]["state"], "available")
        self.assertFalse(result["branch_analysis"]["ranking_allowed"])
        self.assertIn("opponent moves remain unknown", result["branch_analysis"]["slots"][0]["defensive_semantics"])


if __name__ == "__main__":
    unittest.main()
