from __future__ import annotations

import unittest

from scripts.production_smoke import verify_once, verify_with_retry


EXPECTED = "0123456789ab"
COUNT = 2


def payloads(build_id: str = EXPECTED):
    return {
        "data/llm-bootstrap.json": {"build_id": build_id, "normalized_record_count": COUNT},
        "data/build-manifest.json": {"build_id": build_id, "normalized_record_count": COUNT},
        "data/pokemon-index.json": {
            "build_id": build_id,
            "normalized_record_count": COUNT,
            "shards": [{"path": "data/pokemon/chunk-0001.json"}, {"path": "data/pokemon/chunk-0002.json"}],
        },
        "data/pokemon.json": {"manifest": {"build_id": build_id}, "records": [{}, {}]},
        "api/v1/index.json": {"endpoints": {"manifest": "manifest.json", "species": "species/{dex}.json"}},
        "api/v1/manifest.json": {"build_id": build_id},
        "data/candidates/index.json": {"build_id": build_id},
        "data/investments/records.json": {"build_id": build_id, "record_count": COUNT},
        "data/external/index.json": {
            "build_id": build_id,
            "snapshots": [{"path": "data/external/snapshots/events.json"}],
        },
        "data/pokemon/chunk-0001.json": {"build_id": build_id, "records": [{}]},
        "data/pokemon/chunk-0002.json": {"build_id": build_id, "records": [{}]},
        "data/external/snapshots/events.json": {"build_id": build_id, "facts": [{}]},
    }


def text_payloads(include_tools: bool = True):
    return {
        "": '<a href="tools.html">Tools</a><a href="insights.html">Insights</a>',
        "insights.html": "insights",
        "tools.html": '<section id="enrichment"></section><section id="local-data-backup"></section>' if include_tools else "tools",
        "manifest.webmanifest": "{}",
        "sw.js": "self.addEventListener('fetch', () => {})",
    }


class ProductionSmokeTests(unittest.TestCase):
    def test_successful_deployed_verification(self) -> None:
        json_data = payloads()
        text_data = text_payloads()
        result = verify_once(
            "https://example.test/",
            EXPECTED,
            get_json=lambda _base, path, _expected: json_data[path],
            get_text=lambda _base, path, _expected: text_data[path],
        )
        self.assertEqual(result.build_id, EXPECTED)
        self.assertEqual(result.record_count, COUNT)
        self.assertEqual(result.external_snapshot_count, 1)

    def test_build_id_mismatch_fails(self) -> None:
        json_data = payloads()
        json_data["api/v1/manifest.json"] = {"build_id": "ffffffffffff"}
        with self.assertRaisesRegex(RuntimeError, "build IDs"):
            verify_once(
                "https://example.test/",
                EXPECTED,
                get_json=lambda _base, path, _expected: json_data[path],
                get_text=lambda _base, path, _expected: text_payloads()[path],
            )

    def test_missing_tools_controls_fail(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "tools.html"):
            verify_once(
                "https://example.test/",
                EXPECTED,
                get_json=lambda _base, path, _expected: payloads()[path],
                get_text=lambda _base, path, _expected: text_payloads(False)[path],
            )

    def test_missing_api_discovery_fails(self) -> None:
        json_data = payloads()
        json_data["api/v1/index.json"] = {"endpoints": {}}
        with self.assertRaisesRegex(RuntimeError, "api/v1/index"):
            verify_once(
                "https://example.test/",
                EXPECTED,
                get_json=lambda _base, path, _expected: json_data[path],
                get_text=lambda _base, path, _expected: text_payloads()[path],
            )

    def test_missing_deployed_shard_fails(self) -> None:
        json_data = payloads()
        del json_data["data/pokemon/chunk-0002.json"]

        def get_json(_base, path, _expected):
            if path not in json_data:
                raise RuntimeError(f"{path} returned HTTP 404")
            return json_data[path]

        with self.assertRaisesRegex(RuntimeError, "chunk-0002"):
            verify_once(
                "https://example.test/",
                EXPECTED,
                get_json=get_json,
                get_text=lambda _base, path, _expected: text_payloads()[path],
            )

    def test_propagation_retry_accepts_only_expected_build(self) -> None:
        attempts = {"count": 0}
        good = payloads()
        stale = payloads("aaaaaaaaaaaa")

        def get_json(_base, path, _expected):
            source = stale if attempts["count"] == 0 else good
            return source[path]

        def sleep(_seconds):
            attempts["count"] += 1

        result = verify_with_retry(
            "https://example.test/",
            EXPECTED,
            attempts=2,
            delay_seconds=0,
            get_json=get_json,
            get_text=lambda _base, path, _expected: text_payloads()[path],
            sleep=sleep,
        )
        self.assertEqual(result.build_id, EXPECTED)
        self.assertEqual(attempts["count"], 1)


if __name__ == "__main__":
    unittest.main()
