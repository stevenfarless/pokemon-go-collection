from __future__ import annotations

import unittest
from pathlib import Path

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

        with self.assertRaisesRegex(ValueError, "missing"):
            rocket.extract_type_traits("\n".join(cases[:-1]))

    def test_normalize_move_requires_complete_numeric_contract(self) -> None:
        source = {
            "moveId": "COUNTER",
            "name": "Counter",
            "type": "fighting",
            "power": 8,
            "energy": 0,
            "energyGain": 7,
            "cooldown": 1000,
            "turns": 1,
        }
        move = rocket.normalize_move(source)
        self.assertIsNotNone(move)
        assert move is not None
        self.assertEqual(move["move_id"], "COUNTER")
        self.assertEqual(move["type"], "fighting")
        self.assertEqual(move["energy_gain"], 7.0)

        incomplete = dict(source)
        incomplete.pop("turns")
        self.assertIsNone(rocket.normalize_move(incomplete))

    def test_knowledge_sync_workflow_regenerates_and_stages_rocket_mechanics(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow = (root / ".github" / "workflows" / "sync-knowledge.yml").read_text(encoding="utf-8")

        self.assertIn('scripts/sync_rocket_battle_mechanics.py', workflow)
        self.assertIn('python scripts/sync_rocket_battle_mechanics.py', workflow)
        self.assertIn('knowledge/rocket-battle-mechanics.json', workflow)
        self.assertIn('knowledge/rocket-battle-mechanics.schema.json', workflow)


if __name__ == "__main__":
    unittest.main()
