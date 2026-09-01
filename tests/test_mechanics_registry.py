import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts import check_mechanics_sources, mechanics_registry


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

    def test_source_fingerprint_ignores_page_chrome_outside_article(self):
        first = "<html><nav>Popular article A</nav><article><h1>Mechanic</h1><p>Same rule.</p></article><footer>One</footer></html>"
        second = "<html><nav>Popular article B</nav><article><h1>Mechanic</h1><p>Same rule.</p></article><footer>Two</footer></html>"
        self.assertEqual(
            check_mechanics_sources._fingerprint_html(first),
            check_mechanics_sources._fingerprint_html(second),
        )

    def test_source_fingerprint_detects_article_content_change(self):
        first = "<article><h1>Mechanic</h1><p>Cost: 5 Candy.</p></article>"
        second = "<article><h1>Mechanic</h1><p>Cost: 6 Candy.</p></article>"
        self.assertNotEqual(
            check_mechanics_sources._fingerprint_html(first),
            check_mechanics_sources._fingerprint_html(second),
        )

    def test_source_fingerprint_falls_back_to_main_then_document(self):
        with_main = "<html><nav>Changed shell</nav><main><p>Primary rule.</p></main></html>"
        main_only = "<main><p>Primary rule.</p></main>"
        self.assertEqual(
            check_mechanics_sources._fingerprint_html(with_main),
            check_mechanics_sources._fingerprint_html(main_only),
        )
        self.assertEqual(check_mechanics_sources._normalize_html("<p>Fallback rule.</p>"), "Fallback rule.")

    def test_source_fingerprint_version_migration_is_explicit(self):
        current = "a" * 64
        self.assertEqual(check_mechanics_sources._source_status(None, current, 1), "baseline-missing")
        self.assertEqual(check_mechanics_sources._source_status(current, current, 1), "baseline-algorithm-changed")
        self.assertEqual(check_mechanics_sources._source_status(current, current, 2), "unchanged")
        self.assertEqual(check_mechanics_sources._source_status(current, "b" * 64, 2), "changed")

    def test_reviewed_source_baselines_and_adventure_effects_url_are_current(self):
        state = json.loads((self.root / ".github" / "mechanics-source-state.json").read_text(encoding="utf-8"))
        sources = {item["id"]: item for item in self.source["sources"]}
        helpshift_sources = {source_id for source_id, item in sources.items() if "helpshift.com" in item["url"]}
        self.assertEqual(helpshift_sources, set(state["sources"]))
        for source_id in helpshift_sources:
            self.assertRegex(state["sources"][source_id]["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(state["sources"][source_id]["reviewed_at"], "2026-09-01")
        self.assertEqual(
            sources["wild-area-adventure-effects"]["url"],
            "https://pokemongo.com/news/origin-forme-adventure-effects-dialga-palkia",
        )
        self.assertEqual(
            sources["wild-area-adventure-effects"]["title"],
            "Origin Forme Dialga and Palkia Adventure Effects",
        )


if __name__ == "__main__":
    unittest.main()
