import unittest

from scripts.check_mechanics_sources import _fingerprint_html, _normalize_html


class MechanicsSourceFingerprintTests(unittest.TestCase):
    def test_relative_last_updated_age_does_not_change_fingerprint(self):
        first = "<article><h1>Mechanic</h1><p>Last Updated: 224d</p><p>Stable rule.</p></article>"
        second = "<article><h1>Mechanic</h1><p>Last Updated: 225d</p><p>Stable rule.</p></article>"

        self.assertEqual(_fingerprint_html(first), _fingerprint_html(second))

    def test_relative_last_updated_units_are_removed(self):
        self.assertEqual(
            _normalize_html("<article><p>Last Updated: 7d</p><p>Rule</p></article>"),
            "Rule",
        )
        self.assertEqual(
            _normalize_html("<article><p>Last Updated: 3 hours</p><p>Rule</p></article>"),
            "Rule",
        )

    def test_mechanics_content_change_still_changes_fingerprint(self):
        before = "<article><p>Last Updated: 7d</p><p>Limit is 800.</p></article>"
        after = "<article><p>Last Updated: 8d</p><p>Limit is 1,000.</p></article>"

        self.assertNotEqual(_fingerprint_html(before), _fingerprint_html(after))


if __name__ == "__main__":
    unittest.main()
