"""Source-column compatibility and JSON Schema contracts for collection builds."""

from __future__ import annotations

from typing import Any, Iterable

NORMALIZED_SCHEMA_VERSION = "1.0.0"
EXPORT_SCHEMA_VERSION = "poke-genie-csv-v1"
SCHEMA_BASE_ID = "https://stevenfarless.github.io/pokemon-go-collection/data/"

CORE_COLUMNS = ("Name", "Pokemon Number", "CP")
OPTIONAL_COLUMN_GROUPS: dict[str, tuple[str, ...]] = {
    "identity": ("Index", "Form", "Gender", "HP"),
    "appraisal": ("Atk IV", "Def IV", "Sta IV", "IV Avg", "Level Min", "Level Max"),
    "moves": ("Quick Move", "Charge Move", "Charge Move 2"),
    "dates": ("Scan Date", "Original Scan Date", "Catch Date"),
    "size": ("Weight", "Height"),
    "status": ("Lucky", "Shadow/Purified", "Favorite", "Dust", "Marked for PvP use"),
    "pvp_great": (
        "Rank % (G)", "Rank # (G)", "Stat Prod (G)", "Dust Cost (G)",
        "Candy Cost (G)", "Name (G)", "Form (G)", "Sha/Pur (G)",
    ),
    "pvp_ultra": (
        "Rank % (U)", "Rank # (U)", "Stat Prod (U)", "Dust Cost (U)",
        "Candy Cost (U)", "Name (U)", "Form (U)", "Sha/Pur (U)",
    ),
    "pvp_little": (
        "Rank % (L)", "Rank # (L)", "Stat Prod (L)", "Dust Cost (L)",
        "Candy Cost (L)", "Name (L)", "Form (L)", "Sha/Pur (L)",
    ),
}


def known_columns() -> tuple[str, ...]:
    columns: list[str] = list(CORE_COLUMNS)
    for group in OPTIONAL_COLUMN_GROUPS.values():
        columns.extend(group)
    return tuple(dict.fromkeys(columns))


def analyze_source_columns(fieldnames: Iterable[str]) -> dict[str, Any]:
    source = [str(name) for name in fieldnames]
    source_set = set(source)
    missing_required = [name for name in CORE_COLUMNS if name not in source_set]
    groups: dict[str, Any] = {}
    missing_optional: list[str] = []
    warnings: list[str] = []

    for name, columns in OPTIONAL_COLUMN_GROUPS.items():
        missing = [column for column in columns if column not in source_set]
        present = [column for column in columns if column in source_set]
        groups[name] = {
            "columns": list(columns),
            "present_columns": present,
            "missing_columns": missing,
            "complete": not missing,
        }
        missing_optional.extend(missing)
        if missing:
            warnings.append(
                f"Optional column group {name!r} is incomplete; missing: {', '.join(missing)}"
            )

    known = set(known_columns())
    unknown = [name for name in source if name not in known]
    if unknown:
        warnings.append("Unknown source columns were preserved in metadata: " + ", ".join(unknown))

    return {
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "normalized_schema_version": NORMALIZED_SCHEMA_VERSION,
        "required_columns": list(CORE_COLUMNS),
        "missing_required_columns": missing_required,
        "optional_column_groups": groups,
        "missing_optional_columns": missing_optional,
        "unknown_columns": unknown,
        "source_columns": source,
        "warnings": warnings,
    }


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _string(nullable: bool = True) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string"}
    return _nullable(schema) if nullable else schema


def _number(nullable: bool = True, **limits: Any) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "number", **limits}
    return _nullable(schema) if nullable else schema


def _integer(nullable: bool = True, **limits: Any) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "integer", **limits}
    return _nullable(schema) if nullable else schema


def _column_group_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["columns", "present_columns", "missing_columns", "complete"],
        "properties": {
            "columns": {"type": "array", "items": {"type": "string"}},
            "present_columns": {"type": "array", "items": {"type": "string"}},
            "missing_columns": {"type": "array", "items": {"type": "string"}},
            "complete": {"type": "boolean"},
        },
        "additionalProperties": False,
    }


