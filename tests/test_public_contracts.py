from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.build_dashboard import build
from scripts.public_contracts import validate_public_resources


class PublicContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository_root = Path(__file__).resolve().parents[1]
        cls._template_temp = tempfile.TemporaryDirectory()
        cls.template = Path(cls._template_temp.name) / "dist"
        build(cls.repository_root, cls.template)
        validate_public_resources(cls.template)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._template_temp.cleanup()

    def copy_build(self, root: Path) -> Path:
        output = root / "dist"
        shutil.copytree(self.template, output)
        return output

    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def write(path: Path, payload: dict) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    @staticmethod
    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def refresh_registry_integrity(self, output: Path, relative_path: str) -> None:
        manifest_path = output / "data" / "build-manifest.json"
        manifest = self.load(manifest_path)
        for entry in manifest["resources"].values():
            if entry["path"] != relative_path:
                continue
            target = output / relative_path
            if "byte_size" in entry:
                entry["byte_size"] = target.stat().st_size
            if "sha256" in entry:
                entry["sha256"] = self.sha256(target)
            self.write(manifest_path, manifest)
            return
        self.fail(f"Missing registry entry for {relative_path}")

    def test_current_build_passes_all_public_contracts(self) -> None:
        validate_public_resources(self.template)

    def test_undeclared_stale_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = self.copy_build(Path(temporary))
            (output / "data" / "stale-resource.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stale_or_undeclared"):
                validate_public_resources(output)

    def test_cross_build_resource_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = self.copy_build(Path(temporary))
            manifest_path = output / "data" / "build-manifest.json"
            manifest = self.load(manifest_path)
            manifest["resources"]["collection_summary"]["build_id"] = "000000000000"
            self.write(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "different build"):
                validate_public_resources(output)

    def test_public_json_without_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = self.copy_build(Path(temporary))
            manifest_path = output / "data" / "build-manifest.json"
            manifest = self.load(manifest_path)
            manifest["resources"]["source_columns"].pop("schema", None)
            self.write(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "no declared schema"):
                validate_public_resources(output)

    def test_cross_resource_count_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = self.copy_build(Path(temporary))
            summary_path = output / "data" / "collection-summary.json"
            summary = self.load(summary_path)
            summary["pokemon_count"] += 1
            self.write(summary_path, summary)
            self.refresh_registry_integrity(output, "data/collection-summary.json")
            with self.assertRaisesRegex(ValueError, "normalized count"):
                validate_public_resources(output)

    def test_duplicate_canonical_record_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = self.copy_build(Path(temporary))
            pokemon_path = output / "data" / "pokemon.json"
            payload = self.load(pokemon_path)
            self.assertGreaterEqual(len(payload["records"]), 2)
            payload["records"][1]["identity"]["record_id"] = payload["records"][0]["identity"]["record_id"]
            self.write(pokemon_path, payload)
            with self.assertRaisesRegex(ValueError, "record IDs"):
                validate_public_resources(output)

    def test_same_export_produces_equivalent_canonical_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            second = Path(temporary) / "dist"
            build(self.repository_root, second)
            validate_public_resources(second)

            for filename in (
                "pokemon.json",
                "collection-summary.json",
                "deduplication-report.json",
                "scan-quality-report.json",
            ):
                first_payload = self.load(self.template / "data" / filename)
                second_payload = self.load(second / "data" / filename)
                if filename == "pokemon.json":
                    first_payload = first_payload["records"]
                    second_payload = second_payload["records"]
                self.assertEqual(first_payload, second_payload, filename)


if __name__ == "__main__":
    unittest.main()
