import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts import privacy_profiles


class PrivacyProfilesTests(unittest.TestCase):
    def test_redacted_profile_preserves_identity_and_blanks_sensitive_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            payload = {
                "manifest": {"build_id": "abc"},
                "records": [{
                    "pokemon_number": 25,
                    "name": "Pikachu",
                    "cp": 500,
                    "source_index": 7,
                    "identity": {"record_id": "keep-me"},
                    "dates": {"scan": "2026-08-20", "original_scan": "2026-08-19", "catch": "2026-08-18"},
                }],
            }
            (data / "pokemon.json").write_text(json.dumps(payload), encoding="utf-8")
            with (data / "latest-export.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Index", "Name", "Pokemon Number", "CP", "Scan Date", "Catch Date"])
                writer.writeheader(); writer.writerow({"Index": "7", "Name": "Pikachu", "Pokemon Number": "25", "CP": "500", "Scan Date": "2026-08-20", "Catch Date": "2026-08-18"})
            (root / "index.html").write_text('<html><div class="trainer-contact">Friend Code: 2252 2231 2780</div>Fuddledumpy’s Pokémon GO Collection</html>', encoding="utf-8")
            profile = privacy_profiles.prepare_privacy(root, {"POKEMON_GO_PRIVACY_PROFILE": "redacted"})
            audit = privacy_profiles.finalize_privacy(root, profile)
            result = json.loads((data / "pokemon.json").read_text(encoding="utf-8"))["records"][0]
            self.assertEqual(result["identity"]["record_id"], "keep-me")
            self.assertIsNone(result["source_index"])
            self.assertIsNone(result["dates"]["catch"])
            self.assertNotIn("2252 2231 2780", (root / "index.html").read_text(encoding="utf-8"))
            self.assertFalse(audit["friend_code_public"])
            with (data / "latest-export.csv").open(encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["Scan Date"], "")
            self.assertEqual(row["Catch Date"], "")

    def test_private_preview_is_marked_non_deployable(self):
        profile = privacy_profiles.resolve_profile({"POKEMON_GO_PRIVACY_PROFILE": "private-local-preview"})
        self.assertFalse(profile["deployment_allowed"])


if __name__ == "__main__":
    unittest.main()