def manifest_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_BASE_ID + "build-manifest.schema.json",
        "title": "Pokémon GO collection build manifest",
        "type": "object",
        "required": [
            "source_file", "source_filename", "export_timestamp", "timestamp_basis",
            "pokemon_count", "column_count", "source_sha256", "generated_at_utc",
            "generator", "build_id", "schema_version", "export_schema_version",
            "required_columns", "missing_required_columns", "source_columns",
            "missing_optional_columns", "unknown_columns", "schema_warnings",
            "optional_column_groups", "assets", "cache_policy",
        ],
        "properties": {
            "source_file": {"type": "string", "minLength": 1},
            "source_filename": {"type": "string", "minLength": 1},
            "export_timestamp": {"type": "string", "minLength": 1},
            "timestamp_basis": {"type": "string", "minLength": 1},
            "pokemon_count": {"type": "integer", "minimum": 1},
            "column_count": {"type": "integer", "minimum": len(CORE_COLUMNS)},
            "source_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "generated_at_utc": {"type": "string", "minLength": 1},
            "generator": {"type": "string", "const": "scripts/build_collection.py"},
            "build_id": {"type": "string", "pattern": "^[0-9a-f]{12}$"},
            "schema_version": {"type": "string", "const": NORMALIZED_SCHEMA_VERSION},
            "export_schema_version": {"type": "string", "const": EXPORT_SCHEMA_VERSION},
            "required_columns": {
                "type": "array", "items": {"type": "string"},
                "const": list(CORE_COLUMNS),
            },
            "missing_required_columns": {
                "type": "array", "items": {"type": "string"}, "maxItems": 0,
            },
            "source_columns": {
                "type": "array", "items": {"type": "string"},
                "minItems": len(CORE_COLUMNS),
            },
            "missing_optional_columns": {"type": "array", "items": {"type": "string"}},
            "unknown_columns": {"type": "array", "items": {"type": "string"}},
            "schema_warnings": {"type": "array", "items": {"type": "string"}},
            "optional_column_groups": {
                "type": "object",
                "required": list(OPTIONAL_COLUMN_GROUPS),
                "additionalProperties": _column_group_schema(),
            },
            "assets": {
                "type": "object",
                "required": ["styles", "app", "hardening", "accessibility"],
                "properties": {
                    "styles": {"type": "string", "pattern": "^assets/styles\\.[0-9a-f]{12}\\.css$"},
                    "app": {"type": "string", "pattern": "^assets/app\\.[0-9a-f]{12}\\.js$"},
                    "hardening": {"type": "string", "pattern": "^assets/hardening\\.[0-9a-f]{12}\\.js$"},
                    "accessibility": {"type": "string", "pattern": "^assets/accessibility\\.[0-9a-f]{12}\\.js$"},
                },
                "additionalProperties": False,
            },
            "cache_policy": {
                "type": "object",
                "required": ["host", "headers_controlled_by", "asset_strategy", "data_version_parameter", "service_worker"],
                "properties": {
                    "host": {"type": "string", "const": "GitHub Pages"},
                    "headers_controlled_by": {"type": "string", "const": "GitHub Pages"},
                    "asset_strategy": {"type": "string", "const": "content-hashed filenames"},
                    "data_version_parameter": {"type": "string", "pattern": "^[0-9a-f]{12}$"},
                    "service_worker": {"type": "boolean", "const": False},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }


def league_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "rank_percent", "rank_number", "stat_product", "dust_cost", "candy_cost",
            "evolution_name", "evolution_form", "status",
        ],
        "properties": {
            "rank_percent": _number(minimum=0, maximum=100),
            "rank_number": _integer(minimum=1),
            "stat_product": _number(minimum=0),
            "dust_cost": _integer(minimum=0),
            "candy_cost": _integer(minimum=0),
            "evolution_name": _string(),
            "evolution_form": _string(),
            "status": _nullable({"type": "string", "enum": ["normal", "shadow", "purified"]}),
        },
        "additionalProperties": False,
    }


def iv_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["attack", "defense", "stamina", "average_percent", "total", "is_hundo", "is_nundo"],
        "properties": {
            "attack": _integer(minimum=0, maximum=15),
            "defense": _integer(minimum=0, maximum=15),
            "stamina": _integer(minimum=0, maximum=15),
            "average_percent": _number(minimum=0, maximum=100),
            "total": _number(minimum=0, maximum=45),
            "is_hundo": {"type": "boolean"},
            "is_nundo": {"type": "boolean"},
        },
        "additionalProperties": False,
    }


