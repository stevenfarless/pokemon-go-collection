#!/usr/bin/env python3
"""Build the static Pokémon GO collection site from the newest Poke Genie export."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

EXPORT_PATTERN = re.compile(
    r"^shared-text-(?P<date>\d{4}-\d{2}-\d{2}) "
    r"(?P<hour>\d{2})_(?P<minute>\d{2})_(?P<second>\d{2})\."
    r"(?P<millisecond>\d{3})\.csv$"
)

EXPECTED_COLUMNS = [
    "Index", "Name", "Form", "Pokemon Number", "Gender", "CP", "HP",
    "Atk IV", "Def IV", "Sta IV", "IV Avg", "Level Min", "Level Max",
    "Quick Move", "Charge Move", "Charge Move 2", "Scan Date",
    "Original Scan Date", "Catch Date", "Weight", "Height", "Lucky",
    "Shadow/Purified", "Favorite", "Dust", "Rank % (G)", "Rank # (G)",
    "Stat Prod (G)", "Dust Cost (G)", "Candy Cost (G)", "Name (G)",
    "Form (G)", "Sha/Pur (G)", "Rank % (U)", "Rank # (U)",
    "Stat Prod (U)", "Dust Cost (U)", "Candy Cost (U)", "Name (U)",
    "Form (U)", "Sha/Pur (U)", "Rank % (L)", "Rank # (L)",
    "Stat Prod (L)", "Dust Cost (L)", "Candy Cost (L)", "Name (L)",
    "Form (L)", "Sha/Pur (L)", "Marked for PvP use",
]

SKIP_DIRS = {".git", ".github", "dist", "site", "scripts", "tests", "__pycache__"}


@dataclass(frozen=True)
class ExportFile:
    path: Path
    timestamp: datetime


def parse_export_filename(path: Path) -> ExportFile | None:
    match = EXPORT_PATTERN.fullmatch(path.name)
    if not match:
        return None
    stamp = datetime.strptime(
        f"{match.group('date')} {match.group('hour')}:{match.group('minute')}:"
        f"{match.group('second')}.{match.group('millisecond')}",
        "%Y-%m-%d %H:%M:%S.%f",
    )
    return ExportFile(path=path, timestamp=stamp)


def discover_exports(repository_root: Path) -> list[ExportFile]:
    exports: list[ExportFile] = []
    for path in repository_root.rglob("*.csv"):
        relative_parts = path.relative_to(repository_root).parts[:-1]
        if any(part in SKIP_DIRS or part.startswith(".") for part in relative_parts):
            continue
        parsed = parse_export_filename(path)
        if parsed:
            exports.append(parsed)
    return sorted(exports, key=lambda item: (item.timestamp, item.path.as_posix()))


def select_latest_export(repository_root: Path) -> ExportFile:
    exports = discover_exports(repository_root)
    if not exports:
        raise ValueError(
            "No Poke Genie exports found. Expected a filename like "
            "shared-text-2026-08-05 23_24_00.336.csv"
        )
    newest_timestamp = exports[-1].timestamp
    newest = [item for item in exports if item.timestamp == newest_timestamp]
    if len(newest) > 1:
        paths = ", ".join(item.path.relative_to(repository_root).as_posix() for item in newest)
        raise ValueError(f"Multiple exports have the newest timestamp: {paths}")
    return newest[0]


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def number(value: str | None, *, integer: bool = False) -> int | float | None:
    value = clean(value)
    if value is None:
        return None
    try:
        parsed = float(value.replace(",", ""))
    except ValueError:
        return None
    if integer and parsed.is_integer():
        return int(parsed)
    return parsed


def percent(value: str | None) -> float | None:
    value = clean(value)
    if value is None:
        return None
    return number(value.removesuffix("%"))


def truthy(value: str | None) -> bool:
    return clean(value) in {"1", "true", "True", "TRUE", "yes", "Yes", "Y"}


def shadow_status(value: str | None) -> str:
    raw = clean(value)
    return {"1": "shadow", "2": "purified"}.get(raw, "normal")


def pvp_status(value: str | None) -> str | None:
    raw = clean(value)
    if raw is None:
        return None
    return {"0": "normal", "1": "shadow", "2": "purified"}.get(raw, raw)


def league_record(row: dict[str, str], code: str) -> dict[str, Any]:
    return {
        "rank_percent": percent(row.get(f"Rank % ({code})")),
        "rank_number": number(row.get(f"Rank # ({code})"), integer=True),
        "stat_product": number(row.get(f"Stat Prod ({code})")),
        "dust_cost": number(row.get(f"Dust Cost ({code})"), integer=True),
        "candy_cost": number(row.get(f"Candy Cost ({code})"), integer=True),
        "evolution_name": clean(row.get(f"Name ({code})")),
        "evolution_form": clean(row.get(f"Form ({code})")),
        "status": pvp_status(row.get(f"Sha/Pur ({code})")),
    }


def normalize_row(row: dict[str, str], row_number: int) -> dict[str, Any]:
    name = clean(row.get("Name"))
    dex_number = number(row.get("Pokemon Number"), integer=True)
    cp = number(row.get("CP"), integer=True)
    if name is None:
        raise ValueError(f"CSV row {row_number} has no Pokémon name")
    if dex_number is None:
        raise ValueError(f"CSV row {row_number} has an invalid Pokémon number")
    if cp is None:
        raise ValueError(f"CSV row {row_number} has an invalid CP value")

    attack = number(row.get("Atk IV"), integer=True)
    defense = number(row.get("Def IV"), integer=True)
    stamina = number(row.get("Sta IV"), integer=True)
    iv_average = number(row.get("IV Avg"))

    return {
        "source_index": number(row.get("Index"), integer=True),
        "name": name,
        "form": clean(row.get("Form")),
        "pokemon_number": dex_number,
        "gender": clean(row.get("Gender")),
        "cp": cp,
        "hp": number(row.get("HP"), integer=True),
        "ivs": {
            "attack": attack,
            "defense": defense,
            "stamina": stamina,
            "average_percent": iv_average,
            "total": sum(v for v in (attack, defense, stamina) if isinstance(v, (int, float)))
            if all(v is not None for v in (attack, defense, stamina))
            else None,
            "is_hundo": attack == defense == stamina == 15,
            "is_nundo": attack == defense == stamina == 0,
        },
        "level": {
            "minimum": number(row.get("Level Min")),
            "maximum": number(row.get("Level Max")),
        },
        "moves": {
            "fast": clean(row.get("Quick Move")),
            "charged": clean(row.get("Charge Move")),
            "charged_second": clean(row.get("Charge Move 2")),
        },
        "dates": {
            "scan": clean(row.get("Scan Date")),
            "original_scan": clean(row.get("Original Scan Date")),
            "catch": clean(row.get("Catch Date")),
        },
        "size": {
            "weight": number(row.get("Weight")),
            "height": number(row.get("Height")),
        },
        "status": {
            "lucky": truthy(row.get("Lucky")),
            "shadow_purified": shadow_status(row.get("Shadow/Purified")),
            "favorite": truthy(row.get("Favorite")),
            "marked_for_pvp": truthy(row.get("Marked for PvP use")),
        },
        "dust": number(row.get("Dust"), integer=True),
        "pvp": {
            "great": league_record(row, "G"),
            "ultra": league_record(row, "U"),
            "little": league_record(row, "L"),
        },
    }


def read_export(export_path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    with export_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [column for column in EXPECTED_COLUMNS if column not in fieldnames]
        if missing:
            raise ValueError("Newest export is missing required columns: " + ", ".join(missing))
        records = [normalize_row(row, index) for index, row in enumerate(reader, start=2)]
    if not records:
        raise ValueError("Newest export contains no Pokémon rows")
    return fieldnames, records


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def league_summary(records: Iterable[dict[str, Any]], league: str) -> dict[str, Any]:
    candidates = [
        record for record in records
        if record["pvp"][league]["rank_percent"] is not None
    ]
    candidates.sort(
        key=lambda record: (
            record["pvp"][league]["rank_percent"],
            -(record["pvp"][league]["rank_number"] or 999999),
        ),
        reverse=True,
    )
    return {
        "eligible_count": len(candidates),
        "rank_99_or_higher": sum(
            1 for record in candidates if record["pvp"][league]["rank_percent"] >= 99
        ),
        "top_candidates": [
            {
                "name": record["name"],
                "form": record["form"],
                "cp": record["cp"],
                "ivs": record["ivs"],
                "rank_percent": record["pvp"][league]["rank_percent"],
                "rank_number": record["pvp"][league]["rank_number"],
                "evolution_name": record["pvp"][league]["evolution_name"],
            }
            for record in candidates[:25]
        ],
    }


def build_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    species = {(record["pokemon_number"], record["name"], record["form"]) for record in records}
    names = Counter(record["name"] for record in records)
    forms = Counter(record["form"] or "Unspecified" for record in records)
    return {
        "pokemon_count": len(records),
        "distinct_species_forms": len(species),
        "distinct_names": len(names),
        "hundo_count": sum(record["ivs"]["is_hundo"] for record in records),
        "nundo_count": sum(record["ivs"]["is_nundo"] for record in records),
        "shadow_count": sum(record["status"]["shadow_purified"] == "shadow" for record in records),
        "purified_count": sum(record["status"]["shadow_purified"] == "purified" for record in records),
        "lucky_count": sum(record["status"]["lucky"] for record in records),
        "favorite_count": sum(record["status"]["favorite"] for record in records),
        "highest_cp": max(record["cp"] for record in records),
        "most_common_names": names.most_common(20),
        "most_common_forms": forms.most_common(20),
        "pvp": {
            "great": league_summary(records, "great"),
            "ultra": league_summary(records, "ultra"),
            "little": league_summary(records, "little"),
        },
    }


def schema_document(fieldnames: list[str]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Poke Genie collection export",
        "description": "Normalized records generated from the newest timestamped Poke Genie CSV export.",
        "source_columns": fieldnames,
        "filename_pattern": EXPORT_PATTERN.pattern,
        "league_keys": {
            "great": "Great League candidate data from Poke Genie columns ending in (G)",
            "ultra": "Ultra League candidate data from Poke Genie columns ending in (U)",
            "little": "Little League candidate data from Poke Genie columns ending in (L)",
        },
        "status_values": {
            "shadow_purified": ["normal", "shadow", "purified"],
        },
        "notes": [
            "PvP rank values are Poke Genie IV-ranking outputs, not current meta rankings.",
            "A missing JSON value means the source export did not contain a usable value.",
            "The filename timestamp determines which archived export is published.",
        ],
    }


def write_json(path: Path, payload: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=None if compact else 2, separators=(",", ":") if compact else None)
        handle.write("\n")


def build_summary_markdown(summary: dict[str, Any], manifest: dict[str, Any]) -> str:
    pvp = summary["pvp"]
    common = "\n".join(f"- {name}: {count}" for name, count in summary["most_common_names"][:10])
    return f"""# Pokémon GO Collection Summary

