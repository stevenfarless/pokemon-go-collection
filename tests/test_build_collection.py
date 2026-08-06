from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts import build_site
from scripts.build_collection import build, discover_exports
from scripts.validate_generated import validate_generated


class CollectionBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "exports").mkdir()
        (self.root / "site").mkdir()
        (self.root / "site" / "index.html").write_text(
            "<!doctype html><html><head>"
            '<link rel="stylesheet" href="assets/styles.css">'
            '<script defer src="assets/app.js"></script>'
            "</head><body>{{SOURCE_FILENAME}} {{EXPORT_TIMESTAMP}} "
            "{{POKEMON_COUNT}} {{GENERATED_AT}}</body></html>",
            encoding="utf-8",
        )
        (self.root / "site" / "app.js").write_text(
            'fetch("data/pokemon.json"); fetch("data/collection-summary.json");',
            encoding="utf-8",
        )
        (self.root / "site" / "styles.css").write_text("body { margin: 0; }", encoding="utf-8")
        (self.root / "site" / "stability.css").write_text("main { min-height: 10rem; }", encoding="utf-8")
        (self.root / "site" / "hardening.js").write_text("// hardening", encoding="utf-8")
        (self.root / "site" / "accessibility.js").write_text("// accessibility", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_export(
        self,
        directory: Path,
        filename: str,
        *,
        fieldnames: list[str] | None = None,
        name: str = "Bulbasaur",
    ) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        columns = fieldnames or list(build_site.EXPECTED_COLUMNS)
        path = directory / filename
        row = {column: "" for column in columns}
        values = {
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
        }
        row.update({key: value for key, value in values.items() if key in row})
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerow(row)
        return path

    def test_discovery_ignores_matching_files_outside_exports(self) -> None:
        self.write_export(self.root, "shared-text-2026-08-06 00_00_00.000.csv", name="Outside")
        expected = self.write_export(
            self.root / "exports", "shared-text-2026-08-05 23_24_00.336.csv", name="Inside"
        )
        self.write_export(
            self.root / "exports" / ".hidden",
            "shared-text-2026-08-07 00_00_00.000.csv",
            name="Hidden",
        )
        self.assertEqual([item.path for item in discover_exports(self.root)], [expected])

    def test_optional_columns_can_be_missing_and_are_disclosed(self) -> None:
        columns = ["CP", "Name", "Pokemon Number", "Future Column"]
        self.write_export(
            self.root / "exports",
            "shared-text-2026-08-05 23_24_00.336.csv",
            fieldnames=columns,
        )
        output = self.root / "dist"
        manifest = build(self.root, output)
        payload = json.loads((output / "data" / "pokemon.json").read_text(encoding="utf-8"))
        record = payload["records"][0]

        self.assertIsNone(record["ivs"]["attack"])
        self.assertIsNone(record["moves"]["fast"])
        self.assertEqual(record["status"]["shadow_purified"], "normal")
        self.assertIn("Atk IV", manifest["missing_optional_columns"])
        self.assertEqual(manifest["unknown_columns"], ["Future Column"])
        self.assertTrue(manifest["schema_warnings"])

    def test_missing_core_column_fails(self) -> None:
        self.write_export(
            self.root / "exports",
            "shared-text-2026-08-05 23_24_00.336.csv",
            fieldnames=["Name", "CP"],
        )
        with self.assertRaisesRegex(ValueError, "Pokemon Number"):
            build(self.root, self.root / "dist")

    def test_build_versions_assets_and_publishes_valid_contracts(self) -> None:
        self.write_export(
            self.root / "exports", "shared-text-2026-08-05 23_24_00.336.csv"
        )
        output = self.root / "dist"
        manifest = build(self.root, output)
        validate_generated(output)

        self.assertEqual(manifest["generator"], "scripts/build_collection.py")
        self.assertRegex(manifest["build_id"], r"^[0-9a-f]{12}$")
        for asset in manifest["assets"].values():
            self.assertRegex(asset, r"^assets/[a-z]+\.[0-9a-f]{12}\.(?:css|js)$")
            self.assertTrue((output / asset).is_file())

        html = (output / "index.html").read_text(encoding="utf-8")
        self.assertIn("data-critical-css", html)
        self.assertIn('rel="preload"', html)
        self.assertNotIn('href="assets/styles.css"', html)
        self.assertNotIn('src="assets/app.js"', html)
        self.assertIn(manifest["assets"]["app"], html)
        self.assertIn(manifest["assets"]["hardening"], html)
        self.assertIn(manifest["assets"]["accessibility"], html)

        app = (output / manifest["assets"]["app"]).read_text(encoding="utf-8")
        self.assertIn(f"pokemon.json?v={manifest['build_id']}", app)
        self.assertIn(f"collection-summary.json?v={manifest['build_id']}", app)

        source_columns = json.loads(
            (output / "data" / "source-columns.json").read_text(encoding="utf-8")
        )
        self.assertEqual(source_columns["missing_required_columns"], [])
        for schema_name in (
            "schema.json",
            "collection-summary.schema.json",
            "build-manifest.schema.json",
        ):
            schema = json.loads((output / "data" / schema_name).read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)

    def test_duplicate_newest_timestamp_inside_exports_still_fails(self) -> None:
        filename = "shared-text-2026-08-05 23_24_00.336.csv"
        self.write_export(self.root / "exports", filename)
        self.write_export(self.root / "exports" / "archive", filename)
        with self.assertRaisesRegex(ValueError, "Multiple exports"):
            build(self.root, self.root / "dist")


if __name__ == "__main__":
    unittest.main()