def record_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "source_index", "name", "form", "pokemon_number", "gender", "cp", "hp",
            "ivs", "level", "moves", "dates", "size", "status", "dust", "pvp",
        ],
        "properties": {
            "source_index": _integer(),
            "name": {"type": "string", "minLength": 1},
            "form": _string(),
            "pokemon_number": {"type": "integer", "minimum": 1},
            "gender": _string(),
            "cp": {"type": "integer", "minimum": 0},
            "hp": _integer(minimum=0),
            "ivs": {"$ref": "#/$defs/ivs"},
            "level": {
                "type": "object",
                "required": ["minimum", "maximum"],
                "properties": {"minimum": _number(minimum=0), "maximum": _number(minimum=0)},
                "additionalProperties": False,
            },
            "moves": {
                "type": "object",
                "required": ["fast", "charged", "charged_second"],
                "properties": {"fast": _string(), "charged": _string(), "charged_second": _string()},
                "additionalProperties": False,
            },
            "dates": {
                "type": "object",
                "required": ["scan", "original_scan", "catch"],
                "properties": {"scan": _string(), "original_scan": _string(), "catch": _string()},
                "additionalProperties": False,
            },
            "size": {
                "type": "object",
                "required": ["weight", "height"],
                "properties": {"weight": _number(minimum=0), "height": _number(minimum=0)},
                "additionalProperties": False,
            },
            "status": {
                "type": "object",
                "required": ["lucky", "shadow_purified", "favorite", "marked_for_pvp"],
                "properties": {
                    "lucky": {"type": "boolean"},
                    "shadow_purified": {"type": "string", "enum": ["normal", "shadow", "purified"]},
                    "favorite": {"type": "boolean"},
                    "marked_for_pvp": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            "dust": _integer(minimum=0),
            "pvp": {
                "type": "object",
                "required": ["great", "ultra", "little"],
                "properties": {
                    "great": {"$ref": "#/$defs/league"},
                    "ultra": {"$ref": "#/$defs/league"},
                    "little": {"$ref": "#/$defs/league"},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }


def pokemon_payload_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_BASE_ID + "schema.json",
        "title": "Normalized Pokémon GO collection payload",
        "description": "Validation contract for data/pokemon.json.",
        "type": "object",
        "required": ["manifest", "records"],
        "properties": {
            "manifest": {"$ref": "#/$defs/manifest"},
            "records": {"type": "array", "items": {"$ref": "#/$defs/record"}, "minItems": 1},
        },
        "$defs": {
            "manifest": {key: value for key, value in manifest_schema().items() if not key.startswith("$")},
            "record": record_schema(),
            "league": league_schema(),
            "ivs": iv_schema(),
        },
        "additionalProperties": False,
    }


def summary_schema() -> dict[str, Any]:
    count = {"type": "integer", "minimum": 0}
    pair = {
        "type": "array",
        "prefixItems": [{"type": "string"}, count],
        "minItems": 2,
        "maxItems": 2,
    }
    top_candidate = {
        "type": "object",
        "required": ["name", "form", "cp", "ivs", "rank_percent", "rank_number", "evolution_name"],
        "properties": {
            "name": {"type": "string"},
            "form": _string(),
            "cp": {"type": "integer"},
            "ivs": {"$ref": "#/$defs/ivs"},
            "rank_percent": _number(),
            "rank_number": _integer(),
            "evolution_name": _string(),
        },
        "additionalProperties": False,
    }
    league_summary = {
        "type": "object",
        "required": ["eligible_count", "rank_99_or_higher", "top_candidates"],
        "properties": {
            "eligible_count": count,
            "rank_99_or_higher": count,
            "top_candidates": {"type": "array", "items": top_candidate},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_BASE_ID + "collection-summary.schema.json",
        "title": "Pokémon GO collection summary",
        "type": "object",
        "required": [
            "pokemon_count", "distinct_species_forms", "distinct_names", "hundo_count",
            "nundo_count", "shadow_count", "purified_count", "lucky_count",
            "favorite_count", "highest_cp", "most_common_names", "most_common_forms", "pvp",
        ],
        "properties": {
            "pokemon_count": {"type": "integer", "minimum": 1},
            "distinct_species_forms": count,
            "distinct_names": count,
            "hundo_count": count,
            "nundo_count": count,
            "shadow_count": count,
            "purified_count": count,
            "lucky_count": count,
            "favorite_count": count,
            "highest_cp": {"type": "integer", "minimum": 0},
            "most_common_names": {"type": "array", "items": pair},
            "most_common_forms": {"type": "array", "items": pair},
            "pvp": {
                "type": "object",
                "required": ["great", "ultra", "little"],
                "properties": {"great": league_summary, "ultra": league_summary, "little": league_summary},
                "additionalProperties": False,
            },
        },
        "$defs": {"ivs": iv_schema()},
        "additionalProperties": False,
    }


def source_columns_document(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "Poke Genie source-column compatibility report",
        "description": "Descriptive source-column metadata. This is not a payload validation schema.",
        **report,
        "notes": [
            "Only Name, Pokemon Number, and CP are required to publish a usable record.",
            "Missing optional source columns normalize to null, false, or normal according to the field contract.",
            "Unknown columns are reported but do not stop a build.",
        ],
    }
