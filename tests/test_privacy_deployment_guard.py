import json
import tempfile
import unittest
from pathlib import Path

from scripts.deployment_guard import validate_privacy_status


class PrivacyDeploymentGuardTests(unittest.TestCase):
    def test_private_marker_blocks_public_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".private-local-preview").write_text("private", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "local-only"):
                validate_privacy_status(root)

    def test_redacted_profile_can_promote_when_audit_allows_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data" / "privacy-audit.json").write_text(json.dumps({
                "schema_version": 1,
                "profile": "redacted",
                "deployment_allowed": True,
                "friend_code_public": False,
                "browser_local_namespaces_public": False,
            }), encoding="utf-8")
            status = validate_privacy_status(root)
            self.assertEqual(status["profile"], "redacted")
            self.assertFalse(status["friend_code_public"])


if __name__ == "__main__":
    unittest.main()
