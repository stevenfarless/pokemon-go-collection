from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts import evidence_contract


class EvidenceContractTests(unittest.TestCase):
    def test_official_fresh_and_simulation_are_distinct(self) -> None:
        official = evidence_contract.external_evidence(
            {
                "classification": "Official",
                "provider": "official-reviewed",
                "source_reference": "https://example.test/event",
                "dataset_timestamp": "2026-08-28T10:00:00Z",
                "freshness": {
                    "state": "fresh",
                    "checked_at": "2026-08-28T10:05:00Z",
                    "reason": "within_freshness_policy",
                },
                "validity": {"valid_until": "2026-08-29T10:00:00Z"},
            }
        )
        simulation = evidence_contract.simulation_evidence(
            model_version="raid-model-1",
            confidence="medium",
            assumptions=["Explicit boss inputs"],
        )
        self.assertEqual("official-current", official["kind"])
        self.assertEqual("fresh", official["freshness"]["state"])
        self.assertEqual("simulation", simulation["kind"])
        self.assertEqual("not-applicable", simulation["freshness"]["state"])
        self.assertNotEqual(official["authority"], simulation["authority"])

    def test_stale_official_source_is_outdated_not_current(self) -> None:
        evidence = evidence_contract.external_evidence(
            {
                "classification": "Official",
                "freshness": {"state": "stale", "reason": "dataset_exceeds_max_age"},
            }
        )
        self.assertEqual("outdated", evidence["kind"])
        self.assertEqual("stale", evidence["freshness"]["state"])
        self.assertEqual("stale", evidence["prerequisites"][0]["state"])

    def test_unknown_keeps_reason_and_remediation_without_false_value(self) -> None:
        evidence = evidence_contract.unknown_evidence(
            "Exact move data is unavailable.",
            "Rescan or wait for a reviewed source.",
        )
        Draft202012Validator(evidence_contract.schema()).validate(evidence)
        self.assertEqual("unknown", evidence["kind"])
        self.assertEqual("missing", evidence["prerequisites"][0]["state"])
        self.assertIn("Rescan", evidence["prerequisites"][0]["remediation"])
        self.assertNotIn(False, evidence.values())
        self.assertNotIn(0, evidence.values())

    def test_today_and_event_resources_receive_typed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            data = output / "data"
            (data / "external").mkdir(parents=True)
            (data / "today.json").write_text(
                json.dumps(
                    {
                        "top_actions": [
                            {
                                "id": "current:events",
                                "kind": "current",
                                "title": "Current event",
                                "route": "today.html#event",
                                "source_resource": "data/external/snapshots/events.json",
                                "source_reference": "https://example.test/event",
                                "provider": "official-reviewed",
                                "dataset_timestamp": "2026-08-28T10:00:00Z",
                                "freshness": {"state": "fresh"},
                                "reversibility": "informational",
                                "warnings": [],
                                "why": [],
                            },
                            {
                                "id": "build:one",
                                "kind": "collection",
                                "title": "Review a costly build",
                                "route": "index.html?record=abc",
                                "source_resource": "data/recommendations/resource-review.json",
                                "reversibility": "review-before-action",
                                "cost": {"stardust": 100000},
                                "warnings": [],
                                "why": ["Published deterministic queue"],
                                "evidence_layer": "Calculated from owned collection facts",
                            },
                        ],
                        "sections": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (data / "external" / "index.json").write_text(
                json.dumps(
                    {
                        "snapshots": [
                            {
                                "path": "data/external/snapshots/events.json",
                                "classification": "Official",
                                "provider": "official-reviewed",
                                "source_reference": "https://example.test/event",
                                "dataset_timestamp": "2026-08-28T10:00:00Z",
                                "freshness": {
                                    "state": "fresh",
                                    "checked_at": "2026-08-28T10:05:00Z",
                                },
                                "validity": {"valid_until": "2026-08-29T10:00:00Z"},
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (data / "event-calendar.json").write_text(
                json.dumps(
                    {
                        "events": [
                            {
                                "id": "event-1",
                                "title": "Official event",
                                "route": "event-calendar.html?event=event-1",
                                "source": {
                                    "authority": "Official",
                                    "provider": "official-reviewed",
                                    "source_reference": "https://example.test/event",
                                    "dataset_timestamp": "2026-08-28T10:00:00Z",
                                    "freshness": {"state": "fresh"},
                                    "validity": {"valid_until": "2026-08-29T10:00:00Z"},
                                },
                            }
                        ],
                        "deadlines": [
                            {
                                "id": "deadline-1",
                                "title": "Evolve before deadline",
                                "route": "evolution-lab.html",
                                "source": {
                                    "authority": "Official",
                                    "provider": "official-reviewed",
                                    "dataset_timestamp": "2026-08-28T10:00:00Z",
                                    "freshness": {"state": "fresh"},
                                },
                                "exact_owned_records": [],
                                "manual_confirmation": "Confirm in game.",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            today_entries = evidence_contract.annotate_today(output)
            event_entries = evidence_contract.annotate_event_calendar(output)
            today = json.loads((data / "today.json").read_text(encoding="utf-8"))
            calendar = json.loads((data / "event-calendar.json").read_text(encoding="utf-8"))

            self.assertEqual("official-current", today["top_actions"][0]["evidence"]["kind"])
            build_evidence = today["top_actions"][1]["evidence"]
            self.assertEqual("calculated", build_evidence["kind"])
            self.assertTrue(
                any(item["state"] == "unknown" for item in build_evidence["prerequisites"])
            )
            self.assertEqual("official-current", calendar["events"][0]["evidence"]["kind"])
            deadline = calendar["deadlines"][0]["evidence"]
            self.assertTrue(
                any(item["name"] == "exact owned eligibility" for item in deadline["prerequisites"])
            )
            self.assertEqual(2, len(today_entries))
            self.assertEqual(2, len(event_entries))

    def test_index_schema_accepts_machine_evidence_index(self) -> None:
        sample = {
            "schema_version": evidence_contract.EVIDENCE_INDEX_VERSION,
            "evidence_schema": "data/evidence.schema.json",
            "entries": [
                {
                    "id": "page:raid-readiness.html",
                    "surface": "page",
                    "title": "Raid Readiness simulation evidence",
                    "route": "raid-readiness.html",
                    "resource": "data/raid-readiness.json",
                    "consequential": True,
                    "evidence": evidence_contract.simulation_evidence(model_version="model-1"),
                }
            ],
        }
        Draft202012Validator(evidence_contract.index_schema()).validate(sample)


if __name__ == "__main__":
    unittest.main()
