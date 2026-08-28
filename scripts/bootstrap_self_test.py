#!/usr/bin/env python3
"""Actionable self-test for a fresh GitHub fork of the collection companion."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from . import build_collection, build_site, check_architecture
    from .knowledge_validation import load_repository_knowledge
except ImportError:
    import build_collection
    import build_site
    import check_architecture
    from knowledge_validation import load_repository_knowledge


REQUIRED_PATHS = (
    ".github/workflows/deploy-pages.yml",
    ".github/workflows/bootstrap-self-test.yml",
    ".github/workflows/sync-knowledge.yml",
    "scripts/build_dashboard.py",
    "scripts/validate_generated.py",
    "scripts/deployment_guard.py",
    "scripts/sync_knowledge.py",
    "knowledge/source-lock.json",
    "knowledge/pokemon-go.json",
    "knowledge/pokemon-go.schema.json",
    "knowledge/species-index.json",
    "knowledge/species-index.schema.json",
    "knowledge/PVPOKE-LICENSE.txt",
    "requirements-dev.txt",
    "package.json",
    "package-lock.json",
)


_SECRET_REF_PATTERN = re.compile(r"\$\{\{\s*secrets\.[A-Za-z0-9_]+\s*\}\}")


def _redact_secret_refs(text: str) -> str:
    return _SECRET_REF_PATTERN.sub("${{ secrets.REDACTED }}", text)


def _sanitize_for_output(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_secret_refs(value)
    if isinstance(value, list):
        return [_sanitize_for_output(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_for_output(item) for key, item in value.items()}
    return value


def evaluate(repository_root: Path, *, require_export: bool = True) -> dict[str, Any]:
    root = repository_root.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    for relative in REQUIRED_PATHS:
        if not (root / relative).is_file():
            errors.append(f"Missing required project file: {relative}")

    architecture_errors = check_architecture.check(root)
    errors.extend(f"Architecture policy: {message}" for message in architecture_errors)

    if all((root / relative).is_file() for relative in (
        "knowledge/source-lock.json",
        "knowledge/pokemon-go.json",
        "knowledge/pokemon-go.schema.json",
    )):
        try:
            load_repository_knowledge(root)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"Pokémon GO knowledge snapshot is not synchronized/valid: {exc}")

    export_dir = root / "exports"
    csv_paths = sorted(export_dir.rglob("*.csv")) if export_dir.is_dir() else []
    parsed = [build_site.parse_export_filename(path) for path in csv_paths]
    invalid = [path for path, item in zip(csv_paths, parsed) if item is None]
    exports = build_collection.discover_exports(root)

    if invalid:
        message = (
            "Ignored CSV files under exports/ whose names do not match the supported Poke Genie archive "
            "pattern shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv: "
            + ", ".join(path.name for path in invalid[:8])
        )
        if require_export and not exports:
            errors.append(
                message
                + ". Upload at least one valid Poke Genie export without renaming it."
            )
        else:
            warnings.append(message)

    if require_export and not exports and not invalid:
        errors.append(
            "No valid Poke Genie export found. Upload the exported CSV to exports/ without renaming it."
        )
    if exports:
        newest_timestamp = exports[-1].timestamp
        newest = [item for item in exports if item.timestamp == newest_timestamp]
        if len(newest) > 1:
            errors.append(
                "More than one export has the newest filename timestamp; remove or rename the accidental duplicate."
            )

    deploy_path = root / ".github" / "workflows" / "deploy-pages.yml"
    if deploy_path.is_file():
        deploy = deploy_path.read_text(encoding="utf-8")
        required_fragments = (
            "pages: write",
            "id-token: write",
            "actions/upload-pages-artifact@",
            "actions/deploy-pages@",
            "scripts/deployment_guard.py",
        )
        for fragment in required_fragments:
            if fragment not in deploy:
                errors.append(f"Deployment workflow is missing expected configuration: {fragment}")

    if not (root / ".github" / "workflows" / "rollback-pages.yml").is_file():
        warnings.append(
            "Rollback workflow is not present. A fork can still deploy, but last-known-good manual rollback is unavailable."
        )

    newest_export = exports[-1].path.relative_to(root).as_posix() if exports else None
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "valid_export_count": len(exports),
        "newest_export": newest_export,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a fork is ready to build and deploy")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--allow-missing-export", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    result = evaluate(args.root, require_export=not args.allow_missing_export)
    if args.as_json:
        safe_result = _sanitize_for_output(result)
        print(json.dumps(safe_result, ensure_ascii=False, indent=2))
    else:
        if result["errors"]:
            print("Bootstrap self-test failed:", file=sys.stderr)
            for error in result["errors"]:
                print(f"- {error}", file=sys.stderr)
        else:
            print(
                f"Bootstrap self-test passed. Valid exports: {result['valid_export_count']}; "
                f"newest: {result['newest_export']}"
            )
        for warning in result["warnings"]:
            print(f"Warning: {warning}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