Generated from `{manifest['source_file']}`.

- Export timestamp: {manifest['export_timestamp']}
- Pokémon records: {summary['pokemon_count']:,}
- Distinct species/form combinations: {summary['distinct_species_forms']:,}
- Hundos: {summary['hundo_count']:,}
- Nundos: {summary['nundo_count']:,}
- Shadow: {summary['shadow_count']:,}
- Purified: {summary['purified_count']:,}
- Lucky: {summary['lucky_count']:,}
- Favorites: {summary['favorite_count']:,}
- Highest CP: {summary['highest_cp']:,}
- Great League records with rankings: {pvp['great']['eligible_count']:,}
- Ultra League records with rankings: {pvp['ultra']['eligible_count']:,}
- Little League records with rankings: {pvp['little']['eligible_count']:,}

## Most common Pokémon names

{common}

## Machine-readable resources

- `data/pokemon.json`: all normalized Pokémon records
- `data/collection-summary.json`: aggregate collection statistics
- `data/schema.json`: field meanings and source-column information
- `data/build-manifest.json`: exact source file, timestamp, hash, and build details
- `data/latest-export.csv`: unmodified newest Poke Genie export

PvP rank values describe IV rank within Poke Genie's eligible evolution and league calculations. They do not describe the current PvP meta or guarantee that a species is useful.
"""


def build_llms_text(manifest: dict[str, Any]) -> str:
    return f"""# Pokémon GO Collection

