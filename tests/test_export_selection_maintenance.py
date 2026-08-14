from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_collection import discover_exports


class ExportSelectionMaintenanceTests(unittest.TestCase):
    def test_exports_are_sorted_by_filename_timestamp_across_archive_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "exports" / "archive").mkdir(parents=True)
            names = [
                "shared-text-2026-08-14 06_00_00.000.csv",
                "shared-text-2026-08-13 23_59_59.999.csv",
                "shared-text-2026-08-14 06_01_00.000.csv",
            ]
            (root / "exports" / names[0]).write_text("x", encoding="utf-8")
            (root / "exports" / "archive" / names[1]).write_text("x", encoding="utf-8")
            (root / "exports" / "archive" / names[2]).write_text("x", encoding="utf-8")

            exports = discover_exports(root)
            self.assertEqual(exports[-1].path.name, names[2])

    def test_older_export_added_later_cannot_become_newest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "exports"
            archive.mkdir()
            newest = archive / "shared-text-2026-08-14 06_01_00.000.csv"
            older = archive / "shared-text-2026-08-01 12_00_00.000.csv"
            newest.write_text("newest", encoding="utf-8")
            older.write_text("older uploaded later", encoding="utf-8")
            older.touch()

            exports = discover_exports(root)
            self.assertEqual(exports[-1].path, newest)

    def test_malformed_export_filename_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "exports"
            archive.mkdir()
            valid = archive / "shared-text-2026-08-14 06_01_00.000.csv"
            invalid = archive / "my-current-pokemon.csv"
            valid.write_text("valid", encoding="utf-8")
            invalid.write_text("invalid", encoding="utf-8")

            exports = discover_exports(root)
            self.assertEqual([item.path for item in exports], [valid])


if __name__ == "__main__":
    unittest.main()
