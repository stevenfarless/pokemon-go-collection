"""Semantic validation and row-level diagnostics for Poke Genie CSV exports."""

from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

CORE_COLUMNS = ("Name", "Pokemon Number", "CP")
STATUS_COLUMNS = ("Shadow/Purified", "Sha/Pur (G)", "Sha/Pur (U)", "Sha/Pur (L)")
BOOLEAN_COLUMNS = ("Lucky", "Favorite", "Marked for PvP use")
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}

INTEGER_RULES: dict[str, tuple[int | None, int | None, bool]] = {
    "Index": (1, None, False),
    "Pokemon Number": (1, None, True),
    "CP": (1, None, True),
    "HP": (1, None, False),
    "Atk IV": (0, 15, False),
    "Def IV": (0, 15, False),
    "Sta IV": (0, 15, False),
    "Dust": (0, None, False),
    "Rank # (G)": (1, None, False),
    "Dust Cost (G)": (0, None, False),
    "Candy Cost (G)": (0, None, False),
    "Rank # (U)": (1, None, False),
    "Dust Cost (U)": (0, None, False),
    "Candy Cost (U)": (0, None, False),
    "Rank # (L)": (1, None, False),
    "Dust Cost (L)": (0, None, False),
    "Candy Cost (L)": (0, None, False),
}

NUMBER_RULES: dict[str, tuple[float | None, float | None]] = {
    "IV Avg": (0, 100),
    "Level Min": (1, 51),
    "Level Max": (1, 51),
    "Weight": (0, None),
    "Height": (0, None),
    "Rank % (G)": (0, 100),
    "Stat Prod (G)": (0, None),
    "Rank % (U)": (0, 100),
    "Stat Prod (U)": (0, None),
    "Rank % (L)": (0, 100),
    "Stat Prod (L)": (0, None),
}


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    row_number: int
    source_index: str | None
    pokemon_name: str | None
    column: str
    value: str
    message: str
    action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def format(self) -> str:
        identity = []
        if self.source_index:
            identity.append(f"source index {self.source_index}")
        if self.pokemon_name:
            identity.append(self.pokemon_name)
        suffix = f" ({', '.join(identity)})" if identity else ""
        return (
            f"CSV row {self.row_number}{suffix}, column {self.column!r}, "
            f"value {self.value!r}: {self.message} [{self.action}]"
        )


class SemanticValidationError(ValueError):
    """Fatal semantic validation errors with exact row-level diagnostics."""

    def __init__(self, diagnostics: Iterable[Diagnostic]):
        self.diagnostics = list(diagnostics)
        preview = "\n".join(item.format() for item in self.diagnostics[:20])
        remaining = len(self.diagnostics) - 20
        if remaining > 0:
            preview += f"\n... and {remaining} more error(s)"
        super().__init__(preview or "Semantic validation failed")


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _parse_number(value: str, column: str | None = None) -> float:
    normalized = value.replace(",", "").removesuffix("%")
    if column == "Weight":
        normalized = normalized.removesuffix("kg")
    elif column == "Height":
        normalized = normalized.removesuffix("m")
    parsed = float(normalized)
    if not math.isfinite(parsed):
        raise ValueError("value is not finite")
    return parsed


def _diagnostic(
    *, severity: str, row_number: int, row: Mapping[str, Any], column: str,
    value: str, message: str, action: str,
) -> Diagnostic:
    return Diagnostic(
        severity=severity,
        row_number=row_number,
        source_index=_clean(row.get("Index")) or None,
        pokemon_name=_clean(row.get("Name")) or None,
        column=column,
        value=value,
        message=message,
        action=action,
    )


