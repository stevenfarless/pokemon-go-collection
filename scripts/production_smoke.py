#!/usr/bin/env python3
"""Bounded post-deployment verification for the public GitHub Pages collection site."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SmokeResult:
    build_id: str
    record_count: int
    first_shard: str
    last_shard: str
    external_snapshot_count: int


def _url(base_url: str, path: str, expected_build_id: str) -> str:
    base = base_url.rstrip("/") + "/"
    separator = "&" if "?" in path else "?"
    return base + path.lstrip("/") + f"{separator}verify={expected_build_id}"


def network_json(base_url: str, path: str, expected_build_id: str) -> Any:
    request = urllib.request.Request(
        _url(base_url, path, expected_build_id),
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache", "User-Agent": "pokemon-go-collection-production-smoke/1"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"{path} returned HTTP {response.status}")
        return json.load(response)


def network_text(base_url: str, path: str, expected_build_id: str) -> str:
    request = urllib.request.Request(
        _url(base_url, path, expected_build_id),
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache", "User-Agent": "pokemon-go-collection-production-smoke/1"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"{path} returned HTTP {response.status}")
        return response.read().decode("utf-8")


def verify_once(
    base_url: str,
    expected_build_id: str,
    *,
    get_json: Callable[[str, str, str], Any] = network_json,
    get_text: Callable[[str, str, str], str] = network_text,
) -> SmokeResult:
    """Verify deployed static routes and coordinated-build machine contracts once."""
    for path in ("", "insights.html", "tools.html", "manifest.webmanifest", "sw.js"):
        text = get_text(base_url, path, expected_build_id)
        if not text.strip():
            raise RuntimeError(f"{path or '/'} returned an empty response")
    tools = get_text(base_url, "tools.html", expected_build_id)
    if 'id="local-data-backup"' not in tools or 'id="enrichment"' not in tools:
        raise RuntimeError("tools.html is missing the local-data/enrichment production controls")
    root = get_text(base_url, "", expected_build_id)
    if 'href="tools.html"' not in root or 'href="insights.html"' not in root:
        raise RuntimeError("root collection navigation is missing Tools or Insights")

    bootstrap = get_json(base_url, "data/llm-bootstrap.json", expected_build_id)
    manifest = get_json(base_url, "data/build-manifest.json", expected_build_id)
    shard_index = get_json(base_url, "data/pokemon-index.json", expected_build_id)
    pokemon = get_json(base_url, "data/pokemon.json", expected_build_id)
    api_index = get_json(base_url, "api/v1/index.json", expected_build_id)
    api_manifest = get_json(base_url, "api/v1/manifest.json", expected_build_id)
    candidates = get_json(base_url, "data/candidates/index.json", expected_build_id)
    investments = get_json(base_url, "data/investments/records.json", expected_build_id)
    external = get_json(base_url, "data/external/index.json", expected_build_id)

    build_ids = {
        str(bootstrap.get("build_id") or ""),
        str(manifest.get("build_id") or ""),
        str(shard_index.get("build_id") or ""),
        str((pokemon.get("manifest") or {}).get("build_id") or ""),
        str(api_manifest.get("build_id") or ""),
        str(candidates.get("build_id") or ""),
        str(investments.get("build_id") or ""),
        str(external.get("build_id") or ""),
    }
    if build_ids != {expected_build_id}:
        raise RuntimeError(f"deployed build IDs {sorted(build_ids)} do not equal expected {expected_build_id}")

    record_count = int(manifest.get("normalized_record_count") or 0)
    if record_count <= 0:
        raise RuntimeError("deployed manifest has no normalized records")
    counts = {
        int(bootstrap.get("normalized_record_count") or 0),
        int(shard_index.get("normalized_record_count") or 0),
        len(pokemon.get("records") or []),
        int(investments.get("record_count") or 0),
    }
    if counts != {record_count}:
        raise RuntimeError(f"deployed record counts disagree: {sorted(counts)} vs manifest {record_count}")

    shards = shard_index.get("shards") or []
    if not shards:
        raise RuntimeError("deployed shard index is empty")
    first_path = str(shards[0].get("path") or "")
    last_path = str(shards[-1].get("path") or "")
    for path in (first_path, last_path):
        if not path:
            raise RuntimeError("deployed shard index contains a blank shard path")
        shard = get_json(base_url, path, expected_build_id)
        if shard.get("build_id") != expected_build_id or not shard.get("records"):
            raise RuntimeError(f"invalid deployed shard {path}")

    endpoints = api_index.get("endpoints") or {}
    serialized_api = json.dumps(endpoints, sort_keys=True)
    if "manifest" not in serialized_api or "species" not in serialized_api:
        raise RuntimeError("api/v1/index.json is missing required discovery paths")

    snapshots = external.get("snapshots") or []
    for item in snapshots:
        path = item.get("path")
        if path:
            snapshot = get_json(base_url, str(path), expected_build_id)
            if snapshot.get("build_id") != expected_build_id:
                raise RuntimeError(f"external snapshot {path} belongs to a different build")

    return SmokeResult(
        build_id=expected_build_id,
        record_count=record_count,
        first_shard=first_path,
        last_shard=last_path,
        external_snapshot_count=len(snapshots),
    )


def verify_with_retry(
    base_url: str,
    expected_build_id: str,
    *,
    attempts: int = 12,
    delay_seconds: float = 10.0,
    get_json: Callable[[str, str, str], Any] = network_json,
    get_text: Callable[[str, str, str], str] = network_text,
    sleep: Callable[[float], None] = time.sleep,
) -> SmokeResult:
    """Retry only for a bounded propagation window, never accepting the wrong build."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return verify_once(base_url, expected_build_id, get_json=get_json, get_text=get_text)
        except (RuntimeError, OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as error:
            last_error = error
            if attempt == attempts:
                break
            sleep(delay_seconds)
    raise RuntimeError(f"production smoke failed after {attempts} attempts: {last_error}") from last_error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-build-id", required=True)
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--delay-seconds", type=float, default=10.0)
    args = parser.parse_args()
    result = verify_with_retry(
        args.base_url,
        args.expected_build_id,
        attempts=max(1, args.attempts),
        delay_seconds=max(0, args.delay_seconds),
    )
    print(
        f"Verified deployed build {result.build_id}: {result.record_count} records, "
        f"shards {result.first_shard} .. {result.last_shard}, "
        f"{result.external_snapshot_count} external snapshots"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
