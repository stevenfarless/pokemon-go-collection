from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import event_calendar


class EventCalendarTests(unittest.TestCase):
    def _write(self, root: Path, relative: str, payload: object) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _fixture(self, root: Path, freshness: str = "fresh") -> None:
        self._write(
            root,
            "data/pokemon.json",
            {
                "records": [
                    {
                        "identity": {"record_id": "nickit-owned"},
                        "pokemon_number": 827,
                        "name": "Nickit",
                        "form": "",
                        "cp": 500,
                        "ivs": {"average_percent": 91.1},
                        "pvp": {"great": {"rank_percent": 99.2}},
                        "status": {"shadow_purified": "normal"},
                    }
                ]
            },
        )
        self._write(
            root,
            "data/reference/index.json",
            {
                "entries": [
                    {"dex": 827, "types": ["Dark"]},
                    {"dex": 828, "types": ["Dark"]},
                ]
            },
        )
        self._write(
            root,
            "data/gap-radar.json",
            {
                "species": [
                    {"dex": 827, "name": "Nickit", "species_state": "yes", "links": {"reference": "reference.html?dex=827"}},
                    {"dex": 828, "name": "Thievul", "species_state": "missing", "links": {"reference": "reference.html?dex=828"}},
                ]
            },
        )
        self._write(root, "data/roster-readiness.json", {"weakest": [{"type": "dark", "best_score": 40}]})
        source = {
            "provider": "fixture-official",
            "data_category": "events",
            "classification": "Official",
            "source_reference": "https://example.test/event",
            "source_references": ["https://example.test/event"],
            "dataset_timestamp": "2026-08-20T12:00:00Z",
            "data_version": "fixture-1",
            "freshness": {"state": freshness, "max_age_hours": 48},
            "validity": {"valid_from": "2026-08-20T12:00:00Z", "valid_until": "2026-08-25T23:00:00Z"},
            "path": "data/external/snapshots/events-fixture.json",
        }
        self._write(root, "data/external/index.json", {"snapshots": [source]})
        self._write(
            root,
            "data/external/snapshots/events-fixture.json",
            {
                "data_category": "events",
                "facts": [
                    {
                        "event_id": "fixture-community-day",
                        "title": "Fixture Community Day",
                        "starts_at": "2026-08-21T14:00:00-05:00",
                        "ends_at": "2026-08-21T17:00:00-05:00",
                        "timezone": "local; fixture America/Chicago",
                        "featured_dex": [827, 828],
                        "featured_species": ["Nickit", "Thievul"],
                        "evolution_targets": [
                            {
                                "dex": 828,
                                "name": "Thievul",
                                "required_evolution_from": "Nickit",
                                "exclusive_charged_move": "Icy Wind",
                                "window_ends_at": "2026-08-21T21:00:00-05:00",
                            }
                        ],
                        "source_reference": "https://example.test/event",
                    }
                ],
            },
        )

    def test_fresh_event_builds_exact_collection_overlays_and_separate_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self._fixture(output, "fresh")
            manifest = {"build_id": "abcdef123456", "generated_at_utc": "2026-08-20T18:00:00Z", "export_timestamp": "2026-08-20T18:00:00Z"}
            payload = event_calendar.build_calendar(output, manifest)
            event_calendar.schema()
            self.assertEqual(len(payload["events"]), 1)
            event = payload["events"][0]
            self.assertTrue(event["actionable_at_build"])
            self.assertEqual(event["source"]["authority"], "Official")
            self.assertEqual(event["overlays"]["exact_owned_records"][0]["record_id"], "nickit-owned")
            self.assertEqual(event["overlays"]["strong_pvp_records"][0]["record_id"], "nickit-owned")
            self.assertEqual(event["overlays"]["missing_featured_species"][0]["dex"], 828)
            self.assertIn("dark", event["overlays"]["related_weak_roster_types"])

            deadline = next(item for item in payload["deadlines"] if item["kind"] == "evolution-move-window")
            self.assertEqual(deadline["parent_event_id"], event["id"])
            self.assertEqual(deadline["ends_at"], "2026-08-21T21:00:00-05:00")
            self.assertEqual(deadline["exact_owned_records"][0]["record_id"], "nickit-owned")
            self.assertEqual(deadline["target"]["exclusive_move"], "Icy Wind")
            self.assertTrue(deadline["actionable_at_build"])

    def test_stale_snapshot_is_retained_only_as_non_actionable_history_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self._fixture(output, "stale")
            manifest = {"build_id": "abcdef123456", "generated_at_utc": "2026-08-20T18:00:00Z", "export_timestamp": "2026-08-20T18:00:00Z"}
            payload = event_calendar.build_calendar(output, manifest)
            self.assertEqual(len(payload["events"]), 1)
            self.assertFalse(payload["events"][0]["actionable_at_build"])
            self.assertTrue(all(not item["actionable_at_build"] for item in payload["deadlines"]))
            self.assertEqual(payload["current_policy"]["stale_or_expired"], "history-only; never shown in Now/Today/Next 7 days/Later actionable scopes")


if __name__ == "__main__":
    unittest.main()
