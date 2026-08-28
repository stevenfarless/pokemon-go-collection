from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_architecture import check


class ArchitecturePolicyTests(unittest.TestCase):
    def make_minimal_repo(self, root: Path) -> None:
        for path in (
            Path("docs/architecture.md"),
            Path("docs/fork-bootstrap.md"),
            Path("docs/deployment-safety.md"),
            Path(".github/workflows/deploy-pages.yml"),
            Path(".github/workflows/bootstrap-self-test.yml"),
            Path(".github/workflows/rollback-pages.yml"),
            Path(".github/workflows/sync-knowledge.yml"),
            Path("scripts/build_dashboard.py"),
            Path("scripts/bootstrap_self_test.py"),
            Path("scripts/deployment_guard.py"),
            Path("scripts/sync_knowledge.py"),
            Path("knowledge/source-lock.json"),
            Path("knowledge/pokemon-go.json"),
            Path("knowledge/pokemon-go.schema.json"),
            Path("knowledge/species-index.json"),
            Path("knowledge/species-index.schema.json"),
            Path("knowledge/PVPOKE-LICENSE.txt"),
            Path("exports/README.md"),
        ):
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# fixture\n", encoding="utf-8")
        (root / "site").mkdir(exist_ok=True)
        (root / "package.json").write_text(
            json.dumps({"dependencies": {}}),
            encoding="utf-8",
        )

    def test_safe_static_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_minimal_repo(root)
            self.assertEqual(check(root), [])

    def test_retired_validation_workflow_is_not_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_minimal_repo(root)
            self.assertFalse((root / ".github" / "workflows" / "validate.yml").exists())
            self.assertEqual(check(root), [])

    def test_required_hosted_backend_dependency_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_minimal_repo(root)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"firebase": "1.0.0"}}),
                encoding="utf-8",
            )
            errors = check(root)
            self.assertTrue(any("firebase" in error for error in errors))

    def test_owner_provisioned_workflow_secret_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_minimal_repo(root)
            workflow = root / ".github" / "workflows" / "deploy-pages.yml"
            workflow.write_text(
                "steps:\n  - run: echo '${{ secrets.REQUIRED_API_KEY }}'\n",
                encoding="utf-8",
            )
            errors = check(root)
            self.assertTrue(any("REQUIRED_API_KEY" in error for error in errors))

    def test_current_repository_satisfies_permanent_policy(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(check(root), [])


if __name__ == "__main__":
    unittest.main()
