import re
import unittest
from pathlib import Path

from scripts import platform_publish


class StaticWebSecurityTests(unittest.TestCase):
    def test_csp_blocks_external_active_content_and_unsafe_base(self):
        policy = platform_publish.CSP
        self.assertIn("default-src 'self'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("base-uri 'self'", policy)
        self.assertIn("form-action 'self'", policy)
        self.assertIn("worker-src 'self'", policy)

    def test_static_sources_do_not_use_executable_string_sinks(self):
        root = Path(__file__).resolve().parents[1] / "site"
        bad = []
        patterns = [re.compile(r"\beval\s*\("), re.compile(r"\bnew\s+Function\s*\("), re.compile(r"document\.write\s*\(")]
        for path in root.glob("*.js"):
            text = path.read_text(encoding="utf-8")
            if any(pattern.search(text) for pattern in patterns):
                bad.append(path.name)
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
