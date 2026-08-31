from __future__ import annotations

import unittest

from scripts import rocket_matchup


class RocketMatchupContractTests(unittest.TestCase):
    def test_normalizes_branching_slots_with_stable_types(self) -> None:
        encounter = {
            "encounter_id": "leader-example",
            "slots": [
                [{"dex": 1, "name": "Bulbasaur"}],
                [{"dex": 4, "name": "Charmander"}, {"dex": 7, "name": "Squirtle"}],
                [{"dex": 25, "name": "Pikachu"}],
            ],
        }
        reference = {
            "entries": [
                {"dex": 1, "types": ["grass", "poison"], "released": True},
                {"dex": 4, "types": ["fire"], "released": True},
                {"dex": 7, "types": ["water"], "released": True},
                {"dex": 25, "types": ["electric"], "released": True},
            ]
        }

        result = rocket_matchup.normalize_matchup_context(encounter, reference)

        self.assertEqual(result["state"], "available")
        self.assertEqual(len(result["slots"]), 3)
        self.assertEqual([item["dex"] for item in result["slots"][1]["possibilities"]], [4, 7])
        self.assertEqual(result["slots"][0]["possibilities"][0]["types"], ["grass", "poison"])
        self.assertEqual(result["ranking"]["state"], "blocked-missing-battle-inputs")
        self.assertIn("type-effectiveness", result["ranking"]["required_before_ranking"][0])

    def test_marks_dex_with_conflicting_released_form_types_unresolved(self) -> None:
        encounter = {"encounter_id": "form-example", "slots": [[{"dex": 19, "name": "Rattata"}]]}
        reference = {
            "entries": [
                {"dex": 19, "types": ["normal"], "released": True},
                {"dex": 19, "types": ["dark", "normal"], "released": True},
            ]
        }

        result = rocket_matchup.normalize_matchup_context(encounter, reference)

        self.assertEqual(result["state"], "partial")
        self.assertEqual(result["unresolved_dexes"], [19])
        possibility = result["slots"][0]["possibilities"][0]
        self.assertEqual(possibility["types"], [])
        self.assertEqual(possibility["type_state"], "unresolved-form-or-reference")

    def test_empty_or_invalid_lineup_blocks_matchup_context(self) -> None:
        result = rocket_matchup.normalize_matchup_context(
            {"encounter_id": "empty", "slots": [[{"dex": "invalid"}]]},
            {"entries": []},
        )
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["slots"][0]["possibilities"], [])

    def test_owned_candidate_preserves_observed_moves_without_scoring(self) -> None:
        candidate = {
            "record_id": "owned-1",
            "pokemon_number": 68,
            "name": "Machamp",
            "cp": 2900,
            "moves": {"fast": "Counter", "charged": "Dynamic Punch", "charged_second": None},
            "knowledge": {"types": ["fighting"]},
        }

        result = rocket_matchup.analyze_owned_candidate(candidate)

        self.assertEqual(result["record_id"], "owned-1")
        self.assertEqual(result["observed_moves"]["fast"], "Counter")
        self.assertEqual(result["species_types"], ["fighting"])
        self.assertEqual(result["move_typing_state"], "unresolved")
        self.assertIsNone(result["matchup_score"])
        self.assertFalse(result["recommendation_allowed"])


if __name__ == "__main__":
    unittest.main()
