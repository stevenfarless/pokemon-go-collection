from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.bootstrap_self_test import REQUIRED_PATHS, evaluate
from scripts.build_dashboard import build
from scripts.deployment_guard import inspect_staged_build


class DeploymentGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls.root = Path(__file__).resolve().parents[1]
        cls.output = Path(cls._temporary.name) / "dist"
        cls.manifest = build(cls.root, cls.output)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    def _copy_build(self) -> Path:
        destination = Path(self._temporary.name) / self._testMethodName
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(self.output, destination)
        return destination

    def test_valid_canonical_build_is_promotable(self) -> None:
        metadata = inspect_staged_build(self.output)
        self.assertEqual(metadata["build_id"], self.manifest["build_id"])
        self.assertEqual(metadata["pokemon_count"], self.manifest["normalized_record_count"])
        self.assertGreater(metadata["resource_count"], 0)

    def test_expected_build_id_blocks_wrong_rollback_artifact(self) -> None:
        with self.assertRaisesRegex(ValueError, "Rollback build ID mismatch"):
            inspect_staged_build(self.output, expected_build_id="000000000000")

    def test_stale_asset_blocks_mixed_build_promotion(self) -> None:
        candidate = self._copy_build()
        (candidate / "assets" / "app.deadbeefdead.js").write_text("stale\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "undeclared/stale assets"):
            inspect_staged_build(candidate)

    def test_missing_page_blocks_promotion(self) -> None:
        candidate = self._copy_build()
        (candidate / "index.html").unlink()
        with self.assertRaisesRegex(ValueError, "missing required Pages resource"):
            inspect_staged_build(candidate)


class BootstrapSelfTestTests(unittest.TestCase):
    def _fixture(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        for relative in REQUIRED_PATHS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n", encoding="utf-8")

        rollback = root / ".github" / "workflows" / "rollback-pages.yml"
        rollback.parent.mkdir(parents=True, exist_ok=True)
        rollback.write_text("name: rollback\n", encoding="utf-8")
        deploy = root / ".github" / "workflows" / "deploy-pages.yml"
        deploy.write_text(
            "pages: write\nid-token: write\nactions/upload-pages-artifact@x\n"
            "actions/deploy-pages@x\nscripts/deployment_guard.py\n",
            encoding="utf-8",
        )
        validate = root / ".github" / "workflows" / "validate.yml"
        validate.write_text("python scripts/validate_generated.py\n", encoding="utf-8")

        knowledge_dir = root / "knowledge"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        commit = "a" * 40
        lock = {
            "dataset_version": "fixture",
            "source": {"commit": commit},
        }
        payload = {
            "dataset_version": "fixture",
            "classification": "Verified community data",
            "source": {"name": "fixture", "commit": commit},
            "mechanics": {"cp_multiplier_levels": [{"level": 20.0, "multiplier": 0.5974}]},
            "entries": [],
        }
        permissive_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
        }
        (knowledge_dir / "source-lock.json").write_text(json.dumps(lock), encoding="utf-8")
        (knowledge_dir / "pokemon-go.json").write_text(json.dumps(payload), encoding="utf-8")
        (knowledge_dir / "pokemon-go.schema.json").write_text(json.dumps(permissive_schema), encoding="utf-8")
        (knowledge_dir / "species-index.json").write_text("{}\n", encoding="utf-8")
        (knowledge_dir / "species-index.schema.json").write_text(json.dumps(permissive_schema), encoding="utf-8")
        (knowledge_dir / "PVPOKE-LICENSE.txt").write_text("fixture\n", encoding="utf-8")

        exports = root / "exports"
        exports.mkdir(parents=True, exist_ok=True)
        (exports / "shared-text-2026-08-05 23_24_00.336.csv").write_text(
            "Name,Pokemon Number,CP\nPikachu,25,500\n",
            encoding="utf-8",
        )
        return temporary, root

    @mock.patch("scripts.bootstrap_self_test.check_architecture.check", return_value=[])
    def test_minimal_fork_fixture_passes(self, _architecture: mock.Mock) -> None:
        temporary, root = self._fixture()
        self.addCleanup(temporary.cleanup)
        result = evaluate(root)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["valid_export_count"], 1)

    @mock.patch("scripts.bootstrap_self_test.check_architecture.check", return_value=[])
    def test_nonconforming_archived_csv_warns_when_valid_export_exists(self, _architecture: mock.Mock) -> None:
        temporary, root = self._fixture()
        self.addCleanup(temporary.cleanup)
        (root / "exports" / "shared-text-2026-08-06 09_02_00.csv").write_text(
            "Name,Pokemon Number,CP\n",
            encoding="utf-8",
        )
        result = evaluate(root)
        self.assertTrue(result["ok"], result["errors"])
        self.assertTrue(any("Ignored CSV files" in warning for warning in result["warnings"]))

    @mock.patch("scripts.bootstrap_self_test.check_architecture.check", return_value=[])
    def test_only_malformed_export_name_is_actionable_failure(self, _architecture: mock.Mock) -> None:
        temporary, root = self._fixture()
        self.addCleanup(temporary.cleanup)
        for path in (root / "exports").glob("*.csv"):
            path.unlink()
        (root / "exports" / "pokemon.csv").write_text("Name,Pokemon Number,CP\n", encoding="utf-8")
        result = evaluate(root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("supported Poke Genie archive pattern" in error for error in result["errors"]))

    @mock.patch("scripts.bootstrap_self_test.check_architecture.check", return_value=[])
    def test_missing_export_has_setup_instruction(self, _architecture: mock.Mock) -> None:
        temporary, root = self._fixture()
        self.addCleanup(temporary.cleanup)
        for path in (root / "exports").glob("*.csv"):
            path.unlink()
        result = evaluate(root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("Upload the exported CSV" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
