#!/usr/bin/env python3
"""Detect source-page changes without copying source prose into the repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

FINGERPRINT_VERSION = 2


def _content_scope(raw: str) -> str:
    """Prefer article/main content so site-wide chrome changes do not trigger reviews."""
    for tag in ("article", "main"):
        match = re.search(rf"(?is)<{tag}\b[^>]*>(.*?)</{tag}>", raw)
        if match:
            return match.group(1)
    return raw


def _normalize_html(raw: str) -> str:
    raw = _content_scope(raw)
    raw = re.sub(r"(?is)<(script|style|noscript|template).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def _fingerprint_html(raw: str) -> str:
    normalized = _normalize_html(raw)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _fingerprint(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "pokemon-go-collection-mechanics-review/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:  # noqa: S310 - fixed reviewed HTTPS URLs
        raw = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    return _fingerprint_html(raw)


def _source_status(previous: str | None, current: str, state_fingerprint_version: int) -> str:
    if not previous:
        return "baseline-missing"
    if state_fingerprint_version != FINGERPRINT_VERSION:
        return "baseline-algorithm-changed"
    return "changed" if current != previous else "unchanged"


def check(registry_path: Path, state_path: Path) -> dict:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {"schema_version": 1, "sources": {}}
    state_fingerprint_version = state.get("fingerprint_version", 1)
    results = []
    for source in registry.get("sources", []):
        if not source.get("watch"):
            continue
        source_id = source["id"]
        previous = (state.get("sources") or {}).get(source_id, {}).get("sha256")
        try:
            current = _fingerprint(source["url"])
            status = _source_status(previous, current, state_fingerprint_version)
            results.append({"id": source_id, "url": source["url"], "status": status, "previous_sha256": previous, "current_sha256": current})
        except (OSError, UnicodeError, urllib.error.URLError) as error:
            results.append({"id": source_id, "url": source["url"], "status": "fetch-failed", "error": str(error)[:300]})
    actionable_statuses = {"changed", "baseline-missing", "baseline-algorithm-changed", "fetch-failed"}
    actionable = [item for item in results if item["status"] in actionable_statuses]
    return {
        "schema_version": 1,
        "fingerprint_version": FINGERPRINT_VERSION,
        "checked_sources": len(results),
        "actionable_count": len(actionable),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=Path("knowledge/mechanics-registry.json"))
    parser.add_argument("--state", type=Path, default=Path(".github/mechanics-source-state.json"))
    parser.add_argument("--output", type=Path, default=Path("mechanics-source-change-report.json"))
    args = parser.parse_args()
    report = check(args.registry, args.state)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checked_sources": report["checked_sources"], "actionable_count": report["actionable_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
