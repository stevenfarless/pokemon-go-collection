from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentationSyncTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_readme_exposes_post_roadmap_surfaces(self) -> None:
        readme = self.read("README.md")
        for required in (
            "/insights.html",
            "/tools.html",
            "/data/llm-bootstrap.json",
            "/data/pokemon-index.json",
            "/data/recommendations/",
            "/data/candidates/",
            "/data/investments/",
            "/data/reasoning/",
            "/data/external/snapshots/",
            "/api/v1/",
            "identity.record_id",
            "browser-local enrichment",
            "Export all local data",
            "production smoke verification",
        ):
            self.assertIn(required, readme)
        self.assertIn("unavailable", readme)

    def test_static_companion_uses_canonical_local_identity(self) -> None:
        document = self.read("docs/static-companion-features.md")
        self.assertIn("identity.record_id", document)
        self.assertIn("Ambiguous matches remain unresolved", document)
        self.assertIn("Browser-local notes and review labels", document)
        self.assertIn("Browser-local enrichment", document)
        self.assertIn("Unified local-data backup", document)
        self.assertIn("Production deployment verification", document)
        self.assertNotIn("No note or destructive decision is attached to that derived identity", document)

    def test_external_current_data_documents_real_reviewed_production_adapters(self) -> None:
        document = self.read("docs/external-game-data.md")
        self.assertIn("Current production status", document)
        self.assertIn("external/providers/official-events.json", document)
        self.assertIn("external/providers/official-raids.json", document)
        self.assertIn("automated_source_scraping: false", document)
        self.assertIn("last-known-good", document)
        self.assertIn("stale", document)
        self.assertIn("expired", document)
        self.assertNotIn("Issue #95 tracks the first production adapters", document)

    def test_core_docs_name_final_resource_boundaries(self) -> None:
        contracts = self.read("docs/data-contracts.md")
        planning = self.read("docs/planning-tools.md")
        api = self.read("docs/public-data-api.md")
        architecture = self.read("docs/architecture.md")

        for required in ("data/recommendations/", "data/candidates/", "data/investments/", "data/reasoning/"):
            self.assertIn(required, contracts)
            self.assertIn(required, api)

        self.assertIn("Browser-local notes and review labels", planning)
        self.assertIn("Freshness-gated event preparation", planning)
        self.assertIn("/tools.html", architecture)
        self.assertIn("Browser-local user state", architecture)


if __name__ == "__main__":
    unittest.main()
