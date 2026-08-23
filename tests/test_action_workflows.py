from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts import action_workflows, build_site, schema_contracts, semantic_validation


class ActionWorkflowTests(unittest.TestCase):
    def manifest(self) -> dict:
        return {
            "build_id": "123456789abc",
            "generated_at_utc": "2026-08-23T08:30:00Z",
            "export_timestamp": "2026-08-23T08:00:00.000",
        }

    def record(self, record_id: str, rank: float | None = 95.0, *, favorite: bool = False) -> dict:
        return {
            "pokemon_number": 25,
            "name": "Pikachu",
            "form": None,
            "gender": "Male",
            "cp": 500,
            "hp": 70,
            "ivs": {"attack": 10, "defense": 12, "stamina": 13, "average_percent": 77.8, "total": 35, "is_hundo": False, "is_nundo": False},
            "level": {"minimum": 20.0, "maximum": 20.0},
            "moves": {"fast": "Thunder Shock", "charged": "Wild Charge", "charged_second": None},
            "dates": {"scan": "2026-08-23", "original_scan": "2026-08-01", "catch": "2026-08-01"},
            "status": {"lucky": False, "shadow_purified": "normal", "favorite": favorite, "marked_for_pvp": False},
            "pvp": {
                "great": {"rank_percent": rank, "rank_number": 20, "stat_product": 99.0, "dust_cost": 10000, "candy_cost": 20},
                "ultra": {"rank_percent": None},
                "little": {"rank_percent": None},
            },
            "identity": {"record_id": record_id},
        }

    @staticmethod
    def write(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    def fixture_output(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp = tempfile.TemporaryDirectory()
        output = Path(temp.name)
        first = self.record("record-a", 90.0)
        second = self.record("record-b", 99.0, favorite=True)
        self.write(output / "data/pokemon.json", {"records": [first, second]})
        self.write(output / "data/recommendations/index.json", {"queues": [
            {"name": "rescan", "path": "data/recommendations/rescan.json"},
            {"name": "pvp-candidates", "path": "data/recommendations/pvp-candidates.json"},
            {"name": "duplicate-review", "path": "data/recommendations/duplicate-review.json"},
        ]})
        self.write(output / "data/recommendations/rescan.json", {"records": [{"record_id": "record-a", "reasons": ["missing_ivs"], "warnings": ["missing_ivs"]}]})
        self.write(output / "data/recommendations/pvp-candidates.json", {"records": [{"record_id": "record-b", "reasons": ["high_pvp_iv_percentile"]}]})
        self.write(output / "data/recommendations/duplicate-review.json", {"records": [{"record_id": "record-a", "reasons": ["owned_duplicate"]}, {"record_id": "record-b", "reasons": ["owned_duplicate"]}]})
        self.write(output / "data/scan-quality-report.json", {"findings": [{"record_id": "record-a", "reason_code": "missing_ivs", "severity": "warning", "suggested_action": "rescan"}]})
        self.write(output / "data/reasoning/records.json", {"records": [
            {"record_id": "record-a", "recommendations": [{"recommendation": "review_or_rescan_before_consequential_decision"}], "irreversible_actions_blocked": ["transfer", "evolve"]},
            {"record_id": "record-b", "recommendations": [], "irreversible_actions_blocked": []},
        ]})
        self.write(output / "data/investments/records.json", {"records": [{"record_id": "record-a"}, {"record_id": "record-b"}]})
        self.write(output / "data/collection-diff.json", {
            "from_build_id": "aaaaaaaaaaaa",
            "to_build_id": "123456789abc",
            "wording": "Removed means no longer present in the current normalized export; it does not by itself prove an in-game transfer.",
            "added": [],
            "removed": [{"record_id": "old-record", "pokemon_number": 1, "name": "Bulbasaur", "form": None, "cp": 100}],
            "changed": [],
            "ambiguous": [{"reason": "non_unique_fingerprint"}],
        })
        self.write(output / "data/history-index.json", {"snapshot_count": 2, "snapshots": [{"export_timestamp": "2026-08-22T01:00:00.000"}, {"export_timestamp": "2026-08-23T08:00:00.000"}]})
        self.write(output / "data/mechanics/index.json", {"reviewed_at": "2026-08-23", "sources": [], "domains": [{"id": "inventory-search", "label": "Inventory search", "status": "supported", "source_ids": [], "applicable_at": "2026-08-23"}]})
        self.write(output / "data/external/index.json", {"snapshots": []})
        return temp, output

    def test_decision_card_blocks_consequential_action_and_never_declares_safe_transfer(self) -> None:
        temp, output = self.fixture_output()
        with temp:
            _, payload = action_workflows.build_decisions(output, self.manifest())
            first = next(item for item in payload["cards"] if item["record_id"] == "record-a")
            self.assertEqual(first["status"], "blocked")
            self.assertIn("transfer", first["irreversible_actions_blocked"])
            self.assertIn("Scan Inbox", first["exact_next_step"]["label"])
            self.assertNotIn("safe to transfer", json.dumps(payload).lower())
            self.assertTrue(first["guidance_invariant"])
            self.assertIn("shiny", first["unknown_protection_classes"])

    def test_decision_card_surfaces_better_owned_copy_without_meta_claim(self) -> None:
        temp, output = self.fixture_output()
        with temp:
            _, payload = action_workflows.build_decisions(output, self.manifest())
            first = next(item for item in payload["cards"] if item["record_id"] == "record-a")
            self.assertEqual(first["better_owned_alternative"]["record_id"], "record-b")
            self.assertIn("not a current-meta ranking", first["better_owned_alternative"]["statement"])

    def test_timeline_keeps_conservative_removal_semantics_and_is_bounded(self) -> None:
        temp, output = self.fixture_output()
        with temp:
            payload = action_workflows.build_timeline(output, self.manifest())
            collection = payload["lanes"]["collection"]
            removed = next(item for item in collection["entries"] if item["kind"] == "removed-from-export")
            self.assertIn("does not prove an in-game transfer", removed["summary"])
            self.assertTrue(payload["bounded"])
            self.assertLessEqual(len(collection["entries"]), payload["max_items_per_lane"])
            self.assertEqual(payload["lanes"]["local-planning"]["status"], "browser-local")

    def test_action_packs_are_locators_not_blind_transfer_lists(self) -> None:
        temp, output = self.fixture_output()
        with temp:
            payload = action_workflows.build_action_packs(output, self.manifest())
            ids = {pack["id"] for pack in payload["packs"]}
            self.assertTrue({"duplicate-review", "rescan-incomplete", "pvp-party", "raid-max-party", "evolution-review", "evolve-current-move-window", "remove-frustration", "trade-review", "locate-exact"}.issubset(ids))
            self.assertIn("No current template is labeled a safe blind transfer list", payload["operator_contract"]["policy"])
            duplicate = next(pack for pack in payload["packs"] if pack["id"] == "duplicate-review")
            self.assertTrue(duplicate["manual_review_record_ids"])
            self.assertTrue(all(not batch["exact"] for batch in duplicate["batches"]))
            frustration = next(pack for pack in payload["packs"] if pack["id"] == "remove-frustration")
            self.assertEqual(frustration["status"], "unavailable")

    def test_preflight_contract_is_derived_from_production_validation_constants(self) -> None:
        payload = action_workflows.build_preflight_contract(self.manifest())
        self.assertEqual(payload["required_columns"], list(schema_contracts.CORE_COLUMNS))
        self.assertEqual(payload["integer_rules"]["Pokemon Number"]["minimum"], semantic_validation.INTEGER_RULES["Pokemon Number"][0])
        self.assertTrue(payload["integer_rules"]["Pokemon Number"]["required"])
        self.assertEqual(payload["number_rules"]["IV Avg"]["maximum"], 100)
        self.assertEqual(payload["privacy"], "Selected CSV bytes are parsed only in the browser and are never uploaded by the preflight code.")

    def test_all_workflow_schemas_are_valid_draft_2020_12(self) -> None:
        for schema in action_workflows.schemas().values():
            Draft202012Validator.check_schema(schema)

    def test_shared_preflight_fixtures_match_production_acceptance(self) -> None:
        fixture = json.loads((Path(__file__).parent / "fixtures" / "preflight-cases.json").read_text(encoding="utf-8"))
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                parsed_name = build_site.parse_export_filename(Path(case["filename"]))
                reader = csv.DictReader(io.StringIO(case["csv"]))
                fields = reader.fieldnames or []
                report = schema_contracts.analyze_source_columns(fields)
                accepted = parsed_name is not None and not report["missing_required_columns"]
                warnings = []
                if accepted:
                    try:
                        _, warnings = semantic_validation.validate_rows(fields, list(reader))
                    except (ValueError, semantic_validation.SemanticValidationError):
                        accepted = False
                self.assertEqual(accepted, case["accepted"])
                if case.get("unknown_columns"):
                    self.assertEqual(report["unknown_columns"], case["unknown_columns"])
                if case.get("warning_column") and accepted:
                    self.assertIn(case["warning_column"], {warning.column for warning in warnings})


if __name__ == "__main__":
    unittest.main()
