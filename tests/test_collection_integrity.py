from __future__ import annotations

import copy
import unittest
from datetime import date

from scripts import build_site
from scripts.collection_integrity import process_collection, reconcile_records


class CollectionIntegrityTests(unittest.TestCase):
    def row(self, **overrides: str) -> dict[str, str]:
        values = {
            "Index": "1",
            "Name": "Mewtwo",
            "Form": "",
            "Pokemon Number": "150",
            "Gender": "",
            "CP": "2387",
            "HP": "155",
            "Atk IV": "15",
            "Def IV": "14",
            "Sta IV": "13",
            "IV Avg": "93.3",
            "Level Min": "20",
            "Level Max": "20",
            "Quick Move": "Confusion",
            "Charge Move": "Shadow Ball",
            "Charge Move 2": "",
            "Scan Date": "2026-08-01",
            "Original Scan Date": "2026-08-01",
            "Catch Date": "2026-07-31",
            "Weight": "122",
            "Height": "2",
            "Lucky": "0",
            "Shadow/Purified": "0",
            "Favorite": "1",
            "Dust": "2500",
            "Marked for PvP use": "0",
        }
        values.update(overrides)
        return values

    def normalize(self, rows: list[dict[str, str]]) -> list[dict]:
        return [build_site.normalize_row(row, number) for number, row in enumerate(rows, start=2)]

    def test_incomplete_and_complete_rescan_collapse_to_richest_record(self) -> None:
        incomplete = self.row(**{"Quick Move": "", "Charge Move": "", "Weight": "", "Index": "10"})
        complete = self.row(Index="11")
        rows = [incomplete, complete]
        normalized, report, _ = reconcile_records(
            rows,
            self.normalize(rows),
            source_filename="shared-text-2026-08-01 12_00_00.000.csv",
        )

        self.assertEqual(len(normalized), 1)
        self.assertEqual(report["source_record_count"], 2)
        self.assertEqual(report["normalized_record_count"], 1)
        self.assertEqual(report["duplicates_collapsed"], 1)
        self.assertEqual(report["automatic_group_count"], 1)
        record = normalized[0]
        self.assertEqual(record["moves"]["fast"], "Confusion")
        self.assertEqual(record["provenance"]["source_rows"], [2, 3])
        self.assertEqual(record["provenance"]["source_scan_count"], 2)
        self.assertRegex(record["identity"]["record_id"], r"^pgc_[0-9a-f]{20}$")
        self.assertRegex(record["identity"]["record_fingerprint"], r"^fp_[0-9a-f]{20}$")

    def test_conflicting_exact_ivs_are_preserved_for_review(self) -> None:
        first = self.row(Index="20")
        second = self.row(Index="21", **{"Atk IV": "14"})
        rows = [first, second]
        normalized, report, _ = reconcile_records(
            rows,
            self.normalize(rows),
            source_filename="shared-text-2026-08-01 12_00_00.000.csv",
        )

        self.assertEqual(len(normalized), 2)
        self.assertEqual(report["duplicates_collapsed"], 0)
        self.assertEqual(report["automatic_group_count"], 0)
        self.assertEqual(report["possible_group_count"], 1)

    def test_different_original_scan_dates_are_not_automatically_merged(self) -> None:
        first = self.row(Index="30")
        second = self.row(Index="31", **{"Original Scan Date": "2026-07-15"})
        rows = [first, second]
        normalized, report, _ = reconcile_records(
            rows,
            self.normalize(rows),
            source_filename="shared-text-2026-08-01 12_00_00.000.csv",
        )
        self.assertEqual(len(normalized), 2)
        self.assertEqual(report["duplicates_collapsed"], 0)

    def test_cross_build_fingerprint_survives_reordering(self) -> None:
        mewtwo = self.row(Index="40")
        pikachu = self.row(
            Index="41",
            Name="Pikachu",
            **{"Pokemon Number": "25", "CP": "500", "HP": "80", "Original Scan Date": "2026-07-20"},
        )
        first_records, _, _ = reconcile_records(
            [mewtwo, pikachu],
            self.normalize([mewtwo, pikachu]),
            source_filename="shared-text-2026-08-01 12_00_00.000.csv",
        )
        second_records, _, _ = reconcile_records(
            [pikachu, mewtwo],
            self.normalize([pikachu, mewtwo]),
            source_filename="shared-text-2026-08-02 12_00_00.000.csv",
        )
        first = {record["name"]: record["identity"]["record_fingerprint"] for record in first_records}
        second = {record["name"]: record["identity"]["record_fingerprint"] for record in second_records}
        self.assertEqual(first, second)

    def test_scan_quality_links_findings_to_canonical_records(self) -> None:
        incomplete = self.row(
            Index="50",
            **{
                "Atk IV": "",
                "Def IV": "",
                "Sta IV": "",
                "Level Min": "",
                "Level Max": "",
                "Quick Move": "",
                "Scan Date": "2025-01-01",
            },
        )
        records, deduplication, quality = process_collection(
            [incomplete],
            self.normalize([incomplete]),
            source_filename="shared-text-2026-08-01 12_00_00.000.csv",
            reference_date=date(2026, 8, 1),
            unknown_columns=["Future Field"],
            semantic_warnings=[
                {
                    "row_number": 2,
                    "source_index": "50",
                    "column": "Favorite",
                    "message": "unrecognized boolean value",
                }
            ],
        )
        self.assertEqual(deduplication["duplicates_collapsed"], 0)
        reasons = {finding["reason_code"] for finding in quality["findings"]}
        self.assertIn("missing_exact_ivs", reasons)
        self.assertIn("missing_level", reasons)
        self.assertIn("incomplete_moves", reasons)
        self.assertIn("stale_scan", reasons)
        self.assertIn("unknown_source_column", reasons)
        self.assertIn("parser_warning_favorite", reasons)
        record_id = records[0]["identity"]["record_id"]
        linked = [finding for finding in quality["findings"] if finding["reason_code"] == "missing_exact_ivs"]
        self.assertEqual(linked[0]["record_id"], record_id)
        self.assertIn("species_and_form_semantics", quality["coverage"])

    def test_reconciliation_is_deterministic(self) -> None:
        rows = [self.row(Index="60"), self.row(Index="61")]
        first = reconcile_records(
            rows,
            self.normalize(rows),
            source_filename="shared-text-2026-08-01 12_00_00.000.csv",
        )
        second = reconcile_records(
            copy.deepcopy(rows),
            self.normalize(copy.deepcopy(rows)),
            source_filename="shared-text-2026-08-01 12_00_00.000.csv",
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
