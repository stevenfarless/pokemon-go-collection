from __future__ import annotations

import math
import unittest
from pathlib import Path

from scripts.knowledge_validation import KnowledgeBase, augment_scan_quality, load_repository_knowledge
from scripts.sync_knowledge import build_snapshot, normalize_form


class KnowledgeValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cpm = 0.59740000963211
        self.payload = {
            "dataset_version": "fixture-1",
            "classification": "Verified community data",
            "source": {"name": "fixture", "commit": "a" * 40},
            "mechanics": {
                "cp_multiplier_levels": [
                    {"level": 20.0, "multiplier": self.cpm},
                    {"level": 20.5, "multiplier": 0.604823657502073},
                ]
            },
            "entries": [
                {
                    "dex": 1,
                    "species_id": "bulbasaur",
                    "display_name": "Bulbasaur",
                    "base_name": "Bulbasaur",
                    "form_key": "normal",
                    "form_aliases": ["", "none", "normal"],
                    "base_stats": {"attack": 118, "defense": 111, "stamina": 128},
                    "transformation": {"kind": None},
                },
                {
                    "dex": 26,
                    "species_id": "raichu_alolan",
                    "display_name": "Raichu (Alolan)",
                    "base_name": "Raichu",
                    "form_key": "alola",
                    "form_aliases": ["alola", "alolan"],
                    "base_stats": {"attack": 201, "defense": 154, "stamina": 155},
                    "transformation": {"kind": None},
                },
            ],
        }
        self.knowledge = KnowledgeBase(self.payload)

    def _record(self, *, cp: int | None = None, hp: int | None = None, form=None, dex: int = 1) -> dict:
        ivs = {"attack": 10, "defense": 10, "stamina": 10}
        stats = {"attack": 118, "defense": 111, "stamina": 128}
        expected_cp = max(
            10,
            math.floor(
                (stats["attack"] + 10)
                * math.sqrt(stats["defense"] + 10)
                * math.sqrt(stats["stamina"] + 10)
                * self.cpm * self.cpm
                / 10
            ),
        )
        expected_hp = max(10, math.floor((stats["stamina"] + 10) * self.cpm))
        return {
            "pokemon_number": dex,
            "name": "Bulbasaur" if dex == 1 else "Raichu",
            "form": form,
            "cp": expected_cp if cp is None else cp,
            "hp": expected_hp if hp is None else hp,
            "ivs": ivs,
            "level": {"minimum": 20.0, "maximum": 20.0},
            "identity": {"record_id": "pgc_0123456789abcdefabcd"},
            "provenance": {"source_rows": [2], "source_indices": [1]},
        }

    def _report(self) -> dict:
        return {
            "summary": {},
            "coverage": {},
            "findings": [],
        }

    def test_regional_form_normalization_joins_adjective_and_region_names(self) -> None:
        self.assertEqual(normalize_form("Alolan"), "alola")
        self.assertEqual(normalize_form("Alola"), "alola")
        match = self.knowledge.match(self._record(form="Alolan", dex=26))
        self.assertEqual(match.status, "matched")
        self.assertEqual(match.entry["species_id"], "raichu_alolan")

    def test_valid_cp_hp_level_combination_passes(self) -> None:
        record = self._record()
        match = self.knowledge.match(record)
        plausible, levels = self.knowledge.plausible_cp_hp(record, match.entry)
        self.assertTrue(plausible)
        self.assertEqual(levels[0]["level"], 20.0)
        report = augment_scan_quality(self._report(), [record], self.knowledge)
        self.assertNotIn("implausible_cp_hp_level", report["summary"]["reason_counts"])
        self.assertEqual(report["knowledge"]["plausibility_checked_count"], 1)

    def test_impossible_cp_hp_level_combination_requests_rescan(self) -> None:
        record = self._record(cp=9999)
        report = augment_scan_quality(self._report(), [record], self.knowledge)
        self.assertEqual(report["summary"]["reason_counts"]["implausible_cp_hp_level"], 1)
        finding = report["findings"][0]
        self.assertEqual(finding["suggested_action"], "rescan")
        self.assertEqual(finding["record_id"], record["identity"]["record_id"])

    def test_unknown_form_is_preserved_as_uncertainty(self) -> None:
        record = self._record(form="Unmapped Form")
        report = augment_scan_quality(self._report(), [record], self.knowledge)
        self.assertEqual(report["summary"]["reason_counts"]["unrecognized_species_form"], 1)
        self.assertEqual(report["findings"][0]["suggested_action"], "review")
        self.assertEqual(report["knowledge"]["matched_record_count"], 0)

    def test_missing_scan_inputs_skip_plausibility_instead_of_guessing(self) -> None:
        record = self._record()
        record["hp"] = None
        report = augment_scan_quality(self._report(), [record], self.knowledge)
        self.assertNotIn("implausible_cp_hp_level", report["summary"]["reason_counts"])
        self.assertEqual(report["knowledge"]["plausibility_skipped_count"], 1)

    def test_repository_snapshot_is_valid_pinned_and_substantial(self) -> None:
        root = Path(__file__).resolve().parents[1]
        knowledge = load_repository_knowledge(root)
        self.assertEqual(knowledge.source["commit"], "5e1e3d971369a47aaf3e7247f50710d80205d570")
        self.assertEqual(knowledge.classification, "Verified community data")
        self.assertGreater(len(knowledge.entries), 1000)
        self.assertIn(1, knowledge.by_dex)

    def test_snapshot_builder_excludes_shadow_duplicate_rows(self) -> None:
        lock = {
            "dataset_version": "fixture",
            "classification": "Verified community data",
            "source": {
                "name": "PvPoke",
                "repository": "pvpoke/pvpoke",
                "commit": "a" * 40,
                "commit_date": "2026-01-01",
                "license": "MIT",
                "pokemon_path": "pokemon.json",
                "mechanics_path": "Pokemon.js",
            },
        }
        source = [
            {
                "dex": 1,
                "speciesName": "Bulbasaur",
                "speciesId": "bulbasaur",
                "baseStats": {"atk": 118, "def": 111, "hp": 128},
                "types": ["grass", "poison"],
                "tags": ["shadoweligible"],
                "fastMoves": ["TACKLE"],
                "chargedMoves": ["SEED_BOMB"],
                "thirdMoveCost": 10000,
                "family": {"id": "FAMILY_BULBASAUR"},
            },
            {
                "dex": 1,
                "speciesName": "Bulbasaur (Shadow)",
                "speciesId": "bulbasaur_shadow",
                "baseStats": {"atk": 118, "def": 111, "hp": 128},
                "types": ["grass", "poison"],
                "tags": ["shadow"],
                "fastMoves": ["TACKLE"],
                "chargedMoves": ["SEED_BOMB"],
            },
        ]
        mechanics = "var cpms = [" + ",".join(str(0.1 + index * 0.001) for index in range(109)) + "];"
        snapshot, index = build_snapshot(lock, source, mechanics)
        self.assertEqual(index["entry_count"], 1)
        self.assertEqual(snapshot["entries"][0]["species_id"], "bulbasaur")
        self.assertIsNone(snapshot["entries"][0]["second_charged_move_cost"]["candy"])
        self.assertIsNone(snapshot["entries"][0]["dynamax_eligibility"])


if __name__ == "__main__":
    unittest.main()
