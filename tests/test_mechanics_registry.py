import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts import mechanics_registry


class MechanicsRegistryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.source = json.loads((self.root / "knowledge" / "mechanics-registry.json").read_text(encoding="utf-8"))

    def test_required_current_domains_have_explicit_states(self):
        domains = {item["id"]: item for item in self.source["domains"]}
        expected = {
            "inventory-search", "iv-appraisal-cp-levels", "evolution", "moves-tms", "shadow-purified",
            "mega-primal", "max-pokemon", "hyper-training", "fusion", "adventure-effects", "buddy",
            "raids", "pvp", "trading", "home-transfer",
        }
        self.assertTrue(expected.issubset(domains))
        self.assertTrue(all(domains[key]["status"] in mechanics_registry.STATUSES for key in expected))

    def test_published_registry_is_schema_valid_and_build_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "data").mkdir()
            payload = mechanics_registry.publish(self.root, output, {"build_id": "0123456789ab", "generated_at_utc": "2026-08-23T06:00:00Z"})
            Draft202012Validator(mechanics_registry.schema()).validate(payload)
            self.assertEqual(payload["build_id"], "0123456789ab")
            self.assertEqual(payload["coverage"]["total"], len(payload["domains"]))
            self.assertTrue((output / "mechanics-coverage.md").is_file())

    def test_change_detection_surfaces_actionable_source_details(self):
        workflow = (self.root / ".github" / "workflows" / "mechanics-change-detection.yml").read_text(encoding="utf-8")
        self.assertIn("mechanics-source-review.md", workflow)
        self.assertIn("Previous SHA-256", workflow)
        self.assertIn("Current SHA-256", workflow)
        self.assertIn("--body-file mechanics-source-review.md", workflow)
        self.assertIn("GITHUB_STEP_SUMMARY", workflow)

    def test_change_detection_runs_after_watched_source_configuration_changes(self):
        workflow = (self.root / ".github" / "workflows" / "mechanics-change-detection.yml").read_text(encoding="utf-8")
        self.assertIn("push:", workflow)
        self.assertIn("branches: [main]", workflow)
        for path in (
            ".github/mechanics-source-state.json",
            ".github/workflows/mechanics-change-detection.yml",
            "knowledge/mechanics-registry.json",
            "scripts/check_mechanics_sources.py",
        ):
            self.assertIn(f'- "{path}"', workflow)

    def test_reviewed_source_baselines_and_wild_area_url_are_current(self):
        state = json.loads((self.root / ".github" / "mechanics-source-state.json").read_text(encoding="utf-8"))
        sources = {item["id"]: item for item in self.source["sources"]}
        helpshift_sources = {source_id for source_id, item in sources.items() if "helpshift.com" in item["url"]}
        self.assertEqual(helpshift_sources, set(state["sources"]))
        for source_id in helpshift_sources:
            self.assertRegex(state["sources"][source_id]["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(state["sources"][source_id]["reviewed_at"], "2026-09-01")
        self.assertEqual(
            sources["wild-area-adventure-effects"]["url"],
            "https://gotour.pokemongolive.com/gowildarea/global/",
        )


if __name__ == "__main__":
    unittest.main()
