from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_site import EXPECTED_COLUMNS, build, parse_export_filename, select_latest_export


class BuildSiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "exports").mkdir()
        (self.root / "site").mkdir()
        (self.root / "site" / "index.html").write_text(
            "{{SOURCE_FILENAME}} {{EXPORT_TIMESTAMP}} {{POKEMON_COUNT}} {{GENERATED_AT}}",
            encoding="utf-8",
        )
        (self.root / "site" / "app.js").write_text("", encoding="utf-8")
        (self.root / "site" / "styles.css").write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_export(self, filename: str, name: str = "Bulbasaur") -> Path:
        path = self.root / "exports" / filename
        row = {column: "" for column in EXPECTED_COLUMNS}
        row.update({
            "Index": "1",
            "Name": name,
            "Pokemon Number": "1",
            "CP": "500",
            "HP": "60",
            "Atk IV": "15",
            "Def IV": "15",
            "Sta IV": "15",
            "IV Avg": "100.0",
            "Lucky": "0",
            "Shadow/Purified": "0",
            "Favorite": "1",
            "Rank % (G)": "99.50%",
            "Rank # (G)": "20",
        })
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=EXPECTED_COLUMNS)
            writer.writeheader()
            writer.writerow(row)
        return path

    def test_filename_parser(self) -> None:
        parsed = parse_export_filename(Path("shared-text-2026-08-05 23_24_00.336.csv"))
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.timestamp.isoformat(timespec="milliseconds"), "2026-08-05T23:24:00.336")
        self.assertIsNone(parse_export_filename(Path("2026-08-05 export.csv")))

    def test_selects_newest_timestamp_not_mtime(self) -> None:
        older = self.write_export("shared-text-2026-08-01 01_00_00.000.csv")
        newest = self.write_export("shared-text-2026-08-05 23_24_00.336.csv")
        older.touch()
        selected = select_latest_export(self.root)
        self.assertEqual(selected.path, newest)

    def test_duplicate_newest_timestamp_fails(self) -> None:
        self.write_export("shared-text-2026-08-05 23_24_00.336.csv")
        duplicate_dir = self.root / "archive"
        duplicate_dir.mkdir()
        duplicate = duplicate_dir / "shared-text-2026-08-05 23_24_00.336.csv"
        duplicate.write_text((self.root / "exports" / duplicate.name).read_text(encoding="utf-8"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Multiple exports"):
            select_latest_export(self.root)

    def test_build_outputs_normalized_data(self) -> None:
        self.write_export("shared-text-2026-08-05 23_24_00.336.csv")
        output = self.root / "dist"
        manifest = build(self.root, output)
        self.assertEqual(manifest["pokemon_count"], 1)
        payload = json.loads((output / "data" / "pokemon.json").read_text(encoding="utf-8"))
        record = payload["records"][0]
        self.assertTrue(record["ivs"]["is_hundo"])
        self.assertEqual(record["pvp"]["great"]["rank_percent"], 99.5)
        self.assertEqual(record["status"]["favorite"], True)
        self.assertTrue((output / "llms.txt").exists())
        self.assertTrue((output / "data" / "latest-export.csv").exists())

    def test_newest_invalid_export_fails_instead_of_falling_back(self) -> None:
        self.write_export("shared-text-2026-08-01 01_00_00.000.csv")
        invalid = self.root / "exports" / "shared-text-2026-08-05 23_24_00.336.csv"
        invalid.write_text("Name,CP\nPikachu,500\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            build(self.root, self.root / "dist")


if __name__ == "__main__":
    unittest.main()
