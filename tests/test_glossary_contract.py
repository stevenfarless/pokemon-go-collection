from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GLOSSARY = ROOT / "knowledge" / "glossary.json"


class GlossaryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(GLOSSARY.read_text(encoding="utf-8"))
        cls.entries = cls.payload["entries"]
        cls.by_id = {entry["id"]: entry for entry in cls.entries}

    def test_entries_are_unique_and_source_backed(self) -> None:
        self.assertEqual(len(self.by_id), len(self.entries))
        self.assertGreaterEqual(len(self.entries), 35)
        for entry in self.entries:
            self.assertTrue(entry["term"].strip())
            self.assertTrue(entry["definition"].strip())
            self.assertTrue(entry["why_it_matters"].strip())
            self.assertTrue(entry["classification"].strip())
            self.assertTrue(entry["source_resource"].startswith("data/"))

    def test_iv_percentage_and_pvp_rank_remain_distinct(self) -> None:
        iv = self.by_id["iv-percent"]
        pvp = self.by_id["pvp-rank"]
        self.assertIn("three appraisal IVs", iv["definition"])
        self.assertIn("league CP cap", pvp["definition"])
        self.assertIn("rather than a current-meta ranking", pvp["definition"])
        self.assertNotEqual(iv["definition"], pvp["definition"])

    def test_changeable_mechanics_use_reviewed_mechanics_registry(self) -> None:
        current_ids = {
            "shadow-bonus",
            "purification",
            "frustration",
            "elite-tm",
            "mega-level",
            "super-max-level",
            "primal",
            "dynamax",
            "gigantamax",
            "max-moves",
            "max-particles",
            "hyper-training",
            "bottle-cap",
            "fusion",
            "adventure-effects",
        }
        for entry_id in current_ids:
            entry = self.by_id[entry_id]
            self.assertEqual(entry["classification"], "current-mechanic")
            self.assertEqual(entry["source_resource"], "data/mechanics/index.json")

    def test_evidence_terms_use_shared_evidence_contract(self) -> None:
        for entry_id in {"source-authority", "freshness", "simulation", "uncertainty"}:
            self.assertEqual(self.by_id[entry_id]["source_resource"], "data/evidence-contract.json")


if __name__ == "__main__":
    unittest.main()
