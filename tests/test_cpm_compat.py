from __future__ import annotations

import unittest

from scripts import cpm_compat


class CpmCompatTests(unittest.TestCase):
    def test_reads_current_knowledge_multiplier_shape(self) -> None:
        mechanics = {"cp_multiplier_levels": [{"level": 20.0, "multiplier": 0.5974}]}
        self.assertEqual(cpm_compat.cpm_for_level(mechanics, 20.0), 0.5974)

    def test_keeps_older_cpm_and_mapping_shapes_compatible(self) -> None:
        self.assertEqual(
            cpm_compat.cpm_for_level({"cp_multiplier_levels": [{"level": 20.0, "cpm": 0.5}]}, 20.0),
            0.5,
        )
        self.assertEqual(cpm_compat.cpm_for_level({"cp_multiplier_levels": {"20.0": 0.6}}, 20.0), 0.6)

    def test_unknown_level_fails_closed(self) -> None:
        self.assertIsNone(cpm_compat.cpm_for_level({"cp_multiplier_levels": []}, 20.0))


if __name__ == "__main__":
    unittest.main()
