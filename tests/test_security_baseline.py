from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SecurityBaselineTests(unittest.TestCase):
    def test_dependabot_covers_all_repository_dependency_ecosystems(self):
        config = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        for ecosystem in ("github-actions", "npm", "pip"):
            self.assertIn(f"package-ecosystem: {ecosystem}", config)

    def test_codeql_covers_javascript_python_and_actions_with_immutable_pins(self):
        workflow = (ROOT / ".github" / "workflows" / "codeql.yml").read_text(encoding="utf-8")
        for language in ("javascript-typescript", "python", "actions"):
            self.assertIn(f"- {language}", workflow)
        self.assertIn("queries: security-extended", workflow)
        self.assertIn("security-events: write", workflow)
        self.assertNotRegex(workflow, r"github/codeql-action/(?:init|analyze)@v\d")
        pins = re.findall(r"github/codeql-action/(?:init|analyze)@([0-9a-f]{40})", workflow)
        self.assertEqual(len(pins), 2)
        self.assertEqual(len(set(pins)), 1)

    def test_dependency_review_blocks_high_severity_with_immutable_pin(self):
        workflow = (ROOT / ".github" / "workflows" / "dependency-review.yml").read_text(encoding="utf-8")
        self.assertIn("fail-on-severity: high", workflow)
        self.assertNotRegex(workflow, r"actions/dependency-review-action@v\d")
        self.assertRegex(workflow, r"actions/dependency-review-action@[0-9a-f]{40}")

    def test_security_policy_and_baseline_documentation_exist(self):
        security_policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        baseline = (ROOT / "docs" / "security-baseline.md").read_text(encoding="utf-8")
        self.assertIn("Reporting a vulnerability", security_policy)
        self.assertIn("GitHub repository settings checklist", baseline)
        self.assertIn("Dependabot alerts enabled", baseline)
        self.assertIn("Code scanning", baseline)


if __name__ == "__main__":
    unittest.main()
