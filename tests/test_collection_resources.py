from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.collection_resources import (
    _diff_snapshots,
    publish_derived_views,
    publish_species_family_resources,
    publish_static_api,
    validate_static_api,
)


class CollectionResourceTests(unittest.TestCase):
    def _record(
        self,
        record_id: str,
        fingerprint: str,
        *,
        dex: int,
        name: str,
        cp: int,
        attack: int,
        defense: int,
        stamina: int,
        status: str = "normal",
        lucky: bool = False,
        favorite: bool = False,
        great_rank: float | None = None,
        original_scan: str = "2026-01-01",
    ) -> dict:
        return {
            "pokemon_number": dex,
            "name": name,
            "form": None,
            "gender": "Male",
            "cp": cp,
            "hp": 100,
            "ivs": {
                "attack": attack,
                "defense": defense,
                "stamina": stamina,
                "average_percent": round((attack + defense + stamina) / 45 * 100, 1),
                "total": attack + defense + stamina,
                "is_hundo": attack == defense == stamina == 15,
                "is_nundo": attack == defense == stamina == 0,
            },
            "level": {"minimum": 20.0, "maximum": 20.0},
            "moves": {"fast": "Tackle", "charged": "Struggle", "charged_second": None},
            "dates": {"scan": "2026-08-13", "original_scan": original_scan, "catch": "2026-01-01"},
            "size": {"weight": 1.0, "height": 1.0},
            "status": {
                "lucky": lucky,
                "shadow_purified": status,
                "favorite": favorite,
                "marked_for_pvp": False,
            },
            "dust": 2500,
            "pvp": {
                "great": {"rank_percent": great_rank},
                "ultra": {"rank_percent": None},
                "little": {"rank_percent": None},
            },
            "identity": {
                "record_id": record_id,
                "record_fingerprint": fingerprint,
                "fingerprint_confidence": "high",
            },
        }

    def _fixture(self, root: Path) -> tuple[Path, dict, list[dict]]:
        output = root / "dist"
        data = output / "data"
        knowledge = data / "knowledge"
        knowledge.mkdir(parents=True)
        manifest = {
            "build_id": "abcdef123456",
            "source_file": "exports/shared-text-2026-08-13 22_11_01.704.csv",
            "export_timestamp": "2026-08-13T22:11:01.704",
            "normalized_record_count": 3,
        }
        records = [
            self._record(
                "pgc_00000000000000000001",
                "fp_00000000000000000001",
                dex=1,
                name="Bulbasaur",
                cp=500,
                attack=15,
                defense=15,
                stamina=15,
                favorite=True,
            ),
            self._record(
                "pgc_00000000000000000002",
                "fp_00000000000000000002",
                dex=1,
                name="Bulbasaur",
                cp=450,
                attack=0,
                defense=0,
                stamina=0,
                status="shadow",
                great_rank=99.4,
            ),
            self._record(
                "pgc_00000000000000000003",
                "fp_00000000000000000003",
                dex=2,
                name="Ivysaur",
                cp=900,
                attack=10,
                defense=12,
                stamina=13,
                lucky=True,
            ),
        ]
        (data / "pokemon.json").write_text(
            json.dumps({"manifest": manifest, "records": records}) + "\n",
            encoding="utf-8",
        )
        (knowledge / "species-index.json").write_text(
            json.dumps(
                {
                    "dataset_version": "fixture-1",
                    "entries": [
                        {
                            "dex": 1,
                            "species_id": "BULBASAUR",
                            "display_name": "Bulbasaur",
                            "form_key": "Normal",
                            "family_id": "family-bulbasaur",
                        },
                        {
                            "dex": 2,
                            "species_id": "IVYSAUR",
                            "display_name": "Ivysaur",
                            "form_key": "Normal",
                            "family_id": "family-bulbasaur",
                        },
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (data / "scan-quality-report.json").write_text(
            json.dumps(
                {
                    "findings": [
                        {
                            "record_id": "pgc_00000000000000000002",
                            "suggested_action": "rescan",
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return output, manifest, records

    def test_species_family_and_views_preserve_exact_owned_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, manifest, records = self._fixture(Path(temporary))
            resources = publish_species_family_resources(output, manifest)
            views = publish_derived_views(output, manifest)

            self.assertEqual(resources["species"]["species_count"], 2)
            self.assertEqual(sum(item["owned_count"] for item in resources["species"]["entries"]), 3)
            self.assertEqual(resources["families"]["family_count"], 1)
            family_path = output / resources["families"]["entries"][0]["path"]
            family = json.loads(family_path.read_text(encoding="utf-8"))
            self.assertEqual({record["name"] for record in family["records"]}, {"Bulbasaur", "Ivysaur"})

            indexed = {entry["name"]: entry for entry in views["entries"]}
            self.assertEqual(indexed["hundos"]["record_count"], 1)
            self.assertEqual(indexed["nundos"]["record_count"], 1)
            self.assertEqual(indexed["shadow"]["record_count"], 1)
            self.assertEqual(indexed["great-league-candidates"]["record_count"], 1)
            self.assertEqual(indexed["needs-rescan"]["record_count"], 1)
            self.assertEqual(indexed["legendary"]["status"], "unavailable")
            self.assertIsNone(indexed["legendary"]["path"])

            rescan = json.loads((output / indexed["needs-rescan"]["path"]).read_text(encoding="utf-8"))
            self.assertEqual(rescan["record_ids"], [records[1]["identity"]["record_id"]])

    def test_diff_tracks_unique_fingerprint_state_change(self) -> None:
        before = self._record(
            "pgc_00000000000000000010",
            "fp_00000000000000000010",
            dex=1,
            name="Bulbasaur",
            cp=500,
            attack=10,
            defense=10,
            stamina=10,
        )
        after = json.loads(json.dumps(before))
        after["record_id"] = "pgc_00000000000000000011"
        after["cp"] = 700
        previous = {"build_id": "111111111111", "records": [before]}
        current = {"build_id": "222222222222", "records": [after]}

        diff = _diff_snapshots(previous, current)
        self.assertEqual(diff["summary"], {"added": 0, "removed": 0, "changed": 1, "ambiguous": 0})
        self.assertIn("level_or_cp", diff["changed"][0]["change_kinds"])
        self.assertEqual(diff["changed"][0]["match"], "fingerprint")

    def test_diff_uses_conservative_secondary_key_when_fingerprint_changes(self) -> None:
        before = self._record(
            "pgc_00000000000000000020",
            "fp_00000000000000000020",
            dex=1,
            name="Bulbasaur",
            cp=500,
            attack=10,
            defense=10,
            stamina=10,
        )
        after = json.loads(json.dumps(before))
        after["record_id"] = "pgc_00000000000000000021"
        after["record_fingerprint"] = "fp_00000000000000000021"
        after["cp"] = 750
        previous = {"build_id": "111111111111", "records": [before]}
        current = {"build_id": "222222222222", "records": [after]}

        diff = _diff_snapshots(previous, current)
        self.assertEqual(diff["summary"], {"added": 0, "removed": 0, "changed": 1, "ambiguous": 0})
        self.assertEqual(diff["changed"][0]["match"], "stable_secondary_key")
        self.assertEqual(diff["changed"][0]["confidence"], "medium")

    def test_static_api_exposes_generated_selective_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, manifest, _records = self._fixture(Path(temporary))
            publish_species_family_resources(output, manifest)
            publish_derived_views(output, manifest)
            (output / "data" / "collection-diff.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "from_build_id": None,
                        "to_build_id": manifest["build_id"],
                        "summary": {"added": 3, "removed": 0, "changed": 0, "ambiguous": 0},
                        "added": [],
                        "removed": [],
                        "changed": [],
                        "ambiguous": [],
                        "wording": "fixture",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (output / "data" / "build-manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")

            publish_static_api(output, manifest)
            validate_static_api(output)
            self.assertTrue((output / "api" / "v1" / "species" / "001.json").is_file())
            self.assertTrue((output / "api" / "v1" / "families" / "001.json").is_file())
            self.assertTrue((output / "api" / "v1" / "views" / "hundos.json").is_file())


if __name__ == "__main__":
    unittest.main()
