from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_dashboard import _replace_html


class DashboardShortcutBuildTests(unittest.TestCase):
    def test_summary_shortcuts_and_trainer_profile_are_added(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            source = """<html><head>
<meta name="description" content="Searchable Pokémon GO collection generated from the newest archived Poke Genie export.">
<title>Pokémon GO Collection</title>
</head><body>
<header class="site-header">
<div class="brand">
<h1>Pokémon GO Collection</h1>
<p>4,571 Pokémon from the latest Poke Genie export</p>
</div>
</header>
<section class="compact-stats" aria-label="Collection summary">
<span><strong id="total-count">4,571</strong> total</span>
</section>
<script defer src="assets/accessibility.old.js"></script>
</body></html>"""
            for filename in ("index.html", "404.html"):
                (output / filename).write_text(source, encoding="utf-8")

            _replace_html(
                output,
                "assets/accessibility.old.js",
                "assets/accessibility.new.js",
                4571,
            )

            generated = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn('data-summary-preset="all"', generated)
            self.assertIn('data-summary-preset="hundos"', generated)
            self.assertIn('data-summary-preset="max-cp"', generated)
            self.assertIn("4,571", generated)
            self.assertNotIn("{{POKEMON_COUNT}}", generated)
            self.assertIn("assets/accessibility.new.js", generated)
            self.assertIn("data-summary-presets", generated)

            self.assertIn(
                "<title>Fuddledumpy’s Pokémon GO Collection</title>",
                generated,
            )
            self.assertIn(
                "<h1>Fuddledumpy’s Pokémon GO Collection</h1>",
                generated,
            )
            self.assertIn("Friend Code:", generated)
            self.assertIn("2252 2231 2780", generated)
            self.assertIn('data-friend-code="225222312780"', generated)
            self.assertIn('id="copy-friend-code"', generated)
            self.assertIn('id="friend-code-status"', generated)
            self.assertIn('meta property="og:title"', generated)
            self.assertIn("Browse Fuddledumpy’s searchable Pokémon GO collection", generated)
            self.assertIn("data-trainer-profile", generated)
            self.assertIn("navigator.clipboard", generated)

            generated_404 = (output / "404.html").read_text(encoding="utf-8")
            self.assertIn("Fuddledumpy’s Pokémon GO Collection", generated_404)
            self.assertIn("2252 2231 2780", generated_404)


if __name__ == "__main__":
    unittest.main()
