from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UploadWorkflowMaintenanceTests(unittest.TestCase):
    def _workflow(self, name: str) -> str:
        return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_deploy_triggers_for_root_and_nested_exports(self):
        workflow = self._workflow("deploy-pages.yml")
        self.assertIn('"exports/shared-text-*.csv"', workflow)
        self.assertIn('"exports/**/shared-text-*.csv"', workflow)

    def test_validation_triggers_for_root_and_nested_exports(self):
        workflow = self._workflow("validate.yml")
        self.assertIn('"exports/shared-text-*.csv"', workflow)
        self.assertIn('"exports/**/shared-text-*.csv"', workflow)

    def test_deploy_uses_the_production_promotion_guard(self):
        workflow = self._workflow("deploy-pages.yml")
        self.assertIn("python scripts/deployment_guard.py --output staging", workflow)

    def test_pull_request_validation_exercises_the_same_guard(self):
        workflow = self._workflow("validate.yml")
        self.assertIn("python scripts/deployment_guard.py --output dist", workflow)


if __name__ == "__main__":
    unittest.main()
