"""Pure calculations and schemas for collection health and insights resources."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import urlencode

DATA_HEALTH_SCHEMA_VERSION = "1.0.0"
INSIGHTS_SCHEMA_VERSION = "1.0.0"
STALE_SCAN_DAYS = 180
RECENT_CATCH_DAYS = 30


def is_missing(value: Any) -> bool:
    return value is None or value == ""


def parse_date(value: Any) -> date | None:
    if is_missing(value):
        return None
    text = str(value).strip()
    for candidate in (text[:10], text):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def build_date(value: str | None) -> date:
    if value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc).date()
        except ValueError:
            pass
    return datetime.now(timezone.utc).date()


def missing_scan_reasons(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    ivs = record.get("ivs", {})
    level = record.get("level", {})
    moves = record.get("moves", {})
    if is_missing(ivs.get("average_percent")):
        reasons.append("iv-average")
    if is_missing(ivs.get("attack")):
        reasons.append("attack-iv")
    if is_missing(ivs.get("defense")):
        reasons.append("defense-iv")
    if is_missing(ivs.get("stamina")):
        reasons.append("stamina-iv")
    if is_missing(level.get("minimum")):
        reasons.append("level-minimum")
    if is_missing(level.get("maximum")):
        reasons.append("level-maximum")
    if is_missing(moves.get("fast")):
        reasons.append("fast-move")
    if is_missing(moves.get("charged")):
        reasons.append("charged-move")
    return reasons


def collection_link(**params: Any) -> str:
    clean = {key: value for key, value in params.items() if value not in (None, "")}
    return "./" + (f"?{urlencode(clean)}" if clean else "")


def species_link(name: str, form: str | None = None, **params: Any) -> str:
    return collection_link(species=name, form=form or None, **params)


def _status_cards(summary: dict[str, Any]) -> list[dict[str, Any]]:
    definitions = (
        ("hundos", "Hundos", summary["hundo_count"], {"hundo": "yes"}),
        ("nundos", "Nundos", summary["nundo_count"], {"nundo": "yes"}),
        ("shadows", "Shadow", summary["shadow_count"], {"status": "shadow"}),
        ("purified", "Purified", summary["purified_count"], {"status": "purified"}),
        ("lucky", "Lucky", summary["lucky_count"], {"lucky": "yes"}),
        ("favorites", "Favorites", summary["favorite_count"], {"fav": "yes"}),
    )
    return [
        {"key": key, "label": label, "count": count, "href": collection_link(**params)}
        for key, label, count, params in definitions
    ]


def build_data_health(
    records: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    selected_league: str = "great",
    stale_scan_days: int = STALE_SCAN_DAYS,
    recent_catch_days: int = RECENT_CATCH_DAYS,
) -> dict[str, Any]:
    today = build_date(manifest.get("generated_at_utc"))
    stale_through = today - timedelta(days=stale_scan_days)
    recent_from = today - timedelta(days=recent_catch_days)
    reasons = [missing_scan_reasons(record) for record in records]

    def count_reason(predicate: Any) -> int:
        return sum(1 for item in reasons if predicate(item))

    missing_pvp = {
        league: sum(1 for record in records if is_missing(record.get("pvp", {}).get(league, {}).get("rank_percent")))
        for league in ("great", "ultra", "little")
    }
    stale_scans = sum(
        1
        for record in records
        if (scan := parse_date(record.get("dates", {}).get("scan"))) is not None and scan <= stale_through
    )
    missing_scan_dates = sum(1 for record in records if parse_date(record.get("dates", {}).get("scan")) is None)
    recent_catches = sum(
        1
        for record in records
        if (caught := parse_date(record.get("dates", {}).get("catch"))) is not None and caught >= recent_from
    )
    counts = {
        "records": len(records),
        "incomplete_scans": sum(bool(item) for item in reasons),
        "missing_ivs": count_reason(lambda item: any(reason.endswith("iv") or reason == "iv-average" for reason in item)),
        "missing_levels": count_reason(lambda item: any(reason.startswith("level-") for reason in item)),
        "missing_moves": count_reason(lambda item: any(reason.endswith("move") for reason in item)),
        "missing_scan_dates": missing_scan_dates,
        "missing_selected_pvp": missing_pvp[selected_league],
        "missing_great_pvp": missing_pvp["great"],
        "missing_ultra_pvp": missing_pvp["ultra"],
        "missing_little_pvp": missing_pvp["little"],
        "stale_scans": stale_scans,
        "recent_catches": recent_catches,
    }
    links = {
        "records": collection_link(),
        "incomplete_scans": collection_link(quality="missing-any", sort="scan:asc,name:asc"),
        "missing_ivs": collection_link(quality="missing-ivs", sort="scan:asc,name:asc"),
        "missing_levels": collection_link(quality="missing-level", sort="scan:asc,name:asc"),
        "missing_moves": collection_link(quality="missing-moves", sort="scan:asc,name:asc"),
        "missing_selected_pvp": collection_link(league=selected_league, pvpelig="unranked", sort="name:asc,cp:desc"),
        "stale_scans": collection_link(scanto=stale_through.isoformat(), sort="scan:asc,name:asc"),
        "recent_catches": collection_link(catchfrom=recent_from.isoformat(), sort="catch:desc,cp:desc"),
    }
    return {
        "schema_version": DATA_HEALTH_SCHEMA_VERSION,
        "source": {
            "filename": manifest["source_filename"],
            "source_file": manifest["source_file"],
            "export_timestamp": manifest["export_timestamp"],
            "timestamp_basis": manifest["timestamp_basis"],
            "record_count": len(records),
            "unknown_column_count": len(manifest.get("unknown_columns", [])),
            "missing_optional_column_count": len(manifest.get("missing_optional_columns", [])),
        },
        "build": {
            "generated_at_utc": manifest["generated_at_utc"],
            "export_schema_version": manifest["export_schema_version"],
            "normalized_schema_version": manifest["schema_version"],
            "warning_count": manifest.get("diagnostics", {}).get("warning_count", 0),
            "error_count": manifest.get("diagnostics", {}).get("error_count", 0),
        },
        "selected_league": selected_league,
        "thresholds": {
            "stale_scan_days": stale_scan_days,
            "stale_scan_through": stale_through.isoformat(),
            "recent_catch_days": recent_catch_days,
            "recent_catch_from": recent_from.isoformat(),
        },
        "counts": counts,
        "links": links,
        "definitions": {
            "complete_scan": "Overall IV percentage, Attack/Defense/HP IVs, minimum and maximum level, fast move, and first charged move are present.",
            "stale_scan": f"A usable scan date is {stale_scan_days} or more days before the build date.",
            "missing_pvp": "The selected league has no Poke Genie IV-ranking percentage. This does not invalidate the core inventory record.",
        },
    }


def _group_records(records: Iterable[dict[str, Any]]) -> dict[tuple[int, str, str | None], list[dict[str, Any]]]:
    groups: dict[tuple[int, str, str | None], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[(record["pokemon_number"], record["name"], record.get("form"))].append(record)
    return groups


def _candidate(record: dict[str, Any], league: str) -> dict[str, Any]:
    pvp = record.get("pvp", {}).get(league, {})
    return {
        "name": record["name"],
        "form": record.get("form"),
        "cp": record["cp"],
        "iv_percent": record.get("ivs", {}).get("average_percent"),
        "rank_percent": pvp.get("rank_percent"),
        "rank_number": pvp.get("rank_number"),
        "evolution_name": pvp.get("evolution_name"),
        "dust_cost": pvp.get("dust_cost"),
        "candy_cost": pvp.get("candy_cost"),
        "href": species_link(record["name"], record.get("form"), league=league, pvpelig="ranked", sort="pvp:desc,pvp-rank:asc,cp:desc"),
    }


def build_insights(
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    manifest: dict[str, Any],
    data_health: dict[str, Any],
) -> dict[str, Any]:
    groups = _group_records(records)
    distribution = Counter(len(group) for group in groups.values())
    duplicate_groups = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0][1].casefold(), item[0][2] or ""))
    single_groups = [item for item in duplicate_groups if len(item[1]) == 1]

    top_duplicates = [
        {
            "pokemon_number": key[0],
            "name": key[1],
            "form": key[2],
            "count": len(group),
            "highest_cp": max(record["cp"] for record in group),
            "best_iv_percent": max(
                (record.get("ivs", {}).get("average_percent") for record in group if not is_missing(record.get("ivs", {}).get("average_percent"))),
                default=None,
            ),
            "href": species_link(key[1], key[2], sort="cp:desc,iv:desc"),
        }
        for key, group in duplicate_groups[:50]
    ]
    singles = [
        {
            "pokemon_number": key[0],
            "name": key[1],
            "form": key[2],
            "cp": group[0]["cp"],
            "iv_percent": group[0].get("ivs", {}).get("average_percent"),
            "href": species_link(key[1], key[2]),
        }
        for key, group in single_groups[:100]
    ]
    highest_cp = sorted(
        (
            {
                "pokemon_number": key[0],
                "name": key[1],
                "form": key[2],
                "cp": max(record["cp"] for record in group),
                "href": species_link(key[1], key[2], sort="cp:desc"),
            }
            for key, group in groups.items()
        ),
        key=lambda item: (-item["cp"], item["name"].casefold(), item["form"] or ""),
    )[:100]

    pvp_sections = []
    for league in ("great", "ultra", "little"):
        ranked = [record for record in records if not is_missing(record.get("pvp", {}).get(league, {}).get("rank_percent"))]
        ranked.sort(
            key=lambda record: (
                -(record["pvp"][league].get("rank_percent") or 0),
                record["pvp"][league].get("rank_number") or 999999,
                -record["cp"],
            )
        )
        affordable = [record for record in ranked if not is_missing(record["pvp"][league].get("dust_cost"))]
        affordable.sort(key=lambda record: (record["pvp"][league]["dust_cost"], -(record["pvp"][league].get("rank_percent") or 0)))
        pvp_sections.append({
            "league": league,
            "label": f"{league.title()} League",
            "eligible_count": len(ranked),
            "rank_99_or_higher": sum((record["pvp"][league].get("rank_percent") or 0) >= 99 for record in ranked),
            "top_candidates": [_candidate(record, league) for record in ranked[:25]],
            "lowest_cost_candidates": [_candidate(record, league) for record in affordable[:10]],
            "href": collection_link(league=league, pvpelig="ranked", sort="pvp:desc,pvp-rank:asc,cp:desc"),
        })

    return {
        "schema_version": INSIGHTS_SCHEMA_VERSION,
        "source": {
            "filename": manifest["source_filename"],
            "export_timestamp": manifest["export_timestamp"],
            "generated_at_utc": manifest["generated_at_utc"],
            "record_count": len(records),
        },
        "overview": {
            "pokemon_count": summary["pokemon_count"],
            "distinct_species_forms": summary["distinct_species_forms"],
            "distinct_names": summary["distinct_names"],
            "highest_cp": summary["highest_cp"],
            "single_copy_groups": len(single_groups),
            "duplicate_groups": sum(1 for group in groups.values() if len(group) > 1),
            "status_cards": _status_cards(summary),
        },
        "duplicate_distribution": [
            {"copies": copies, "group_count": count}
            for copies, count in sorted(distribution.items())
        ],
        "top_duplicate_groups": top_duplicates,
        "single_copy_groups": singles,
        "highest_cp_by_species_form": highest_cp,
        "most_common_names": [
            {"name": name, "count": count, "href": species_link(name, sort="cp:desc,iv:desc")}
            for name, count in summary["most_common_names"]
        ],
        "most_common_forms": [
            {"form": form, "count": count, "href": collection_link(form=None if form == "Unspecified" else form, sort="name:asc,cp:desc")}
            for form, count in summary["most_common_forms"]
        ],
        "pvp": pvp_sections,
        "data_health": {
            "counts": data_health["counts"],
            "links": data_health["links"],
            "thresholds": data_health["thresholds"],
        },
        "limitations": [
            "Counts and rankings use only fields present in the published Poke Genie export.",
            "Poke Genie PvP values rank IV combinations under league caps; they do not measure the current battle meta or team fit.",
            "Missing values are uncertainty, not evidence that a Pokémon is inferior.",
            "The export does not reliably describe every in-game collector or transfer-protection attribute.",
        ],
    }


def data_health_schema() -> dict[str, Any]:
    count = {"type": "integer", "minimum": 0}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Pokémon GO collection Data Health",
        "type": "object",
        "required": ["schema_version", "source", "build", "selected_league", "thresholds", "counts", "links", "definitions"],
        "properties": {
            "schema_version": {"const": DATA_HEALTH_SCHEMA_VERSION},
            "source": {"type": "object"},
            "build": {"type": "object"},
            "selected_league": {"enum": ["great", "ultra", "little"]},
            "thresholds": {"type": "object"},
            "counts": {"type": "object", "additionalProperties": count},
            "links": {"type": "object", "additionalProperties": {"type": "string"}},
            "definitions": {"type": "object", "additionalProperties": {"type": "string"}},
        },
        "additionalProperties": False,
    }


def insights_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Pokémon GO collection insights",
        "type": "object",
        "required": [
            "schema_version", "source", "overview", "duplicate_distribution",
            "top_duplicate_groups", "single_copy_groups", "highest_cp_by_species_form",
            "most_common_names", "most_common_forms", "pvp", "data_health", "limitations",
        ],
        "properties": {
            "schema_version": {"const": INSIGHTS_SCHEMA_VERSION},
            "source": {"type": "object"},
            "overview": {"type": "object"},
            "duplicate_distribution": {"type": "array", "items": {"type": "object"}},
            "top_duplicate_groups": {"type": "array", "items": {"type": "object"}},
            "single_copy_groups": {"type": "array", "items": {"type": "object"}},
            "highest_cp_by_species_form": {"type": "array", "items": {"type": "object"}},
            "most_common_names": {"type": "array", "items": {"type": "object"}},
            "most_common_forms": {"type": "array", "items": {"type": "object"}},
            "pvp": {"type": "array", "items": {"type": "object"}},
            "data_health": {"type": "object"},
            "limitations": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    }
