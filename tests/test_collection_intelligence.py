from __future__ import annotations

import unittest

from scripts.collection_intelligence import build_data_health, build_insights


def record(
    name: str,
    dex: int,
    cp: int,
    *,
    form: str | None = None,
    complete: bool = True,
    scan: str | None = "2026-08-01",
    catch: str | None = "2026-08-05",
    great_rank: float | None = 99.0,
) -> dict:
    return {
        "name": name,
        "form": form,
        "pokemon_number": dex,
        "cp": cp,
        "hp": 100,
        "ivs": {
            "attack": 15 if complete else None,
            "defense": 14 if complete else None,
            "stamina": 13 if complete else None,
            "average_percent": 93.33 if complete else None,
            "total": 42 if complete else None,
            "is_hundo": False,
            "is_nundo": False,
        },
        "level": {"minimum": 30 if complete else None, "maximum": 30 if complete else None},
        "moves": {"fast": "Tackle" if complete else None, "charged": "Body Slam" if complete else None, "charged_second": None},
        "dates": {"scan": scan, "original_scan": scan, "catch": catch},
        "size": {"weight": None, "height": None},
        "status": {"lucky": False, "shadow_purified": "normal", "favorite": False, "marked_for_pvp": False},
        "dust": 5000,
        "pvp": {
            "great": {"rank_percent": great_rank, "rank_number": 10 if great_rank else None, "stat_product": 100, "dust_cost": 10000, "candy_cost": 25, "evolution_name": name, "evolution_form": form, "status": "normal"},
            "ultra": {"rank_percent": None, "rank_number": None, "stat_product": None, "dust_cost": None, "candy_cost": None, "evolution_name": None, "evolution_form": None, "status": None},
            "little": {"rank_percent": None, "rank_number": None, "stat_product": None, "dust_cost": None, "candy_cost": None, "evolution_name": None, "evolution_form": None, "status": None},
        },
    }


class CollectionIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            record("Bulbasaur", 1, 900),
            record("Bulbasaur", 1, 700, scan="2025-01-01"),
            record("Pikachu", 25, 500, complete=False, scan=None, great_rank=None),
        ]
        self.manifest = {
            "source_filename": "shared-text-2026-08-05 23_24_00.336.csv",
            "source_file": "exports/shared-text-2026-08-05 23_24_00.336.csv",
            "export_timestamp": "2026-08-05T23:24:00.336",
            "timestamp_basis": "Timestamp encoded in the filename; no timezone is asserted.",
            "generated_at_utc": "2026-08-06T12:00:00Z",
            "export_schema_version": "poke-genie-csv-v1",
            "schema_version": "1.0.0",
            "unknown_columns": [],
            "missing_optional_columns": [],
            "diagnostics": {"warning_count": 0, "error_count": 0},
        }

    def test_data_health_uses_documented_completeness_and_date_thresholds(self) -> None:
        health = build_data_health(self.records, self.manifest)
        self.assertEqual(health["counts"]["records"], 3)
        self.assertEqual(health["counts"]["incomplete_scans"], 1)
        self.assertEqual(health["counts"]["missing_ivs"], 1)
        self.assertEqual(health["counts"]["missing_levels"], 1)
        self.assertEqual(health["counts"]["missing_moves"], 1)
        self.assertEqual(health["counts"]["missing_scan_dates"], 1)
        self.assertEqual(health["counts"]["missing_selected_pvp"], 1)
        self.assertEqual(health["counts"]["stale_scans"], 1)
        self.assertIn("quality=missing-any", health["links"]["incomplete_scans"])

    def test_insights_group_duplicates_and_preserve_drill_down_links(self) -> None:
        summary = {
            "pokemon_count": 3,
            "distinct_species_forms": 2,
            "distinct_names": 2,
            "hundo_count": 0,
            "nundo_count": 0,
            "shadow_count": 0,
            "purified_count": 0,
            "lucky_count": 0,
            "favorite_count": 0,
            "highest_cp": 900,
            "most_common_names": [["Bulbasaur", 2], ["Pikachu", 1]],
            "most_common_forms": [["Unspecified", 3]],
            "pvp": {},
        }
        health = build_data_health(self.records, self.manifest)
        insights = build_insights(self.records, summary, self.manifest, health)
        self.assertEqual(insights["overview"]["duplicate_groups"], 1)
        self.assertEqual(insights["overview"]["single_copy_groups"], 1)
        self.assertEqual(insights["top_duplicate_groups"][0]["name"], "Bulbasaur")
        self.assertEqual(insights["top_duplicate_groups"][0]["count"], 2)
        self.assertIn("species=Bulbasaur", insights["top_duplicate_groups"][0]["href"])
        self.assertEqual(len(insights["pvp"]), 3)


if __name__ == "__main__":
    unittest.main()