def _validate_numeric(
    row: dict[str, str], row_number: int, column: str,
    minimum: float | None, maximum: float | None, *, integer: bool,
    required: bool, warnings: list[Diagnostic], errors: list[Diagnostic],
) -> None:
    raw = _clean(row.get(column))
    if not raw:
        if required:
            errors.append(_diagnostic(
                severity="error", row_number=row_number, row=row, column=column,
                value=raw, message="required numeric value is blank", action="build stopped",
            ))
        return

    try:
        parsed = _parse_number(raw, column)
    except (ValueError, OverflowError):
        target = errors if required else warnings
        target.append(_diagnostic(
            severity="error" if required else "warning",
            row_number=row_number, row=row, column=column, value=raw,
            message="expected a numeric value",
            action="build stopped" if required else "published as null",
        ))
        if not required:
            row[column] = ""
        return

    if integer and not parsed.is_integer():
        target = errors if required else warnings
        target.append(_diagnostic(
            severity="error" if required else "warning",
            row_number=row_number, row=row, column=column, value=raw,
            message="expected an integer value",
            action="build stopped" if required else "published as null",
        ))
        if not required:
            row[column] = ""
        return

    if minimum is not None and parsed < minimum or maximum is not None and parsed > maximum:
        bounds = (
            f"between {minimum:g} and {maximum:g}" if minimum is not None and maximum is not None
            else f"at least {minimum:g}" if minimum is not None else f"at most {maximum:g}"
        )
        target = errors if required else warnings
        target.append(_diagnostic(
            severity="error" if required else "warning",
            row_number=row_number, row=row, column=column, value=raw,
            message=f"value must be {bounds}",
            action="build stopped" if required else "published as null",
        ))
        if not required:
            row[column] = ""
        return

    if column in {"Weight", "Height"}:
        row[column] = str(parsed)

    if column in {"Level Min", "Level Max"} and not (parsed * 2).is_integer():
        warnings.append(_diagnostic(
            severity="warning", row_number=row_number, row=row, column=column, value=raw,
            message="Pokémon level must use 0.5-level increments",
            action="published as null",
        ))
        row[column] = ""


def validate_rows(
    fieldnames: Iterable[str], rows: Iterable[Mapping[str, Any]], *, start_row: int = 2,
) -> tuple[list[dict[str, str]], list[Diagnostic]]:
    """Return sanitized rows and warnings, or raise for fatal core errors."""
    fields = set(fieldnames)
    missing = [column for column in CORE_COLUMNS if column not in fields]
    if missing:
        raise ValueError("Newest export is missing required columns: " + ", ".join(missing))

    sanitized: list[dict[str, str]] = []
    warnings: list[Diagnostic] = []
    errors: list[Diagnostic] = []

    for row_number, source in enumerate(rows, start=start_row):
        row = {key: _clean(value) for key, value in source.items() if key is not None}
        name = _clean(row.get("Name"))
        if not name:
            errors.append(_diagnostic(
                severity="error", row_number=row_number, row=row, column="Name", value=name,
                message="required Pokémon name is blank", action="build stopped",
            ))

        for column, (minimum, maximum, required) in INTEGER_RULES.items():
            if column in fields:
                _validate_numeric(
                    row, row_number, column, minimum, maximum,
                    integer=True, required=required,
                    warnings=warnings, errors=errors,
                )

        for column, (minimum, maximum) in NUMBER_RULES.items():
            if column in fields:
                _validate_numeric(
                    row, row_number, column, minimum, maximum,
                    integer=False, required=False,
                    warnings=warnings, errors=errors,
                )

        for column in STATUS_COLUMNS:
            if column not in fields:
                continue
            raw = _clean(row.get(column))
            if raw and raw not in {"0", "1", "2"}:
                warnings.append(_diagnostic(
                    severity="warning", row_number=row_number, row=row, column=column,
                    value=raw, message="unrecognized status code; expected 0, 1, or 2",
                    action="published as null/normal with explicit warning",
                ))
                row[column] = "" if column != "Shadow/Purified" else "0"

        for column in BOOLEAN_COLUMNS:
            if column not in fields:
                continue
            raw = _clean(row.get(column))
            if raw and raw.casefold() not in TRUE_VALUES | FALSE_VALUES:
                warnings.append(_diagnostic(
                    severity="warning", row_number=row_number, row=row, column=column,
                    value=raw, message="unrecognized boolean value",
                    action="published as false with explicit warning",
                ))
                row[column] = "0"

        min_level = _clean(row.get("Level Min"))
        max_level = _clean(row.get("Level Max"))
        if min_level and max_level:
            try:
                if _parse_number(min_level) > _parse_number(max_level):
                    warnings.append(_diagnostic(
                        severity="warning", row_number=row_number, row=row,
                        column="Level Min/Level Max", value=f"{min_level}/{max_level}",
                        message="minimum level exceeds maximum level",
                        action="both levels published as null",
                    ))
                    row["Level Min"] = ""
                    row["Level Max"] = ""
            except ValueError:
                pass

        sanitized.append(row)

    if errors:
        raise SemanticValidationError(errors)
    return sanitized, warnings


def validate_csv(path: Path) -> tuple[list[str], list[dict[str, str]], list[Diagnostic]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows, warnings = validate_rows(fieldnames, reader)
    if not rows:
        raise ValueError("Newest export contains no Pokémon rows")
    return fieldnames, rows, warnings
