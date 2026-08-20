#!/usr/bin/env python3
"""Enforce static generated-resource size budgets and write a reviewable report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def generated_files(dist: Path, suffix: str) -> list[Path]:
    return sorted(path for path in dist.rglob(f"*{suffix}") if path.is_file())


def bytes_total(paths: list[Path]) -> int:
    return sum(path.stat().st_size for path in paths)


def relative_size(path: Path, dist: Path) -> dict[str, Any]:
    return {"path": path.relative_to(dist).as_posix(), "bytes": path.stat().st_size}


def index_assets(dist: Path, suffix: str) -> list[Path]:
    html = (dist / "index.html").read_text(encoding="utf-8")
    return [path for path in generated_files(dist / "assets", suffix) if path.name in html]


def evaluate(dist: Path, budget_path: Path) -> tuple[dict[str, Any], list[str]]:
    config = load_json(budget_path)
    limits = config["assets"]
    js_files = generated_files(dist / "assets", ".js")
    css_files = generated_files(dist / "assets", ".css")
    index_js = index_assets(dist, ".js")
    index_css = index_assets(dist, ".css")
    pokemon_json = dist / "data" / "pokemon.json"
    all_files = [path for path in dist.rglob("*") if path.is_file()]
    largest = max(all_files, key=lambda path: path.stat().st_size)

    metrics = {
        "initial_index_javascript_bytes": bytes_total(index_js),
        "initial_index_css_bytes": bytes_total(index_css),
        "all_javascript_bytes": bytes_total(js_files),
        "all_css_bytes": bytes_total(css_files),
        "pokemon_json_bytes": pokemon_json.stat().st_size,
        "largest_generated_resource": relative_size(largest, dist),
        "index_javascript": [relative_size(path, dist) for path in index_js],
        "index_css": [relative_size(path, dist) for path in index_css],
    }
    checks = {
        "initial_index_javascript_bytes": limits["initial_index_javascript_bytes_max"],
        "initial_index_css_bytes": limits["initial_index_css_bytes_max"],
        "all_javascript_bytes": limits["all_javascript_bytes_max"],
        "all_css_bytes": limits["all_css_bytes_max"],
        "pokemon_json_bytes": limits["pokemon_json_bytes_max"],
    }
    failures = [
        f"{name}={metrics[name]} exceeds {limit}"
        for name, limit in checks.items()
        if metrics[name] > limit
    ]
    if largest.stat().st_size > limits["single_generated_resource_bytes_max"]:
        failures.append(
            f"largest resource {metrics['largest_generated_resource']['path']}={largest.stat().st_size} "
            f"exceeds {limits['single_generated_resource_bytes_max']}"
        )
    report = {
        "budget_version": config["version"],
        "metrics": metrics,
        "limits": limits,
        "failures": failures,
        "status": "pass" if not failures else "fail",
    }
    return report, failures


def write_report(report: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "static-budget.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    rows = [
        "# Static performance budgets",
        "",
        f"Status: **{report['status'].upper()}**",
        "",
        "| Metric | Current bytes | Limit bytes |",
        "| --- | ---: | ---: |",
    ]
    for name, limit_key in (
        ("initial_index_javascript_bytes", "initial_index_javascript_bytes_max"),
        ("initial_index_css_bytes", "initial_index_css_bytes_max"),
        ("all_javascript_bytes", "all_javascript_bytes_max"),
        ("all_css_bytes", "all_css_bytes_max"),
        ("pokemon_json_bytes", "pokemon_json_bytes_max"),
    ):
        rows.append(f"| {name} | {report['metrics'][name]} | {report['limits'][limit_key]} |")
    largest = report["metrics"]["largest_generated_resource"]
    rows.extend(["", f"Largest generated resource: `{largest['path']}` ({largest['bytes']} bytes)."])
    if report["failures"]:
        rows.extend(["", "Failures:", *[f"- {item}" for item in report["failures"]]])
    (output / "static-budget.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--budgets", type=Path, default=Path("config/performance-budgets.json"))
    parser.add_argument("--output", type=Path, default=Path("performance-results"))
    args = parser.parse_args()
    report, failures = evaluate(args.dist, args.budgets)
    write_report(report, args.output)
    print((args.output / "static-budget.md").read_text(encoding="utf-8"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
