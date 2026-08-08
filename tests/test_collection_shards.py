from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.collection_shards import (
    HARD_MAX_BYTES,
    publish_collection_shards,
    validate_collection_shards,
)


class CollectionShardTests(unittest.TestCase):
    def _fixture(self, root: Path, count: int = 80) -> tuple[Path, dict, list[dict]]:
        output = root / "dist"
        data = output / "data"
        data.mkdir(parents=True)
        records = []
        for number in range(count):
            records.append(
                {
                    "pokemon_number": 25,
                    "name": "Pikachu",
                    "cp": 500 + number,
                    "identity": {
                        "record_id": f"pgc_{number:020x}",
                    },
                    "padding": "x" * 120,
                }
            )
        manifest = {
            "build_id": "abcdef123456",
            "schema_version": "2.0.0",
            "normalized_record_count": len(records),
            "pokemon_count": len(records),
        }
        (data / "pokemon.json").write_text(
            json.dumps({"manifest": manifest, "records": records}, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return output, manifest, records

    def test_bounded_shards_reconstruct_canonical_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, manifest, records = self._fixture(Path(temporary))
            index = publish_collection_shards(output, manifest, target_bytes=4_000)
            self.assertGreater(index["shard_count"], 1)
            self.assertEqual(sum(item["record_count"] for item in index["shards"]), len(records))
            self.assertTrue(all(item["byte_size"] <= HARD_MAX_BYTES for item in index["shards"]))
            validate_collection_shards(output)

            reconstructed = []
            for entry in index["shards"]:
                shard = json.loads((output / entry["path"]).read_text(encoding="utf-8"))
                reconstructed.extend(shard["records"])
            self.assertEqual(reconstructed, records)

    def test_regeneration_removes_stale_shards(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, manifest, _records = self._fixture(Path(temporary))
            publish_collection_shards(output, manifest, target_bytes=4_000)
            stale = output / "data" / "pokemon" / "chunk-9999.json"
            stale.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Stale or undeclared"):
                validate_collection_shards(output)

            publish_collection_shards(output, manifest, target_bytes=4_000)
            self.assertFalse(stale.exists())
            validate_collection_shards(output)

    def test_missing_shard_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, manifest, _records = self._fixture(Path(temporary))
            index = publish_collection_shards(output, manifest, target_bytes=4_000)
            (output / index["shards"][0]["path"]).unlink()
            with self.assertRaisesRegex(ValueError, "missing file"):
                validate_collection_shards(output)

    def test_tampered_shard_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, manifest, _records = self._fixture(Path(temporary))
            index = publish_collection_shards(output, manifest, target_bytes=4_000)
            path = output / index["shards"][0]["path"]
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["records"].append(payload["records"][0])
            path.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "byte-size invariant"):
                validate_collection_shards(output)


if __name__ == "__main__":
    unittest.main()
