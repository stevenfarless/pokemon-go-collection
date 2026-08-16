from __future__ import annotations

import unittest
from datetime import date

from scripts import build_site
from scripts.collection_integrity import reconcile_records
from scripts.longitudinal_reconciliation import process_longitudinal_collection


class LongitudinalReconciliationTests(unittest.TestCase):
    def row(self, **overrides: str) -> dict[str, str]:
        values = {
            "Index": "1",
            "Name": "Mewtwo",
            "Form": "",
            "Pokemon Number": "150",
            "Gender": "",
            "CP": "3500",
            "HP": "180",
            "Atk IV": "15",
            "Def IV": "14",
            "Sta IV": "15",
            "IV Avg": "97.8",
            "Level Min": "37",
            "Level Max": "37",
            "Quick Move": "Confusion",
            "Charge Move": "Shadow Ball",
            "Charge Move 2": "",
            "Scan Date": "2026-07-01",
            "Original Scan Date": "2026-06-01",
            "Catch Date": "2022-06-18",
            "Weight": "116.01",
            "Height": "1.95",
            "Lucky": "0",
            "Shadow/Purified": "0",
            "Favorite": "1",
            "Dust": "5000",
            "Marked for PvP use": "0",
        }
        values.update(overrides)
        return values

    def normalized(self, rows: list[dict[str, str]]) -> list[dict]:
        return [
            build_site.normalize_row(row, number)
            for number, row in enumerate(rows, start=2)
        ]

    def process(self, rows: list[dict[str, str]]):
        return process_longitudinal_collection(
            rows,
            self.normalized(rows),
            source_filename="shared-text-2026-08-16 08_00_00.000.csv",
            reference_date=date(2026, 8, 16),
        )

    def test_existing_same_state_duplicate_collapse_stays_exact(self) -> None:
        rows = [self.row(Index="10"), self.row(Index="11")]
        records, report, _ = self.process(rows)
        self.assertEqual(len(records), 1)
        self.assertEqual(report["automatic_group_count"], 1)
        self.assertEqual(report["longitudinal_group_count"], 0)
        self.assertEqual(report["duplicates_collapsed"], 1)

    def test_powerups_collapse_to_newest_current_state_with_history(self) -> None:
        rows = [
            self.row(
                Index="20",
                CP="3500",
                HP="180",
                **{
                    "Level Min": "37",
                    "Level Max": "37",
                    "Scan Date": "2026-07-01",
                    "Original Scan Date": "2026-06-01",
                },
            ),
            self.row(
                Index="21",
                CP="3575",
                HP="182",
                **{
                    "Level Min": "38",
                    "Level Max": "38",
                    "Scan Date": "2026-07-10",
                    "Original Scan Date": "2026-06-10",
                },
            ),
            self.row(
                Index="22",
                CP="4012",
                HP="190",
                **{
                    "Level Min": "42",
                    "Level Max": "42",
                    "Scan Date": "2026-08-01",
                    "Original Scan Date": "2026-07-20",
                },
            ),
        ]
        records, report, _ = self.process(rows)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["cp"], 4012)
        self.assertEqual(records[0]["level"]["minimum"], 42.0)
        self.assertEqual(report["longitudinal_group_count"], 1)
        group = report["longitudinal_groups"][0]
        self.assertEqual(group["observation_count"], 3)
        self.assertEqual(group["source_scan_count"], 3)
        self.assertRegex(group["entity_id"], r"^entity_[0-9a-f]{20}$")
        self.assertEqual(
            [item["state"]["cp"] for item in group["observations"]],
            [3500, 3575, 4012],
        )

    def test_move_change_is_an_observation_not_an_identity_break(self) -> None:
        rows = [
            self.row(
                Index="30",
                **{"Scan Date": "2026-07-01", "Charge Move": "Shadow Ball"},
            ),
            self.row(
                Index="31",
                **{
                    "Scan Date": "2026-08-01",
                    "Original Scan Date": "2026-07-15",
                    "Charge Move": "Psystrike",
                },
            ),
        ]
        records, report, _ = self.process(rows)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["moves"]["charged"], "Psystrike")
        self.assertEqual(report["longitudinal_groups"][0]["observation_count"], 2)

    def test_current_exact_record_identity_is_preserved(self) -> None:
        rows = [
            self.row(Index="32", CP="3500", **{"Scan Date": "2026-07-01"}),
            self.row(
                Index="33",
                CP="4012",
                **{
                    "Level Min": "42",
                    "Level Max": "42",
                    "Scan Date": "2026-08-01",
                    "Original Scan Date": "2026-07-20",
                },
            ),
        ]
        exact_records, _, _ = reconcile_records(
            rows,
            self.normalized(rows),
            source_filename="shared-text-2026-08-16 08_00_00.000.csv",
        )
        expected = next(record for record in exact_records if record["cp"] == 4012)
        records, report, _ = self.process(rows)
        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0]["identity"]["record_id"],
            expected["identity"]["record_id"],
        )
        self.assertEqual(
            records[0]["identity"]["record_fingerprint"],
            expected["identity"]["record_fingerprint"],
        )
        self.assertEqual(
            report["longitudinal_groups"][0]["canonical_record_id"],
            expected["identity"]["record_id"],
        )

    def test_same_species_and_exact_ivs_do_not_merge_with_conflicting_stable_data(self) -> None:
        rows = [
            self.row(
                Index="40",
                Weight="116.01",
                Height="1.95",
                **{"Catch Date": "2022-06-18", "Original Scan Date": "2026-06-01"},
            ),
            self.row(
                Index="41",
                Weight="119.50",
                Height="2.03",
                **{"Catch Date": "2022-06-19", "Original Scan Date": "2026-06-02"},
            ),
        ]
        records, report, _ = self.process(rows)
        self.assertEqual(len(records), 2)
        self.assertEqual(report["longitudinal_group_count"], 0)
        self.assertEqual(report["longitudinal_candidate_count"], 0)

    def test_missing_identity_metadata_remains_unmerged(self) -> None:
        rows = [
            self.row(
                Index="50",
                **{"Catch Date": "", "Original Scan Date": "", "Scan Date": "2026-07-01"},
            ),
            self.row(
                Index="51",
                CP="3600",
                **{
                    "Level Min": "38",
                    "Level Max": "38",
                    "Catch Date": "",
                    "Original Scan Date": "",
                    "Scan Date": "2026-08-01",
                },
            ),
        ]
        records, report, _ = self.process(rows)
        self.assertEqual(len(records), 2)
        self.assertEqual(report["longitudinal_group_count"], 0)
        self.assertEqual(report["longitudinal_candidate_count"], 1)
        self.assertEqual(
            report["longitudinal_candidates"][0]["matched_corroborators"],
            ["matching non-empty weight and height"],
        )

    def test_shadow_to_purified_transition_is_never_guessed(self) -> None:
        rows = [
            self.row(
                Index="60",
                **{"Shadow/Purified": "1", "Scan Date": "2026-07-01"},
            ),
            self.row(
                Index="61",
                CP="3900",
                **{
                    "Shadow/Purified": "2",
                    "Level Min": "40",
                    "Level Max": "40",
                    "Scan Date": "2026-08-01",
                },
            ),
        ]
        records, report, _ = self.process(rows)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["status"]["shadow_purified"], "shadow")
        self.assertEqual(records[1]["status"]["shadow_purified"], "purified")
        self.assertEqual(report["longitudinal_group_count"], 0)
        self.assertEqual(report["longitudinal_candidate_count"], 0)

    def test_single_corroborator_is_reported_but_preserved_as_separate(self) -> None:
        rows = [
            self.row(
                Index="70",
                Weight="",
                Height="",
                **{"Scan Date": "2026-07-01", "Original Scan Date": "2026-06-01"},
            ),
            self.row(
                Index="71",
                CP="3600",
                Weight="",
                Height="",
                **{
                    "Level Min": "38",
                    "Level Max": "38",
                    "Scan Date": "2026-08-01",
                    "Original Scan Date": "2026-07-01",
                },
            ),
        ]
        records, report, _ = self.process(rows)
        self.assertEqual(len(records), 2)
        self.assertEqual(report["longitudinal_group_count"], 0)
        self.assertEqual(report["longitudinal_candidate_count"], 1)
        candidate = report["longitudinal_candidates"][0]
        self.assertEqual(candidate["confidence"], "ambiguous")
        self.assertEqual(candidate["matched_corroborator_count"], 1)
        self.assertEqual(candidate["required_corroborator_count"], 2)
        self.assertEqual(len(candidate["record_ids"]), 2)
        self.assertFalse(
            report["policy"]["longitudinal"]["species_and_ivs_alone_are_sufficient"]
        )

    def test_complete_link_rule_prevents_transitive_identity_chain(self) -> None:
        rows = [
            self.row(
                Index="72",
                Weight="116.01",
                Height="1.95",
                **{"Original Scan Date": "2026-05-01", "Scan Date": "2026-07-01"},
            ),
            self.row(
                Index="73",
                CP="3600",
                Weight="116.01",
                Height="1.95",
                **{
                    "Level Min": "38",
                    "Level Max": "38",
                    "Original Scan Date": "2026-05-02",
                    "Scan Date": "2026-07-10",
                },
            ),
            self.row(
                Index="74",
                CP="3700",
                Weight="",
                Height="",
                **{
                    "Level Min": "39",
                    "Level Max": "39",
                    "Original Scan Date": "2026-05-02",
                    "Scan Date": "2026-07-20",
                },
            ),
        ]
        records, report, _ = self.process(rows)
        self.assertEqual(len(records), 2)
        self.assertEqual(report["longitudinal_group_count"], 1)
        self.assertEqual(report["longitudinal_groups"][0]["observation_count"], 2)
        self.assertGreaterEqual(report["longitudinal_candidate_count"], 1)
        self.assertEqual(
            report["policy"]["longitudinal"]["group_rule"],
            "complete-link pairwise evidence; transitive identity inference is forbidden",
        )

    def test_distinct_strong_groups_get_distinct_entity_ids_when_original_scan_differs(self) -> None:
        rows = [
            self.row(
                Index="75",
                CP="3500",
                Weight="",
                Height="",
                **{"Original Scan Date": "2026-05-01", "Scan Date": "2026-07-01"},
            ),
            self.row(
                Index="76",
                CP="3600",
                Weight="",
                Height="",
                **{
                    "Level Min": "38",
                    "Level Max": "38",
                    "Original Scan Date": "2026-05-01",
                    "Scan Date": "2026-07-10",
                },
            ),
            self.row(
                Index="77",
                CP="3700",
                Weight="",
                Height="",
                **{"Original Scan Date": "2026-05-02", "Scan Date": "2026-07-02"},
            ),
            self.row(
                Index="78",
                CP="3800",
                Weight="",
                Height="",
                **{
                    "Level Min": "39",
                    "Level Max": "39",
                    "Original Scan Date": "2026-05-02",
                    "Scan Date": "2026-07-11",
                },
            ),
        ]
        records, report, _ = self.process(rows)
        self.assertEqual(len(records), 2)
        self.assertEqual(report["longitudinal_group_count"], 2)
        entity_ids = [group["entity_id"] for group in report["longitudinal_groups"]]
        self.assertEqual(len(set(entity_ids)), 2)
        bases = [
            group["identity_basis"]["original_scan"]
            for group in report["longitudinal_groups"]
        ]
        self.assertEqual(set(bases), {"2026-05-01", "2026-05-02"})

    def test_structural_mewtwo_regression_fixture_collapses_powerup_history(self) -> None:
        rows = [
            self.row(
                Index="80",
                CP="3500",
                **{
                    "Level Min": "37",
                    "Level Max": "37",
                    "Scan Date": "2026-06-20",
                    "Original Scan Date": "2026-06-20",
                },
            ),
            self.row(
                Index="81",
                CP="3575",
                **{
                    "Level Min": "38",
                    "Level Max": "38",
                    "Scan Date": "2026-07-01",
                    "Original Scan Date": "2026-07-01",
                },
            ),
            self.row(
                Index="82",
                CP="3610",
                **{
                    "Level Min": "38.5",
                    "Level Max": "38.5",
                    "Scan Date": "2026-07-05",
                    "Original Scan Date": "2026-07-05",
                },
            ),
            self.row(
                Index="83",
                CP="4012",
                **{
                    "Level Min": "42",
                    "Level Max": "42",
                    "Scan Date": "2026-08-01",
                    "Original Scan Date": "2026-08-01",
                },
            ),
        ]
        records, report, row_map = self.process(rows)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["level"]["minimum"], 42.0)
        self.assertEqual(report["normalized_record_count"], 1)
        self.assertEqual(report["duplicates_collapsed"], 3)
        self.assertEqual(report["longitudinal_observations_collapsed"], 3)
        self.assertEqual(report["longitudinal_candidate_count"], 0)
        self.assertEqual(len(set(row_map.values())), 1)


if __name__ == "__main__":
    unittest.main()
