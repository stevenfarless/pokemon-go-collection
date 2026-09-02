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

    @staticmethod
    def _candidate_analysis(record_id: str, slots: list[tuple[int, float, float]]) -> dict:
        return {
            "candidate": {"record_id": record_id},
            "branch_analysis": {
                "state": "available",
                "slots": [
                    {
                        "slot": slot,
                        "offensive_state": "available",
                        "offensive_floor_multiplier": offense,
                        "defensive_same_type_state": "available",
                        "defensive_worst_case_same_type_multiplier": defense,
                    }
                    for slot, offense, defense in slots
                ],
            },
        }

    def test_candidate_coverage_dominance_requires_all_slots_to_be_weakly_better(self) -> None:
        stronger = self._candidate_analysis("stronger", [(1, 1.6, 0.625), (2, 1.0, 1.0)])
        weaker = self._candidate_analysis("weaker", [(1, 1.0, 1.0), (2, 1.0, 1.0)])

        result = rocket_branch_analysis.compare_candidate_coverage(stronger, weaker)

        self.assertEqual(result["state"], "available")
        self.assertTrue(result["left_dominates"])
        self.assertFalse(result["right_dominates"])
        self.assertFalse(result["ranking_allowed"])

    def test_candidate_coverage_dominance_blocks_partial_or_mismatched_slots(self) -> None:
        complete = self._candidate_analysis("complete", [(1, 1.6, 0.625), (2, 1.0, 1.0)])
        partial = self._candidate_analysis("partial", [(1, 1.0, 1.0)])
        partial["branch_analysis"]["state"] = "partial"

        result = rocket_branch_analysis.compare_candidate_coverage(complete, partial)

        self.assertEqual(result["state"], "blocked-incomplete-coverage")
        self.assertFalse(result["left_dominates"])
        self.assertFalse(result["right_dominates"])

    def test_candidate_dominance_summary_keeps_exact_record_ids_and_no_party_ranking(self) -> None:
        analyses = [
            self._candidate_analysis("owned-a", [(1, 1.6, 0.625), (2, 1.6, 1.0)]),
            self._candidate_analysis("owned-b", [(1, 1.0, 1.0), (2, 1.6, 1.0)]),
            self._candidate_analysis("owned-c", [(1, 2.56, 1.6), (2, 1.0, 0.625)]),
        ]

        result = rocket_branch_analysis.summarize_candidate_dominance(analyses)

        by_id = {item["record_id"]: item for item in result}
        self.assertEqual(by_id["owned-a"]["dominates_record_ids"], ["owned-b"])
        self.assertEqual(by_id["owned-b"]["dominated_by_record_ids"], ["owned-a"])
        self.assertEqual(by_id["owned-c"]["dominates_record_ids"], [])
        self.assertEqual(by_id["owned-c"]["dominated_by_record_ids"], [])
        self.assertTrue(all(item["comparable_candidate_count"] == 2 for item in result))
        self.assertTrue(all(item["ranking_allowed"] is False for item in result))

    def test_candidate_frontier_keeps_non_dominated_complete_records_and_excludes_partial(self) -> None:
        dominance = [
            {
                "record_id": "owned-a",
                "state": "available",
                "dominated_by_record_ids": [],
            },
            {
                "record_id": "owned-b",
                "state": "available",
                "dominated_by_record_ids": ["owned-a"],
            },
            {
                "record_id": "owned-c",
                "state": "available",
                "dominated_by_record_ids": [],
            },
            {
                "record_id": "owned-unknown",
                "state": "partial",
                "dominated_by_record_ids": [],
            },
        ]

        result = rocket_branch_analysis.summarize_candidate_frontier(dominance)

        self.assertEqual(result["state"], "available")
        self.assertEqual(result["frontier_record_ids"], ["owned-a", "owned-c"])
        self.assertEqual(result["dominated_record_ids"], ["owned-b"])
        self.assertEqual(result["partial_record_ids"], ["owned-unknown"])
        self.assertFalse(result["ranking_allowed"])
        self.assertFalse(result["party_selection_allowed"])

    def test_candidate_frontier_blocks_when_no_complete_candidate_exists(self) -> None:
        result = rocket_branch_analysis.summarize_candidate_frontier(
            [{"record_id": "owned-unknown", "state": "partial", "dominated_by_record_ids": []}]
        )

        self.assertEqual(result["state"], "blocked-no-complete-candidates")
        self.assertEqual(result["frontier_record_ids"], [])
        self.assertEqual(result["partial_record_ids"], ["owned-unknown"])

    def test_multi_candidate_wrapper_preserves_battle_input_gate(self) -> None:
        original = rocket_branch_analysis.analyze_owned_branch_matchup

        def fake(candidate, matchup_context, mechanics):
            return self._candidate_analysis(candidate["record_id"], [(1, candidate["offense"], candidate["defense"])])

        rocket_branch_analysis.analyze_owned_branch_matchup = fake
        try:
            result = rocket_branch_analysis.analyze_owned_branch_candidates(
                [
                    {"record_id": "owned-a", "offense": 1.6, "defense": 0.625},
                    {"record_id": "owned-b", "offense": 1.0, "defense": 1.0},
                ],
                {},
                {},
            )
        finally:
            rocket_branch_analysis.analyze_owned_branch_matchup = original

        self.assertEqual(result["contract_version"], "1.2.0")
        self.assertEqual(result["candidate_dominance"][0]["dominates_record_ids"], ["owned-b"])
        self.assertEqual(result["candidate_frontier"]["frontier_record_ids"], ["owned-a"])
        self.assertEqual(result["candidate_frontier"]["dominated_record_ids"], ["owned-b"])
        self.assertFalse(result["candidate_frontier"]["party_selection_allowed"])
        self.assertEqual(result["recommendation"]["state"], "blocked-missing-rocket-battle-inputs")
        self.assertFalse(result["recommendation"]["ranking_allowed"])


if __name__ == "__main__":
    unittest.main()
