from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts import knowledge_publish, lab_asset_pipeline


ROOT = Path(__file__).resolve().parents[1]


class GlossaryIntegrationTests(unittest.TestCase):
    def test_glossary_is_published_with_versioned_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            knowledge_publish.publish_repository_knowledge(ROOT, output)
            published = output / "data" / "knowledge" / "glossary.json"
            self.assertTrue(published.is_file())
            expected = json.loads((ROOT / "knowledge" / "glossary.json").read_text(encoding="utf-8"))
            actual = json.loads(published.read_text(encoding="utf-8"))
            self.assertEqual(actual, expected)

    def test_glossary_asset_is_hashed_registered_and_injected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "assets").mkdir(parents=True)
            (output / "index.html").write_text("<html><body><main>Collection</main></body></html>", encoding="utf-8")
            manifest = {"assets": {}, "canonical_pipeline": {"style_sources": [], "script_sources": []}}
            lab_asset_pipeline.prepare(ROOT, output, manifest)
            asset = manifest["assets"]["glossary_experience"]
            self.assertRegex(asset, r"^assets/glossary-experience\.[0-9a-f]{12}\.js$")
            self.assertTrue((output / asset).is_file())
            html = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn(f'src="{asset}"', html)
            self.assertIn("data-glossary-experience", html)
            self.assertIn("site/glossary-experience.js", manifest["canonical_pipeline"]["script_sources"])
            self.assertTrue(re.fullmatch(lab_asset_pipeline.LAB_ASSET_PATTERNS["glossary_experience"], asset))


if __name__ == "__main__":
    unittest.main()
