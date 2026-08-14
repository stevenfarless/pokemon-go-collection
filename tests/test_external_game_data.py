from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.external_game_data import (
    assess_freshness,
    external_index,
    normalize_snapshot,
    refresh_with_last_known_good,
)


class ExternalGameDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(Path("tests/fixtures/external-game-data-example.json").read_text(encoding="utf-8"))

    def test_fixture_normalizes_as_fresh_inside_policy(self) -> None:
        now = datetime(2026, 8, 14, 12, tzinfo=timezone.utc)
        normalized = normalize_snapshot(self.fixture, now=now)
        self.assertEqual(normalized["freshness"]["state"], "fresh")
        self.assertEqual(normalized["classification"], "Reported")
        self.assertEqual(normalized["join_keys"], ["species_id"])

    def test_snapshot_becomes_stale_after_max_age(self) -> None:
        normalized = normalize_snapshot(self.fixture, now=datetime(2026, 8, 14, 12, tzinfo=timezone.utc))
        freshness = assess_freshness(normalized, now=datetime(2026, 8, 15, 6, tzinfo=timezone.utc))
        self.assertEqual(freshness["state"], "stale")
        self.assertEqual(freshness["reason"], "dataset_exceeds_max_age")

    def test_validity_window_expiration_takes_precedence(self) -> None:
        candidate = dict(self.fixture)
        candidate["freshness_policy"] = dict(candidate["freshness_policy"], max_age_hours=500)
        normalized = normalize_snapshot(candidate, now=datetime(2026, 8, 14, 12, tzinfo=timezone.utc))
        freshness = assess_freshness(normalized, now=datetime(2026, 8, 17, tzinfo=timezone.utc))
        self.assertEqual(freshness["state"], "expired")

    def test_malformed_refresh_preserves_last_known_good(self) -> None:
        previous = normalize_snapshot(self.fixture, now=datetime(2026, 8, 14, 12, tzinfo=timezone.utc))
        malformed = dict(self.fixture)
        malformed["license"] = {"name": "unknown", "redistribution_permitted": False}
        selected, event = refresh_with_last_known_good(
            malformed,
            previous,
            now=datetime(2026, 8, 14, 13, tzinfo=timezone.utc),
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected["data_version"], previous["data_version"])
        self.assertEqual(event["status"], "failed-update")
        self.assertTrue(event["preserved_last_known_good"])

    def test_malformed_first_refresh_degrades_to_unavailable(self) -> None:
        malformed = dict(self.fixture)
        malformed.pop("join_keys")
        selected, event = refresh_with_last_known_good(
            malformed,
            None,
            now=datetime(2026, 8, 14, 13, tzinfo=timezone.utc),
        )
        self.assertIsNone(selected)
        self.assertEqual(event["status"], "failed-update")
        self.assertFalse(event["preserved_last_known_good"])

    def test_empty_framework_requires_no_provider_or_paid_service(self) -> None:
        index = external_index(snapshots=[], generated_at="2026-08-14T00:00:00Z")
        self.assertEqual(index["overall_freshness"], "unavailable")
        self.assertEqual(index["snapshot_count"], 0)
        self.assertFalse(index["architecture"]["runtime_server_required"])
        self.assertFalse(index["architecture"]["paid_service_required"])
        self.assertFalse(index["architecture"]["provider_required_for_core_collection"])


if __name__ == "__main__":
    unittest.main()
