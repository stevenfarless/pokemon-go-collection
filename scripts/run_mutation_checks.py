#!/usr/bin/env python3
"""Run a small deterministic mutation suite over safety-critical build logic."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Mutation:
    name: str
    path: str
    old: str
    new: str
    test_pattern: str


MUTATIONS = (
    Mutation(
        "asset_hash_width",
        "scripts/build_collection.py",
        'return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]',
        'return hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]',
        "test_build_collection.py",
    ),
    Mutation(
        "required_column_guard",
        "scripts/build_collection.py",
        "        if missing_required:\n            raise ValueError",
        "        if not missing_required:\n            raise ValueError",
        "test_build_collection.py",
    ),
    Mutation(
        "hidden_export_guard",
        "scripts/build_collection.py",
        '        if any(part.startswith(".") for part in relative_directories):\n            continue',
        '        if not any(part.startswith(".") for part in relative_directories):\n            continue',
        "test_build_collection.py",
    ),
)


def copy_test_tree(destination: Path) -> None:
    shutil.copytree(ROOT / "scripts", destination / "scripts")
    shutil.copytree(ROOT / "tests", destination / "tests")


def apply_mutation(root: Path, mutation: Mutation) -> None:
    target = root / mutation.path
    source = target.read_text(encoding="utf-8")
    if source.count(mutation.old) != 1:
        raise RuntimeError(f"mutation anchor {mutation.name!r} is no longer unique")
    target.write_text(source.replace(mutation.old, mutation.new, 1), encoding="utf-8", newline="\n")


def mutant_is_killed(mutation: Mutation) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="pokemon-go-mutant-") as temp_dir:
        work = Path(temp_dir)
        copy_test_tree(work)
        apply_mutation(work, mutation)
        command = [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            mutation.test_pattern,
            "-v",
        ]
        completed = subprocess.run(
            command,
            cwd=work,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        return completed.returncode != 0, completed.stdout


def main() -> int:
    survivors: list[str] = []
    for mutation in MUTATIONS:
        killed, output = mutant_is_killed(mutation)
        status = "KILLED" if killed else "SURVIVED"
        print(f"[{status}] {mutation.name}")
        if not killed:
            survivors.append(mutation.name)
            print(output)
    if survivors:
        print("Surviving mutations: " + ", ".join(survivors), file=sys.stderr)
        return 1
    print(f"Mutation score: {len(MUTATIONS)}/{len(MUTATIONS)} killed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
