from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.source_registry import (
    load_registry,
    publish_source_registry,
    scan_runtime_external_assets,
    validate_registry,
)


class SourceRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.registry = load_registry(cls.root)

    def test_repository_registry_validates(self) -> None:
        validate_registry(self.registry, self.root)

    def test_production_provider_without_registry_owner_fails_closed(self) -> None:
        candidate = copy.deepcopy(self.registry)
        candidate["sources"] = [
            source for source in candidate["sources"] if source["id"] != "pokemon-go-official-announcements"
        ]
        with self.assertRaisesRegex(ValueError, "requires exactly one active reviewed source registry entry"):
            validate_registry(candidate, self.root)

    def test_orphaned_active_provider_claim_fails_closed(self) -> None:
        candidate = copy.deepcopy(self.registry)
        official = next(source for source in candidate["sources"] if source["id"] == "pokemon-go-official-announcements")
        official["production"]["provider_ids"].append("removed-provider")
        with self.assertRaisesRegex(ValueError, "has no production provider file"):
            validate_registry(candidate, self.root)

    def test_pvpoke_source_lock_must_match_reviewed_commit(self) -> None:
        candidate = copy.deepcopy(self.registry)
        pvpoke = next(source for source in candidate["sources"] if source["id"] == "pvpoke-stable-knowledge")
        pvpoke["source"]["exact_version"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "source-lock commit differs"):
            validate_registry(candidate, self.root)

    def test_python_dependency_change_requires_registry_review(self) -> None:
        candidate = copy.deepcopy(self.registry)
        python_source = next(
            source for source in candidate["sources"] if source["id"] == "python-build-test-dependencies"
        )
        python_source["packages"][0]["version"] = "0.0.0"
        with self.assertRaisesRegex(ValueError, "differs from the reviewed Python dependency inventory"):
            validate_registry(candidate, self.root)

    def test_remote_runtime_assets_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site = root / "site"
            site.mkdir()
            (site / "index.html").write_text(
                '<link rel="stylesheet" href="https://example.invalid/style.css">',
                encoding="utf-8",
            )
            findings = scan_runtime_external_assets(root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["path"], "site/index.html")

    def test_publication_uses_same_registry_for_machine_index_and_credits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "index.html").write_text(
                "<!doctype html><html><body><footer></footer></body></html>",
                encoding="utf-8",
            )
            provenance = publish_source_registry(
                self.root,
                output,
                {
                    "build_id": "0123456789ab",
                    "generated_at_utc": "2026-08-29T12:00:00Z",
                },
            )

            published = json.loads((output / "data" / "provenance" / "index.json").read_text(encoding="utf-8"))
            credits = (output / "credits.html").read_text(encoding="utf-8")
            index = (output / "index.html").read_text(encoding="utf-8")

            self.assertEqual(published, provenance)
            self.assertEqual(published["source_count"], len(self.registry["sources"]))
            self.assertEqual(published["runtime_external_asset_audit"]["status"], "clear")
            self.assertGreater(published["dependencies"]["npm_lockfile"]["package_count"], 0)
            self.assertEqual(published["dependencies"]["python_direct"]["package_count"], 3)
            self.assertIn("PvPoke", credits)
            self.assertIn("Pokémon GO official announcements", credits)
            self.assertIn("data/provenance/index.json", credits)
            self.assertIn('href="credits.html"', index)


if __name__ == "__main__":
    unittest.main()
