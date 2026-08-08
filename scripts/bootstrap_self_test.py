#!/usr/bin/env python3
"""Actionable self-test for a fresh GitHub fork of the collection companion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from . import build_collection, build_site, check_architecture
except ImportError:
    import build_collection
    import build_site
    import check_architecture


REQUIRED_PATHS = (
    ".github/workflows/deploy-pages.yml",
    ".github/workflows/validate.yml",
    ".github/workflows/bootstrap-self-test.yml",
    "scripts/build_dashboard.py",
    "scripts/validate_generated.py",
    "scripts/deployment_guard.py",
    "requirements-dev.txt",
    "package.json",
    "package-lock.json",
)


def evaluate(repository_root: Path, *, require_export: bool = True) -> dict[str, Any]:
    root = repository_root.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    for relative in REQUIRED_PATHS:
        if not (root / relative).is_file():
            errors.append(f"Missing required project file: {relative}")

    architecture_errors = check_architecture.check(root)
    errors.extend(f"Architecture policy: {message}" for message in architecture_errors)

    export_dir = root / "exports"
    csv_paths = sorted(export_dir.rglob("*.csv")) if export_dir.is_dir() else []
    parsed = [build_site.parse_export_filename(path) for path in csv_paths]
    invalid = [path for path, item in zip(csv_paths, parsed) if item is None]
    if invalid:
        errors.append(
            "CSV files under exports/ must keep the exact Poke Genie archive name "
            "shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv: "
            + ", ".join(path.name for path in invalid[:8])
        )

    exports = build_collection.discover_exports(root)
    if require_export and not exports:
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

    validate_path = root / ".github" / "workflows" / "validate.yml"
    if validate_path.is_file():
        validate = validate_path.read_text(encoding="utf-8")
        if "scripts/validate_generated.py" not in validate:
            errors.append("Validation workflow does not enforce generated JSON contracts")

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
        print(json.dumps(result, ensure_ascii=False, indent=2))
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
