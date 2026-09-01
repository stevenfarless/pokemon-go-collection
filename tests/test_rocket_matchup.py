from __future__ import annotations

import unittest

from scripts import rocket_matchup


MECHANICS = {
    "multipliers": {
        "same_type_attack_bonus": 1.2,
        "super_effective": 1.6,
        "resisted": 0.625,
        "double_resisted": 0.390625,
    },
    "type_traits": {
        "normal": {"weaknesses": ["fighting"], "resistances": [], "immunities": ["ghost"]},
        "rock": {"weaknesses": ["fighting", "ground"], "resistances": ["normal"], "immunities": []},
    },
    "moves": [
        {"move_id": "COUNTER", "name": "Counter", "type": "fighting", "power": 8.0, "energy_gain": 7.0, "turns": 2},
        {"move_id": "DYNAMIC_PUNCH", "name": "Dynamic Punch", "type": "fighting", "power": 90.0, "energy": 50.0, "turns": 1},
    ],
}


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
        self.assertIn("opponent levels", result["ranking"]["required_before_ranking"][0])

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
        self.assertEqual(result["resolved_moves"], {})
        self.assertEqual(result["pressure_state"], "unavailable")
        self.assertEqual(result["pressure_summary"], {})
        self.assertIsNone(result["matchup_score"])
        self.assertFalse(result["recommendation_allowed"])

    def test_owned_candidate_resolves_observed_moves_from_pinned_mechanics(self) -> None:
        candidate = {
            "record_id": "owned-1",
            "moves": {"fast": " Counter ", "charged": "DYNAMIC PUNCH", "charged_second": None},
            "knowledge": {"types": ["fighting"]},
        }

        result = rocket_matchup.analyze_owned_candidate(candidate, MECHANICS)

        self.assertEqual(result["move_typing_state"], "resolved")
        self.assertEqual(result["resolved_moves"]["fast"]["type"], "fighting")
        self.assertEqual(result["resolved_moves"]["charged"]["mechanics"]["move_id"], "DYNAMIC_PUNCH")
        self.assertEqual(result["resolved_moves"]["charged_second"]["state"], "not-observed")
        self.assertEqual(result["pressure_state"], "available")
        self.assertTrue(result["pressure_summary"]["fast"]["same_type_attack_bonus_applies"])
        self.assertAlmostEqual(result["pressure_summary"]["fast"]["power_per_turn"], 4.8)
        self.assertAlmostEqual(result["pressure_summary"]["fast"]["energy_gain_per_turn"], 3.5)
        self.assertAlmostEqual(result["pressure_summary"]["charged"]["power_per_energy"], 2.16)

    def test_pressure_summary_does_not_apply_stab_to_other_types(self) -> None:
        result = rocket_matchup.analyze_owned_candidate(
            {
                "moves": {"fast": "Counter"},
                "knowledge": {"types": ["normal"]},
            },
            MECHANICS,
        )

        pressure = result["pressure_summary"]["fast"]
        self.assertFalse(pressure["same_type_attack_bonus_applies"])
        self.assertEqual(pressure["same_type_attack_bonus_multiplier"], 1.0)
        self.assertEqual(pressure["power_per_turn"], 4.0)

    def test_ambiguous_move_name_does_not_invent_pressure(self) -> None:
        mechanics = {
            **MECHANICS,
            "moves": [
                {"move_id": "AURA_WHEEL_DARK", "name": "Aura Wheel", "type": "dark", "power": 100, "energy": 45},
                {"move_id": "AURA_WHEEL_ELECTRIC", "name": "Aura Wheel", "type": "electric", "power": 100, "energy": 45},
            ],
        }
        result = rocket_matchup.analyze_owned_candidate(
            {"moves": {"fast": "Aura Wheel"}},
            mechanics,
        )

        self.assertEqual(result["move_typing_state"], "unresolved")
        self.assertEqual(result["resolved_moves"]["fast"]["state"], "ambiguous")
        self.assertEqual(result["resolved_moves"]["fast"]["candidate_types"], ["dark", "electric"])
        self.assertEqual(result["pressure_summary"], {})
        self.assertEqual(result["pressure_state"], "unavailable")

    def test_type_effectiveness_multiplies_dual_type_traits(self) -> None:
        self.assertEqual(
            rocket_matchup.type_effectiveness_multiplier("fighting", ["normal"], MECHANICS),
            1.6,
        )
        self.assertAlmostEqual(
            rocket_matchup.type_effectiveness_multiplier("fighting", ["normal", "rock"], MECHANICS),
            2.56,
        )
        self.assertEqual(
            rocket_matchup.type_effectiveness_multiplier("ghost", ["normal"], MECHANICS),
            0.390625,
        )

    def test_owned_matchup_exposes_coverage_without_recommendation(self) -> None:
        candidate = {
            "record_id": "owned-1",
            "moves": {"fast": "Counter", "charged": "Dynamic Punch"},
            "knowledge": {"types": ["fighting"]},
        }
        context = {
            "slots": [
                {
                    "slot": 1,
                    "possibilities": [
                        {"dex": 143, "name": "Snorlax", "types": ["normal"]},
                        {"dex": 248, "name": "Tyranitar", "types": ["rock", "normal"]},
                    ],
                }
            ]
        }

        result = rocket_matchup.analyze_owned_matchup(candidate, context, MECHANICS)

        self.assertEqual(result["coverage_state"], "available")
        self.assertEqual(result["coverage"][0]["best_effectiveness_multiplier"], 1.6)
        self.assertAlmostEqual(result["coverage"][1]["best_effectiveness_multiplier"], 2.56)
        self.assertEqual(result["candidate"]["pressure_state"], "available")
        self.assertEqual(result["recommendation"]["state"], "blocked-missing-rocket-battle-inputs")
        self.assertFalse(result["candidate"]["recommendation_allowed"])


if __name__ == "__main__":
    unittest.main()
