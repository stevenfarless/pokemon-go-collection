from __future__ import annotations

import unittest

from scripts import rocket_matchup


class RocketNumericValidationTests(unittest.TestCase):
    def test_boolean_move_mechanics_do_not_become_numeric_pressure(self) -> None:
        mechanics = {
            "multipliers": {"same_type_attack_bonus": 1.2},
            "moves": [
                {
                    "move_id": "MALFORMED",
                    "name": "Malformed Move",
                    "type": "fighting",
                    "power": True,
                    "energy_gain": True,
                    "turns": True,
                }
            ],
        }
        candidate = {
            "record_id": "owned-malformed",
            "moves": {"fast": "Malformed Move"},
            "knowledge": {"types": ["fighting"]},
        }

        result = rocket_matchup.analyze_owned_candidate(candidate, mechanics)
        pressure = result["pressure_summary"]["fast"]

        self.assertIsNone(pressure["base_power"])
        self.assertIsNone(pressure["stab_adjusted_power"])
        self.assertIsNone(pressure["turns"])
        self.assertIsNone(pressure["power_per_turn"])
        self.assertIsNone(pressure["energy_gain_per_turn"])
        self.assertFalse(result["recommendation_allowed"])


if __name__ == "__main__":
    unittest.main()
