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


def _fingerprint(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "pokemon-go-collection-mechanics-review/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:  # noqa: S310 - fixed reviewed HTTPS URLs
        raw = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    normalized = re.sub(r"\s+", " ", raw).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def check(registry_path: Path, state_path: Path) -> dict:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {"schema_version": 1, "sources": {}}
    results = []
    for source in registry.get("sources", []):
        if not source.get("watch"):
            continue
        source_id = source["id"]
        previous = (state.get("sources") or {}).get(source_id, {}).get("sha256")
        try:
            current = _fingerprint(source["url"])
            status = "baseline-missing" if not previous else ("changed" if current != previous else "unchanged")
            results.append({"id": source_id, "url": source["url"], "status": status, "previous_sha256": previous, "current_sha256": current})
        except (OSError, UnicodeError, urllib.error.URLError) as error:
            results.append({"id": source_id, "url": source["url"], "status": "fetch-failed", "error": str(error)[:300]})
    actionable = [item for item in results if item["status"] in {"changed", "baseline-missing", "fetch-failed"}]
    return {"schema_version": 1, "checked_sources": len(results), "actionable_count": len(actionable), "results": results}


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
