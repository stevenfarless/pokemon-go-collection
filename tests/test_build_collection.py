from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts import build_site
from scripts.build_collection import build, discover_exports


class HardenedBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "exports").mkdir()
        (self.root / "site").mkdir()
        (self.root / "site" / "index.html").write_text(
            "<html><head><link rel=\"stylesheet\" href=\"assets/styles.css\">"
            "<script defer src=\"assets/app.js\"></script></head>"
            "<body>{{SOURCE_FILENAME}} {{EXPORT_TIMESTAMP}} {{POKEMON_COUNT}} {{GENERATED_AT}}</body></html>",
            encoding="utf-8",
        )
        (self.root / "site" / "app.js").write_text("", encoding="utf-8")
        (self.root / "site" / "styles.css").write_text("", encoding="utf-8")
        (self.root / "site" / "hardening.js").write_text("// hardening", encoding="utf-8")
        (self.root / "site" / "stability.css").write_text("/* stability */", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_export(self, directory: Path, filename: str, name: str = "Bulbasaur") -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        row = {column: "" for column in build_site.EXPECTED_COLUMNS}
        row.update({
            "Index": "1",
            "Name": name,
            "Pokemon Number": "1",
            "CP": "500",
            "HP": "60",
            "Atk IV": "15",
            "Def IV": "15",
            "Sta IV": "15",
            "IV Avg": "100",
            "Level Min": "20",
            "Level Max": "20",
            "Quick Move": "Vine Whip",
            "Charge Move": "Power Whip",
            "Lucky": "0",
            "Shadow/Purified": "0",
            "Favorite": "0",
        })
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=build_site.EXPECTED_COLUMNS)
            writer.writeheader()
            writer.writerow(row)
        return path

    def test_discovery_ignores_matching_files_outside_exports(self) -> None:
        self.write_export(self.root, "shared-text-2026-08-06 00_00_00.000.csv", "Outside")
        expected = self.write_export(
            self.root / "exports", "shared-text-2026-08-05 23_24_00.336.csv", "Inside"
        )
        hidden = self.root / "exports" / ".hidden"
        self.write_export(hidden, "shared-text-2026-08-07 00_00_00.000.csv", "Hidden")

        discovered = discover_exports(self.root)
        self.assertEqual([item.path for item in discovered], [expected])

    def test_build_injects_hardened_assets_and_updates_manifest(self) -> None:
        self.write_export(
            self.root / "exports", "shared-text-2026-08-05 23_24_00.336.csv"
        )
        output = self.root / "dist"
        manifest = build(self.root, output)

        self.assertEqual(manifest["generator"], "scripts/build_collection.py")
        self.assertTrue((output / "assets" / "hardening.js").exists())
        self.assertTrue((output / "assets" / "stability.css").exists())
        html = (output / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="assets/stability.css"', html)
        self.assertIn('src="assets/hardening.js"', html)

        published_manifest = json.loads(
            (output / "data" / "build-manifest.json").read_text(encoding="utf-8")
        )
        payload = json.loads((output / "data" / "pokemon.json").read_text(encoding="utf-8"))
        self.assertEqual(published_manifest["generator"], "scripts/build_collection.py")
        self.assertEqual(payload["manifest"]["generator"], "scripts/build_collection.py")

    def test_duplicate_newest_timestamp_inside_exports_still_fails(self) -> None:
        filename = "shared-text-2026-08-05 23_24_00.336.csv"
        self.write_export(self.root / "exports", filename)
        self.write_export(self.root / "exports" / "archive", filename)
        with self.assertRaisesRegex(ValueError, "Multiple exports"):
            build(self.root, self.root / "dist")


if __name__ == "__main__":
    unittest.main()
