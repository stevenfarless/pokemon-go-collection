from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_dashboard import build
from scripts.validate_generated import validate_generated


class CanonicalDashboardBuildTests(unittest.TestCase):
    def test_canonical_build_publishes_dashboard_health_insights_shards_and_knowledge(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dist"
            manifest = build(repository_root, output)
            validate_generated(output)

            self.assertEqual(manifest["generator"], "scripts/build_dashboard.py")
            self.assertEqual(
                manifest["canonical_pipeline"]["command"],
                "python scripts/build_dashboard.py",
            )
            self.assertEqual(
                manifest["canonical_pipeline"]["html_templates"],
                ["site/index.html", "site/insights.html"],
            )
            self.assertRegex(
                manifest["assets"]["dashboard"],
                r"^assets/dashboard\.[0-9a-f]{12}\.js$",
            )
            self.assertRegex(
                manifest["assets"]["dashboard_styles"],
                r"^assets/dashboard\.[0-9a-f]{12}\.css$",
            )
            self.assertRegex(
                manifest["assets"]["insights"],
                r"^assets/insights\.[0-9a-f]{12}\.js$",
            )

            for resource in (
                "index.html",
                "404.html",
                "insights.html",
                "data/data-health.json",
                "data/data-health.schema.json",
                "data/insights.json",
                "data/insights.schema.json",
                "data/pokemon-index.json",
                "data/pokemon-shard.schema.json",
                "data/scan-quality-report.json",
                "data/knowledge/pokemon-go.json",
                "data/knowledge/pokemon-go.schema.json",
                "data/knowledge/species-index.json",
                "data/knowledge/species-index.schema.json",
                "data/knowledge/PVPOKE-LICENSE.txt",
            ):
                self.assertTrue((output / resource).is_file(), resource)

            index = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("Fuddledumpy’s Pokémon GO Collection", index)
            self.assertIn('id="copy-friend-code"', index)
            self.assertIn('data-summary-preset="hundos"', index)
            self.assertIn('data-column-toggle="moves"', index)
            self.assertIn('id="data-health-panel"', index)
            self.assertIn("name:pikachu", index)
            self.assertIn(manifest["assets"]["dashboard"], index)
            self.assertIn(manifest["assets"]["dashboard_styles"], index)
            self.assertNotIn("{{GENDER_OPTIONS}}", index)
            self.assertNotIn("data-summary-presets", index)
            self.assertNotIn("data-usability", index)

            insights_page = (output / "insights.html").read_text(encoding="utf-8")
            self.assertIn(manifest["assets"]["insights"], insights_page)
            self.assertIn(manifest["assets"]["dashboard_styles"], insights_page)

            health = json.loads(
                (output / "data" / "data-health.json").read_text(encoding="utf-8")
            )
            insights = json.loads(
                (output / "data" / "insights.json").read_text(encoding="utf-8")
            )
            scan_quality = json.loads(
                (output / "data" / "scan-quality-report.json").read_text(encoding="utf-8")
            )
            shard_index = json.loads(
                (output / "data" / "pokemon-index.json").read_text(encoding="utf-8")
            )
            knowledge = json.loads(
                (output / "data" / "knowledge" / "pokemon-go.json").read_text(encoding="utf-8")
            )
            knowledge_index = json.loads(
                (output / "data" / "knowledge" / "species-index.json").read_text(encoding="utf-8")
            )

            self.assertEqual(health["counts"]["records"], manifest["pokemon_count"])
            self.assertEqual(insights["source"]["record_count"], manifest["pokemon_count"])
            self.assertTrue(insights["top_duplicate_groups"])
            self.assertEqual(len(insights["pvp"]), 3)
            self.assertEqual(shard_index["normalized_record_count"], manifest["pokemon_count"])
            self.assertGreater(shard_index["shard_count"], 0)
            self.assertEqual(
                scan_quality["knowledge"]["dataset_version"],
                knowledge["dataset_version"],
            )
            self.assertEqual(
                scan_quality["knowledge"]["source_commit"],
                knowledge["source"]["commit"],
            )
            self.assertEqual(knowledge_index["entry_count"], len(knowledge["entries"]))
            self.assertIn("pokemon_go_knowledge", manifest["resources"])
            self.assertIn("pokemon_go_species_index", manifest["resources"])
            self.assertTrue(any(name.startswith("pokemon_shard_") for name in manifest["resources"]))


if __name__ == "__main__":
    unittest.main()
