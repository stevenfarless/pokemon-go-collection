from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.external_game_data import (
    assess_freshness,
    external_index,
    normalize_snapshot,
    publish_external_framework,
    refresh_with_last_known_good,
    validate_snapshot_join_keys,
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
        self.assertFalse(index["architecture"]["official_site_automated_scraping"])

    def test_reviewed_production_inputs_are_source_attributed_and_joinable(self) -> None:
        root = Path(__file__).resolve().parents[1]
        cases = (
            ("official-events.json", "events", "Official"),
            ("official-raids.json", "raids", "Official"),
            ("rocket-pokemongo-hub-reviewed.json", "rocket", "Verified community data"),
        )
        review_times = {
            "events": datetime(2026, 8, 14, 12, tzinfo=timezone.utc),
            "raids": datetime(2026, 8, 14, 12, tzinfo=timezone.utc),
            "rocket": datetime(2026, 8, 31, 2, tzinfo=timezone.utc),
        }
        for filename, category, classification in cases:
            raw = json.loads((root / "external" / "providers" / filename).read_text(encoding="utf-8"))
            normalized = normalize_snapshot(raw, now=review_times[category])
            self.assertEqual(normalized["classification"], classification)
            self.assertEqual(normalized["data_category"], category)
            self.assertEqual(normalized["freshness"]["state"], "fresh")
            self.assertFalse(normalized["acquisition"]["automated_source_scraping"])
            self.assertTrue(normalized["license"]["redistribution_permitted"])
            validate_snapshot_join_keys(normalized, root)

    def test_rocket_provider_exposes_current_leaders_and_complete_grunt_phrase_branching_without_counter_rankings(self) -> None:
        root = Path(__file__).resolve().parents[1]
        raw = json.loads((root / "external" / "providers" / "rocket-pokemongo-hub-reviewed.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["data_category"], "rocket")
        self.assertEqual(len(raw["facts"]), 30)
        leaders = [fact for fact in raw["facts"] if fact.get("leader") or fact.get("boss")]
        grunts = [fact for fact in raw["facts"] if fact.get("phrase")]
        self.assertEqual(len(leaders), 4)
        self.assertEqual(len(grunts), 26)
        self.assertEqual({fact.get("leader") or fact.get("boss") for fact in leaders}, {"Arlo", "Cliff", "Sierra", "Giovanni"})
        self.assertEqual(
            {fact.get("grunt_type") for fact in grunts},
            {"Bug", "Dark", "Dragon", "Electric", "Fairy", "Fighting", "Fire", "Flying", "Ghost", "Grass", "Ground", "Ice", "Normal", "Poison", "Psychic", "Rock", "Steel", "Water", "Typeless", "Decoy"},
        )
        self.assertTrue(all(len(fact["slots"]) == 3 for fact in raw["facts"]))
        self.assertTrue(all("counter_species_dexes" not in fact for fact in raw["facts"]))
        self.assertIn("Go, my super bug Pokémon!", {fact["phrase"] for fact in grunts})
        self.assertIn("Fooled ya, twerp.", {fact["phrase"] for fact in grunts})
        water = [fact for fact in grunts if fact.get("grunt_type") == "Water"]
        self.assertEqual({fact.get("grunt_gender") for fact in water}, {"female", "male"})
        ambiguous = [fact for fact in grunts if fact.get("grunt_type") == "Typeless"]
        self.assertEqual(len(ambiguous), 6)
        self.assertEqual({fact.get("variant") for fact in ambiguous}, {"Snorlax", "Starters"})
        self.assertIn("https://pokemongohub.net/post/guide/team-go-rocket-battle-guide/", raw["source_references"])
        self.assertFalse(raw["acquisition"]["counter_rankings_redistributed"])

    def test_production_publish_exposes_event_raid_and_rocket_snapshot_paths(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            index = publish_external_framework(
                root,
                output,
                {
                    "build_id": "0123456789ab",
                    "generated_at_utc": "2026-08-31T02:00:00Z",
                },
            )
            self.assertEqual(index["snapshot_count"], 3)
            self.assertEqual(index["overall_freshness"], "fresh")
            categories = {item["data_category"] for item in index["snapshots"]}
            self.assertEqual(categories, {"events", "raids", "rocket"})
            states = {item["data_category"]: item["freshness"]["state"] for item in index["snapshots"]}
            self.assertEqual(states["rocket"], "fresh")
            self.assertIn(states["events"], {"stale", "expired"})
            self.assertIn(states["raids"], {"stale", "expired"})
            for item in index["snapshots"]:
                self.assertTrue(item["path"].startswith("data/external/snapshots/"))
                snapshot = json.loads((output / item["path"]).read_text(encoding="utf-8"))
                self.assertEqual(snapshot["build_id"], "0123456789ab")


if __name__ == "__main__":
    unittest.main()