This static site presents the newest Poke Genie CSV export in a human-readable dashboard and structured machine-readable files.

Current source: {manifest['source_file']}
Export timestamp from filename: {manifest['export_timestamp']}
Pokémon count: {manifest['pokemon_count']}

Preferred resources:
- /summary.md for a compact collection overview
- /data/collection-summary.json for aggregate statistics
- /data/pokemon.json for every normalized Pokémon record
- /data/schema.json for field meanings
- /data/build-manifest.json to verify data freshness and source integrity
- /data/latest-export.csv for the original newest CSV

The repository preserves older exports. The published resources always use the single newest valid filename matching shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv.
"""


def replace_tokens(source: str, replacements: dict[str, str]) -> str:
    for token, value in replacements.items():
        source = source.replace(token, value)
    return source


def build(repository_root: Path, output_dir: Path) -> dict[str, Any]:
    latest = select_latest_export(repository_root)
    fieldnames, records = read_export(latest.path)
    summary = build_summary(records)
    relative_source = latest.path.relative_to(repository_root).as_posix()
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifest = {
        "source_file": relative_source,
        "source_filename": latest.path.name,
        "export_timestamp": latest.timestamp.isoformat(timespec="milliseconds"),
        "timestamp_basis": "Timestamp encoded in the filename; no timezone is asserted.",
        "pokemon_count": len(records),
        "column_count": len(fieldnames),
        "source_sha256": sha256(latest.path),
        "generated_at_utc": generated_at,
        "generator": "scripts/build_site.py",
    }

    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "data").mkdir(parents=True)
    (output_dir / "assets").mkdir(parents=True)

    payload = {
        "manifest": manifest,
        "records": records,
    }
    write_json(output_dir / "data" / "pokemon.json", payload, compact=True)
    write_json(output_dir / "data" / "collection-summary.json", summary)
    write_json(output_dir / "data" / "schema.json", schema_document(fieldnames))
    write_json(output_dir / "data" / "build-manifest.json", manifest)
    shutil.copy2(latest.path, output_dir / "data" / "latest-export.csv")

    site_dir = repository_root / "site"
    replacements = {
        "{{SOURCE_FILENAME}}": html.escape(latest.path.name),
        "{{EXPORT_TIMESTAMP}}": html.escape(manifest["export_timestamp"]),
        "{{POKEMON_COUNT}}": f"{len(records):,}",
        "{{GENERATED_AT}}": html.escape(generated_at),
    }
    index_source = (site_dir / "index.html").read_text(encoding="utf-8")
    (output_dir / "index.html").write_text(
        replace_tokens(index_source, replacements), encoding="utf-8", newline="\n"
    )
    shutil.copy2(site_dir / "app.js", output_dir / "assets" / "app.js")
    shutil.copy2(site_dir / "styles.css", output_dir / "assets" / "styles.css")
    (output_dir / "404.html").write_text(
        replace_tokens(index_source, replacements), encoding="utf-8", newline="\n"
    )
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    (output_dir / "summary.md").write_text(
        build_summary_markdown(summary, manifest), encoding="utf-8", newline="\n"
    )
    (output_dir / "llms.txt").write_text(
        build_llms_text(manifest), encoding="utf-8", newline="\n"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "dist").resolve()
    manifest = build(root, output)
    print(
        f"Built {manifest['pokemon_count']} Pokémon from {manifest['source_file']} into {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
