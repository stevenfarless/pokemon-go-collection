from __future__ import annotations

import copy
import json
import random
import string
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts import build_site
from scripts.collection_integrity import reconcile_records
from scripts.decision_support import build_investment_inputs, build_reasoning_results
from scripts.external_game_data import assess_freshness, normalize_snapshot
from scripts.schema_contracts import CORE_COLUMNS, analyze_source_columns, iv_schema


SEED = 0x504F4B45


def complete_row(**overrides: str) -> dict[str, str]:
    row = {
        "Index": "1", "Name": "Mewtwo", "Form": "", "Pokemon Number": "150", "Gender": "",
        "CP": "2387", "HP": "155", "Atk IV": "15", "Def IV": "14", "Sta IV": "13",
        "IV Avg": "93.3", "Level Min": "20", "Level Max": "20", "Quick Move": "Confusion",
        "Charge Move": "Shadow Ball", "Charge Move 2": "", "Scan Date": "2026-08-01",
        "Original Scan Date": "2026-08-01", "Catch Date": "2026-07-31", "Weight": "122",
        "Height": "2", "Lucky": "0", "Shadow/Purified": "0", "Favorite": "1", "Dust": "2500",
        "Marked for PvP use": "0",
    }
    row.update(overrides)
    return row


def decision_record(record_id: str, cp: int) -> dict:
    empty_league = {
        "rank_percent": None, "rank_number": None, "stat_product": None, "dust_cost": None,
        "candy_cost": None, "evolution_name": None, "evolution_form": None,
    }
    return {
        "pokemon_number": 1, "name": "Bulbasaur", "form": None, "gender": "Male", "cp": cp, "hp": 100,
        "ivs": {"attack": None, "defense": None, "stamina": None, "average_percent": None, "total": None, "is_hundo": False, "is_nundo": False},
        "level": {"minimum": None, "maximum": None},
        "moves": {"fast": None, "charged": None, "charged_second": None},
        "dates": {"scan": "2026-08-14", "original_scan": "2026-01-01", "catch": "2026-01-01"},
        "size": {"weight": 1.0, "height": 1.0},
        "status": {"lucky": False, "shadow_purified": "normal", "favorite": False, "marked_for_pvp": False},
        "dust": 2500,
        "pvp": {"great": dict(empty_league), "ultra": dict(empty_league), "little": dict(empty_league)},
        "identity": {"record_id": record_id},
    }


def decision_knowledge() -> dict:
    return {
        "species_id": "BULBASAUR", "types": ["grass", "poison"],
        "base_stats": {"attack": 118, "defense": 111, "stamina": 128},
        "second_charged_move_cost": {"stardust": 10000, "candy": None, "candy_status": "not-provided-by-pinned-source"},
        "family": {"evolution_species_ids": ["IVYSAUR"], "evolution_candy_cost": None, "special_requirements": None},
    }


