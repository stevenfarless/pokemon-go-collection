"""Static build-time privacy profiles for public collection deployments."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

PROFILE_ENV = "POKEMON_GO_PRIVACY_PROFILE"
PROFILES = {"full-public", "redacted", "private-local-preview"}
DEFAULT_PUBLIC_TITLE = "Fuddledumpy’s Pokémon GO Collection"
DEFAULT_FRIEND_CODE_DISPLAY = "2252 2231 2780"
DEFAULT_FRIEND_CODE_COMPACT = "225222312780"
SENSITIVE_COLUMN_TERMS = (
    "scan date", "original scan date", "catch date", "latitude", "longitude", "location",
    "address", "trainer", "friend code", "nickname", "source index",
)
RECORD_SENSITIVE_KEYS = {
    "source_index", "scan_date", "original_scan_date", "catch_date", "latitude", "longitude",
    "location", "address", "trainer_id", "trainer_name", "friend_code", "nickname",
}


def _truth(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def resolve_profile(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    values = env or os.environ
    name = str(values.get(PROFILE_ENV, "full-public")).strip().lower()
    if name not in PROFILES:
        raise ValueError(f"Unsupported privacy profile {name!r}; choose one of {sorted(PROFILES)}")
    default_friend = name == "full-public"
    return {
        "name": name,
        "redact_collection_metadata": name != "full-public",
        "deployment_allowed": name != "private-local-preview",
        "publish_friend_code": _truth(values.get("POKEMON_GO_PUBLISH_FRIEND_CODE"), default_friend),
        "public_title": str(values.get("POKEMON_GO_PUBLIC_TITLE") or (DEFAULT_PUBLIC_TITLE if name == "full-public" else "Pokémon GO Collection")),
        "friend_code_display": str(values.get("POKEMON_GO_FRIEND_CODE") or DEFAULT_FRIEND_CODE_DISPLAY),
        "sensitive_columns": [],
        "published_export_sha256": None,
    }


def _normal_column(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def sensitive_columns(columns: list[str]) -> list[str]:
    output = []
    for column in columns:
        normal = _normal_column(column)
        if normal == "index" or any(term in normal for term in SENSITIVE_COLUMN_TERMS):
            output.append(column)
    return output


def _record_like(value: dict[str, Any]) -> bool:
    return (
        "pokemon_number" in value and ("cp" in value or "identity" in value or "record_id" in value)
    ) or ("record_id" in value and any(key in value for key in ("name", "pokemon", "ivs", "dates")))


def redact_payload(value: Any, *, record_context: bool = False) -> Any:
    if isinstance(value, list):
        return [redact_payload(item, record_context=record_context) for item in value]
    if not isinstance(value, dict):
        return value
    current_record = record_context or _record_like(value)
    output: dict[str, Any] = {}
    for key, item in value.items():
        normalized = str(key).strip().lower().replace("-", "_").replace(" ", "_")
        if current_record and normalized in RECORD_SENSITIVE_KEYS:
            output[key] = None
            continue
        if current_record and normalized == "dates" and isinstance(item, dict):
            dates = dict(item)
            for date_key in ("scan", "original_scan", "catch"):
                if date_key in dates:
                    dates[date_key] = None
            output[key] = redact_payload(dates, record_context=True)
            continue
        output[key] = redact_payload(item, record_context=current_record)
    return output


def _write_json(path: Path, payload: Any, *, compact: bool = False) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=None if compact else 2, separators=(",", ":") if compact else None) + "\n",
        encoding="utf-8", newline="\n",
    )


def redact_json_file(path: Path) -> bool:
    if path.name.endswith(".schema.json") or "/knowledge/" in path.as_posix() or "/external/" in path.as_posix():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    redacted = redact_payload(payload)
    if redacted == payload:
        return False
    _write_json(path, redacted, compact=path.name == "pokemon.json")
    return True


def redact_csv_file(path: Path, columns: list[str] | None = None) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    targets = columns or sensitive_columns(fieldnames)
    if not targets:
        return []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            for column in targets:
                if column in row:
                    row[column] = ""
            writer.writerow(row)
    return targets


def _apply_public_identity(path: Path, profile: dict[str, Any]) -> None:
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    source = source.replace(DEFAULT_PUBLIC_TITLE, profile["public_title"])
    if profile["publish_friend_code"]:
        compact = re.sub(r"\D", "", profile["friend_code_display"])
        source = source.replace(DEFAULT_FRIEND_CODE_DISPLAY, profile["friend_code_display"])
        source = source.replace(DEFAULT_FRIEND_CODE_COMPACT, compact)
    else:
        source = re.sub(r"\s+and add Friend Code\s+[0-9 ]+\.?", ".", source, flags=re.IGNORECASE)
        source = re.sub(
            r'<div class="trainer-contact"[^>]*>.*?</div>',
            '<div class="trainer-contact" aria-label="Trainer contact">Trainer contact withheld by privacy profile.</div>',
            source,
            count=1,
            flags=re.DOTALL,
        )
    path.write_text(source, encoding="utf-8", newline="\n")


def prepare_privacy(output_dir: Path, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    profile = resolve_profile(env)
    csv_path = output_dir / "data" / "latest-export.csv"
    columns: list[str] = []
    if csv_path.is_file():
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            columns = list(csv.DictReader(handle).fieldnames or [])
    profile["sensitive_columns"] = sensitive_columns(columns)

    for filename in ("index.html", "404.html"):
        _apply_public_identity(output_dir / filename, profile)

    if profile["redact_collection_metadata"]:
        pokemon = output_dir / "data" / "pokemon.json"
        if pokemon.is_file():
            redact_json_file(pokemon)
        if csv_path.is_file():
            redact_csv_file(csv_path, profile["sensitive_columns"])

    if csv_path.is_file():
        profile["published_export_sha256"] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    return profile


def _local_namespace_leaks(output_dir: Path) -> list[str]:
    needles = (
        "pokemon-go-collection:annotations",
        "pokemon-go-collection:enrichment",
        '"origin_note"',
        '"trade_note"',
    )
    leaks = []
    for path in (output_dir / "data").rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".csv"}:
            continue
        if path.name.endswith(".schema.json") or "/knowledge/" in path.as_posix() or "/external/" in path.as_posix():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(needle in text for needle in needles):
            leaks.append(path.relative_to(output_dir).as_posix())
    return sorted(set(leaks))


def finalize_privacy(output_dir: Path, profile: dict[str, Any]) -> dict[str, Any]:
    redacted_files: list[str] = []
    redacted_columns: set[str] = set()
    if profile["redact_collection_metadata"]:
        for path in (output_dir / "data").rglob("*.json"):
            if redact_json_file(path):
                redacted_files.append(path.relative_to(output_dir).as_posix())
        for path in output_dir.rglob("*.csv"):
            columns = redact_csv_file(path)
            if columns:
                redacted_files.append(path.relative_to(output_dir).as_posix())
                redacted_columns.update(columns)
        for path in output_dir.glob("*.html"):
            _apply_public_identity(path, profile)

    leaks = _local_namespace_leaks(output_dir)
    if leaks:
        raise ValueError("Browser-local private namespaces leaked into public data resources: " + ", ".join(leaks))

    audit = {
        "schema_version": 1,
        "profile": profile["name"],
        "deployment_allowed": profile["deployment_allowed"],
        "friend_code_public": profile["publish_friend_code"],
        "public_title": profile["public_title"],
        "detected_sensitive_source_columns": profile.get("sensitive_columns", []),
        "redacted_columns": sorted(redacted_columns or set(profile.get("sensitive_columns", []))) if profile["redact_collection_metadata"] else [],
        "redacted_resource_count": len(set(redacted_files)),
        "redacted_resources": sorted(set(redacted_files)),
        "published_export_sha256": profile.get("published_export_sha256"),
        "source_hash_semantics": "The canonical manifest source_sha256 identifies the original archived source. published_export_sha256 identifies the privacy-profile output served as data/latest-export.csv.",
        "canonical_identity_policy": "Opaque record/entity identifiers are preserved so redaction does not silently re-key records or invalidate historical joins.",
        "browser_local_namespaces_public": False,
        "publication_boundary": [
            "Generated static HTML and declared data resources are public when deployed to GitHub Pages.",
            "Browser-local notes, enrichment, goals, saved views, budgets, recovery snapshots, and diagnostics remain local to the browser.",
        ],
    }
    _write_json(output_dir / "data" / "privacy-audit.json", audit)
    (output_dir / "privacy-audit.md").write_text(
        "# Privacy audit\n\n"
        f"- Profile: `{audit['profile']}`\n"
        f"- Deployment allowed: `{str(audit['deployment_allowed']).lower()}`\n"
        f"- Friend code public: `{str(audit['friend_code_public']).lower()}`\n"
        f"- Sensitive source columns detected: {', '.join(audit['detected_sensitive_source_columns']) or 'none'}\n"
        f"- Redacted resources: {audit['redacted_resource_count']}\n"
        f"- Published export SHA-256: `{audit['published_export_sha256'] or 'unavailable'}`\n"
        "- Browser-local annotations/enrichment are never publication inputs.\n\n"
        "Opaque canonical record/entity IDs are retained so privacy redaction does not silently change identity or history semantics.\n",
        encoding="utf-8", newline="\n",
    )
    marker = output_dir / ".private-local-preview"
    if profile["deployment_allowed"]:
        marker.unlink(missing_ok=True)
    else:
        marker.write_text("This build is for local preview and must not be promoted to public Pages.\n", encoding="utf-8")
    return audit


__all__ = [
    "PROFILE_ENV", "PROFILES", "resolve_profile", "sensitive_columns", "redact_payload",
    "redact_json_file", "redact_csv_file", "prepare_privacy", "finalize_privacy",
]
