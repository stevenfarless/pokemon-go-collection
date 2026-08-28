#!/usr/bin/env python3
"""Enforce the project's permanent zero-cost, GitHub-only core architecture."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable

FORBIDDEN_RUNTIME_PACKAGES = {
    "firebase",
    "firebase-admin",
    "@supabase/supabase-js",
    "supabase",
    "algoliasearch",
    "pinecone",
    "pinecone-client",
}
FORBIDDEN_RUNTIME_PATTERNS = (
    re.compile(r"\bfirebase(?:app)?\.com\b", re.IGNORECASE),
    re.compile(r"\bsupabase\.co\b", re.IGNORECASE),
    re.compile(r"\balgolia(?:search)?\b", re.IGNORECASE),
    re.compile(r"\bapi\.openai\.com\b", re.IGNORECASE),
    re.compile(r"\bapi\.anthropic\.com\b", re.IGNORECASE),
)
SOURCE_SUFFIXES = {".js", ".mjs", ".py", ".html", ".css"}
SOURCE_ROOTS = ("site", "scripts")
SELF_PATH = Path("scripts/check_architecture.py")


def _iter_runtime_source(root: Path) -> Iterable[Path]:
    for directory in SOURCE_ROOTS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            if path.relative_to(root) == SELF_PATH:
                continue
            yield path


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def check_package_json(root: Path) -> list[str]:
    errors: list[str] = []
    payload = _load_json(root / "package.json")
    dependencies = payload.get("dependencies", {})
    forbidden = {item.casefold() for item in FORBIDDEN_RUNTIME_PACKAGES}
    for package in sorted(dependencies):
        if package.casefold() in forbidden:
            errors.append(f"package.json requires disallowed runtime dependency {package!r}")
    return errors


def check_python_requirements(root: Path) -> list[str]:
    errors: list[str] = []
    forbidden = {item.casefold() for item in FORBIDDEN_RUNTIME_PACKAGES}
    for path in sorted(root.glob("requirements*.txt")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            requirement = line.strip()
            if not requirement or requirement.startswith("#"):
                continue
            package = re.split(r"[<>=!~\[\s]", requirement, maxsplit=1)[0].casefold()
            if package in forbidden:
                errors.append(
                    f"{path.relative_to(root)}:{line_number} requires disallowed runtime dependency {package!r}"
                )
    return errors


def check_runtime_sources(root: Path) -> list[str]:
    errors: list[str] = []
    for path in _iter_runtime_source(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FORBIDDEN_RUNTIME_PATTERNS:
            match = pattern.search(text)
            if match:
                errors.append(
                    f"{path.relative_to(root)} contains required-backend indicator {match.group(0)!r}"
                )
    return errors


def check_workflow_secrets(root: Path) -> list[str]:
    """Core workflows must not depend on owner-provisioned secrets."""
    errors: list[str] = []
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return errors
    secret_pattern = re.compile(r"\$\{\{\s*secrets\.[A-Za-z0-9_]+\s*\}\}")
    for path in sorted(workflow_dir.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in secret_pattern.finditer(text):
            errors.append(
                f"{path.relative_to(root)} requires owner-provisioned secret [REDACTED]"
            )
    return errors


def check_required_files(root: Path) -> list[str]:
    required = (
        Path("docs/architecture.md"),
        Path("docs/fork-bootstrap.md"),
        Path("docs/deployment-safety.md"),
        Path(".github/workflows/deploy-pages.yml"),
        Path(".github/workflows/bootstrap-self-test.yml"),
        Path(".github/workflows/rollback-pages.yml"),
        Path(".github/workflows/sync-knowledge.yml"),
        Path("scripts/build_dashboard.py"),
        Path("scripts/bootstrap_self_test.py"),
        Path("scripts/deployment_guard.py"),
        Path("scripts/sync_knowledge.py"),
        Path("knowledge/source-lock.json"),
        Path("knowledge/pokemon-go.json"),
        Path("knowledge/pokemon-go.schema.json"),
        Path("knowledge/species-index.json"),
        Path("knowledge/species-index.schema.json"),
        Path("knowledge/PVPOKE-LICENSE.txt"),
        Path("exports/README.md"),
    )
    return [
        f"required zero-cost architecture file is missing: {path}"
        for path in required
        if not (root / path).is_file()
    ]


def check(root: Path) -> list[str]:
    errors: list[str] = []
    errors.extend(check_required_files(root))
    errors.extend(check_package_json(root))
    errors.extend(check_python_requirements(root))
    errors.extend(check_runtime_sources(root))
    errors.extend(check_workflow_secrets(root))
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = check(root)
    if errors:
        print("Zero-cost architecture check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Zero-cost architecture check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