class DeterministicFuzzProperties(unittest.TestCase):
    def test_export_filename_round_trip_and_malformed_inputs(self) -> None:
        rng = random.Random(SEED)
        origin = datetime(2020, 1, 1)
        for _ in range(300):
            stamp = origin + timedelta(milliseconds=rng.randrange(0, 12 * 365 * 24 * 60 * 60 * 1000))
            name = stamp.strftime("shared-text-%Y-%m-%d %H_%M_%S.") + f"{stamp.microsecond // 1000:03d}.csv"
            parsed = build_site.parse_export_filename(Path(name))
            self.assertIsNotNone(parsed, name)
            self.assertEqual(parsed.timestamp, stamp.replace(microsecond=(stamp.microsecond // 1000) * 1000))
            for malformed in (name.replace("shared-text-", "sharedtext-", 1), name.removesuffix(".csv") + ".txt", name.replace("_", ":", 1), "x" + name):
                self.assertIsNone(build_site.parse_export_filename(Path(malformed)), malformed)

    def test_random_source_schema_reports_exactly_missing_core_columns(self) -> None:
        rng = random.Random(SEED + 1)
        extras = ["Atk IV", "Favorite", "Future Column", "Charge Move"]
        for _ in range(200):
            chosen_core = [column for column in CORE_COLUMNS if rng.random() >= 0.35]
            fieldnames = chosen_core + [column for column in extras if rng.random() >= 0.5]
            rng.shuffle(fieldnames)
            report = analyze_source_columns(fieldnames)
            self.assertEqual(set(report["missing_required_columns"]), set(CORE_COLUMNS) - set(chosen_core))
            self.assertEqual(bool(report["missing_required_columns"]), not set(CORE_COLUMNS).issubset(fieldnames))

    def test_core_numeric_garbage_never_becomes_plausible_zero(self) -> None:
        rng = random.Random(SEED + 2)
        alphabet = string.ascii_letters + "!@#$%^&*()[]{}"
        for _ in range(250):
            garbage = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 18)))
            with self.assertRaisesRegex(ValueError, "Pokémon number"):
                build_site.normalize_row({"Name": "Pikachu", "Pokemon Number": garbage, "CP": "500"}, 2)
            with self.assertRaisesRegex(ValueError, "CP value"):
                build_site.normalize_row({"Name": "Pikachu", "Pokemon Number": "25", "CP": garbage}, 2)

    def test_normalization_is_deterministic_for_random_optional_fields(self) -> None:
        rng = random.Random(SEED + 3)
        optional = ["HP", "Atk IV", "Def IV", "Sta IV", "IV Avg", "Weight", "Height", "Dust"]
        choices = ["", " ", "0", "1", "15", "1,234", "-1", "abc", "99.5", "∞"]
        for index in range(200):
            row = {"Name": "Eevee", "Pokemon Number": "133", "CP": "500"}
            for field in optional:
                row[field] = rng.choice(choices)
            first = build_site.normalize_row(dict(row), index + 2)
            second = build_site.normalize_row(dict(row), index + 2)
            self.assertEqual(first, second)
            for value in (first["hp"], first["ivs"]["attack"], first["ivs"]["defense"], first["ivs"]["stamina"]):
                self.assertTrue(value is None or isinstance(value, (int, float)))

    def test_unknown_boolean_and_shadow_values_fail_closed(self) -> None:
        rng = random.Random(SEED + 4)
        for _ in range(200):
            token = "".join(rng.choice(string.ascii_letters) for _ in range(rng.randint(2, 16)))
            if token in {"true", "True", "TRUE", "yes", "Yes"}:
                continue
            self.assertFalse(build_site.truthy(token))
            self.assertEqual(build_site.shadow_status(token), "normal")

    def test_identity_reconciliation_collapses_only_unambiguous_rescans(self) -> None:
        rng = random.Random(SEED + 5)
        for index in range(100):
            attack = rng.randrange(0, 16)
            base = complete_row(Index=str(index * 2 + 1), **{"Atk IV": str(attack)})
            duplicate = copy.deepcopy(base)
            duplicate["Index"] = str(index * 2 + 2)
            rows = [base, duplicate]
            normalized = [build_site.normalize_row(row, row_number) for row_number, row in enumerate(rows, start=2)]
            collapsed, report, _ = reconcile_records(rows, normalized, source_filename="shared-text-2026-08-01 12_00_00.000.csv")
            self.assertEqual(len(collapsed), 1)
            self.assertEqual(report["duplicates_collapsed"], 1)

            conflict = copy.deepcopy(duplicate)
            conflict["Atk IV"] = str((attack + 1) % 16)
            conflict_rows = [base, conflict]
            conflict_normalized = [build_site.normalize_row(row, row_number) for row_number, row in enumerate(conflict_rows, start=2)]
            preserved, conflict_report, _ = reconcile_records(conflict_rows, conflict_normalized, source_filename="shared-text-2026-08-01 12_00_00.000.csv")
            self.assertEqual(len(preserved), 2)
            self.assertEqual(conflict_report["duplicates_collapsed"], 0)

    def test_normalized_ivs_obey_schema_and_out_of_range_values_are_rejected_by_contract(self) -> None:
        rng = random.Random(SEED + 6)
        validator = Draft202012Validator(iv_schema())
        for _ in range(200):
            values = [rng.randrange(0, 16) for _ in range(3)]
            row = complete_row(**{"Atk IV": str(values[0]), "Def IV": str(values[1]), "Sta IV": str(values[2]), "IV Avg": str(sum(values) / 45 * 100)})
            ivs = build_site.normalize_row(row, 2)["ivs"]
            self.assertTrue(validator.is_valid(ivs), list(validator.iter_errors(ivs)))
            self.assertFalse(validator.is_valid(dict(ivs, attack=rng.randrange(16, 100))))

    def test_external_freshness_is_monotonic_across_fresh_stale_expired_windows(self) -> None:
        fixture = json.loads(Path("tests/fixtures/external-game-data-example.json").read_text(encoding="utf-8"))
        origin = datetime(2026, 8, 14, tzinfo=timezone.utc)
        normalized = normalize_snapshot(fixture, now=origin)
        rng = random.Random(SEED + 7)
        for _ in range(120):
            self.assertEqual(assess_freshness(normalized, now=origin + timedelta(hours=rng.randrange(0, 24)))["state"], "fresh")
            self.assertEqual(assess_freshness(normalized, now=origin + timedelta(hours=rng.randrange(25, 48)))["state"], "stale")
            self.assertEqual(assess_freshness(normalized, now=origin + timedelta(hours=rng.randrange(49, 80)))["state"], "expired")

    def test_missing_collection_facts_always_block_irreversible_recommendations(self) -> None:
        rng = random.Random(SEED + 8)
        knowledge = decision_knowledge()
        for index in range(80):
            record = decision_record(f"pgc_fuzz{index:016x}", rng.randrange(10, 5000))
            investments = [build_investment_inputs(record, knowledge, knowledge_dataset_version="fuzz-fixture")]
            result = build_reasoning_results([record], investments, build_id="abcdef123456")
            item = result["records"][0]
            self.assertIn("transfer", item["irreversible_actions_blocked"])
            self.assertEqual(item["recommendations"][0]["recommendation"], "review_or_rescan_before_consequential_decision")


if __name__ == "__main__":
    unittest.main()
