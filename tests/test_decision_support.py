from __future__ import annotations

import copy
import unittest

from scripts.decision_support import (
    build_investment_inputs,
    build_reasoning_results,
)


class DecisionSupportTests(unittest.TestCase):
    def record(self, record_id: str, *, rank: float | None = 99.0, dust: int | None = 10000, candy: int | None = 20, attack: int | None = 10, cp: int = 1000) -> dict:
        exact = attack is not None
        return {
            "pokemon_number": 1,
            "name": "Bulbasaur",
            "form": None,
            "gender": "Male",
            "cp": cp,
            "hp": 100,
            "ivs": {
                "attack": attack,
                "defense": 10 if exact else None,
                "stamina": 10 if exact else None,
                "average_percent": 66.7 if exact else None,
                "total": 30 if exact else None,
                "is_hundo": False,
                "is_nundo": False,
            },
            "level": {"minimum": 20.0 if exact else None, "maximum": 20.0 if exact else None},
            "moves": {"fast": "TACKLE" if exact else None, "charged": "SLUDGE_BOMB" if exact else None, "charged_second": None},
            "dates": {"scan": "2026-08-14", "original_scan": "2026-01-01", "catch": "2026-01-01"},
            "size": {"weight": 1.0, "height": 1.0},
            "status": {"lucky": False, "shadow_purified": "normal", "favorite": False, "marked_for_pvp": False},
            "dust": 2500,
            "pvp": {
                "great": {"rank_percent": rank, "rank_number": 10, "stat_product": 99.0, "dust_cost": dust, "candy_cost": candy, "evolution_name": "Ivysaur", "evolution_form": None},
                "ultra": {"rank_percent": None, "rank_number": None, "stat_product": None, "dust_cost": None, "candy_cost": None, "evolution_name": None, "evolution_form": None},
                "little": {"rank_percent": None, "rank_number": None, "stat_product": None, "dust_cost": None, "candy_cost": None, "evolution_name": None, "evolution_form": None},
            },
            "identity": {"record_id": record_id},
        }

    def knowledge(self) -> dict:
        return {
            "species_id": "BULBASAUR",
            "types": ["grass", "poison"],
            "base_stats": {"attack": 118, "defense": 111, "stamina": 128},
            "second_charged_move_cost": {"stardust": 10000, "candy": None, "candy_status": "not-provided-by-pinned-source"},
            "family": {"evolution_species_ids": ["IVYSAUR"], "evolution_candy_cost": None, "special_requirements": None},
        }

    def investments(self, records: list[dict]) -> list[dict]:
        return [build_investment_inputs(record, self.knowledge(), knowledge_dataset_version="fixture") for record in records]

    def test_missing_costs_remain_explicitly_unknown(self) -> None:
        record = self.record("pgc_00000000000000000001", dust=None, candy=None)
        item = build_investment_inputs(record, self.knowledge(), knowledge_dataset_version="fixture")
        build = item["derived"]["pvp_builds"][0]
        self.assertIsNone(build["stardust_cost"])
        self.assertIsNone(build["regular_candy_cost"])
        self.assertIsNone(build["xl_candy_cost"])
        self.assertEqual(build["xl_candy_cost_status"], "not_provided_by_poke_genie_export")
        self.assertIsNone(item["derived"]["elite_tm_recommendation"])

    def test_higher_rank_lower_cost_copy_dominates_without_transfer_action(self) -> None:
        better = self.record("pgc_00000000000000000001", rank=99.8, dust=10000, candy=10)
        worse = self.record("pgc_00000000000000000002", rank=97.0, dust=20000, candy=20)
        result = build_reasoning_results([better, worse], self.investments([better, worse]), build_id="abcdef123456")
        worse_result = next(item for item in result["records"] if item["record_id"] == worse["identity"]["record_id"])
        recommendations = {item["recommendation"] for item in worse_result["recommendations"]}
        self.assertIn("lower_priority_than_an_owned_copy_for_known_pvp_rank_and_cost_inputs", recommendations)
        self.assertNotIn("transfer", {item["action_class"] for item in worse_result["recommendations"]})

    def test_conflicting_rank_and_cost_objectives_require_review(self) -> None:
        rank_leader = self.record("pgc_00000000000000000003", rank=99.9, dust=50000, candy=50)
        cheap = self.record("pgc_00000000000000000004", rank=98.0, dust=5000, candy=5)
        result = build_reasoning_results([rank_leader, cheap], self.investments([rank_leader, cheap]), build_id="abcdef123456")
        all_recommendations = [rec["recommendation"] for item in result["records"] for rec in item["recommendations"]]
        self.assertIn("conflicting_rank_and_cost_objectives", all_recommendations)

    def test_missing_scan_blocks_consequential_decision(self) -> None:
        incomplete = self.record("pgc_00000000000000000005", attack=None, rank=None, dust=None, candy=None)
        result = build_reasoning_results([incomplete], self.investments([incomplete]), build_id="abcdef123456")
        recommendations = result["records"][0]["recommendations"]
        self.assertEqual(recommendations[0]["recommendation"], "review_or_rescan_before_consequential_decision")
        self.assertIn("transfer", result["records"][0]["irreversible_actions_blocked"])

    def test_stale_external_context_is_exposed_as_blocker(self) -> None:
        record = self.record("pgc_00000000000000000006")
        result = build_reasoning_results([record], self.investments([record]), build_id="abcdef123456", external_context={"overall_freshness": "stale"})
        self.assertEqual(result["external_freshness"], "stale")
        recommendations = {item["recommendation"] for item in result["records"][0]["recommendations"]}
        self.assertIn("current_meta_conclusion_blocked", recommendations)

    def test_identical_inputs_are_deterministic(self) -> None:
        records = [self.record("pgc_00000000000000000007")]
        investments = self.investments(records)
        left = build_reasoning_results(copy.deepcopy(records), copy.deepcopy(investments), build_id="abcdef123456")
        right = build_reasoning_results(copy.deepcopy(records), copy.deepcopy(investments), build_id="abcdef123456")
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
