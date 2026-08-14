from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import planning_publish


class PostRoadmapNavigationTests(unittest.TestCase):
    def test_patch_human_navigation_cross_links_collection_and_insights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "index.html").write_text(
                '<nav><a href="insights.html">Insights</a></nav>', encoding="utf-8"
            )
            (output_dir / "404.html").write_text(
                '<nav><a href="insights.html">Insights</a></nav>', encoding="utf-8"
            )
            (output_dir / "insights.html").write_text(
                '<nav><a href="./">Collection</a><a href="summary.md">Summary</a></nav>',
                encoding="utf-8",
            )

            planning_publish._patch_human_navigation(output_dir)

            for filename in ("index.html", "404.html", "insights.html"):
                source = (output_dir / filename).read_text(encoding="utf-8")
                self.assertIn('href="tools.html">Tools</a>', source)
                self.assertEqual(source.count('href="tools.html"'), 1)

            insights = (output_dir / "insights.html").read_text(encoding="utf-8")
            self.assertIn('href="./">Collection</a>', insights)

    def test_patch_human_navigation_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            for filename, source in {
                "index.html": '<a href="insights.html">Insights</a>',
                "404.html": '<a href="insights.html">Insights</a>',
                "insights.html": '<a href="./">Collection</a>',
            }.items():
                (output_dir / filename).write_text(source, encoding="utf-8")

            planning_publish._patch_human_navigation(output_dir)
            planning_publish._patch_human_navigation(output_dir)

            for filename in ("index.html", "404.html", "insights.html"):
                source = (output_dir / filename).read_text(encoding="utf-8")
                self.assertEqual(source.count('href="tools.html"'), 1)


if __name__ == "__main__":
    unittest.main()
