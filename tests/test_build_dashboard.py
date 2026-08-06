from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_dashboard import _replace_html


class DashboardShortcutBuildTests(unittest.TestCase):
    def test_summary_section_is_replaced_with_clickable_shortcuts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            source = """<html><head></head><body>
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


if __name__ == "__main__":
    unittest.main()
