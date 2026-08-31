from __future__ import annotations

import unittest

from scripts import sync_rocket_battle_mechanics as rocket


class RocketBattleMechanicsSyncTests(unittest.TestCase):
    def test_extract_multipliers_reads_expected_damage_constants(self) -> None:
        source = """
        sameTypeBonus = 1.2;
        typeEffectivenessBonus = 1.6;
        typeEffectivenessPenalty = 0.625;
        typeEffectivenessDoublePenalty = 0.390625;
        shadowBonus = 1.2;
        trainerBattleBonus = 1.3;
        """
        self.assertEqual(
            rocket.extract_multipliers(source),
            {
                "same_type_attack_bonus": 1.2,
                "super_effective": 1.6,
                "resisted": 0.625,
                "double_resisted": 0.390625,
                "shadow_attack_bonus": 1.2,
                "trainer_battle_bonus": 1.3,
            },
        )

    def test_extract_multipliers_fails_closed_when_upstream_contract_changes(self) -> None:
        with self.assertRaisesRegex(ValueError, "sameTypeBonus"):
            rocket.extract_multipliers("typeEffectivenessBonus = 1.6;")

    def test_extract_type_traits_requires_complete_type_table(self) -> None:
        cases = []
        for type_name in sorted(rocket.EXPECTED_TYPES):
            cases.append(
                f'case "{type_name}": traits = {{resistances: ["fire"], weaknesses: ["water"], '
                'immunities: []}; break;'
            )
        traits = rocket.extract_type_traits("\n".join(cases))
        self.assertEqual(set(traits), rocket.EXPECTED_TYPES)
        self.assertEqual(traits["normal"]["resistances"], ["fire"])

    def test_normalize_move_preserves_supported_battle_fields(self) -> None:
        move = rocket.normalize_move(
            {
                "moveId": "TEST_MOVE",
                "name": "Test Move",
                "type": "Electric",
                "power": 5,
                "energy": 35,
                "energyGain": 8,
                "cooldown": 500,
                "turns": 1,
                "archetype": "General",
                "buffs": [1, 0],
                "buffTarget": "self",
                "buffApplyChance": "0.5",
            }
        )
        self.assertIsNotNone(move)
        assert move is not None
        self.assertEqual(move["type"], "electric")
        self.assertEqual(move["energy_gain"], 8.0)
        self.assertEqual(move["buff_apply_chance"], 0.5)

    def test_normalize_move_rejects_incomplete_or_unknown_type_rows(self) -> None:
        self.assertIsNone(rocket.normalize_move({"moveId": "BAD", "name": "Bad", "type": "cosmic"}))


if __name__ == "__main__":
    unittest.main()
