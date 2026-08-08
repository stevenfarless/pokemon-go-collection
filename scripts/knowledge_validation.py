"""Apply the committed Pokémon GO knowledge snapshot to collection scan-quality checks."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

try:
    from .sync_knowledge import normalize_form
except ImportError:
    from sync_knowledge import normalize_form


@dataclass(frozen=True)
class KnowledgeMatch:
    status: str
    entry: Mapping[str, Any] | None
    detail: str


class KnowledgeBase:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload
        self.dataset_version = str(payload["dataset_version"])
        self.classification = str(payload["classification"])
        self.source = payload["source"]
        self.entries = list(payload["entries"])
        self.by_dex: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
        for entry in self.entries:
            self.by_dex[int(entry["dex"])].append(entry)
        self.cpms = {
            round(float(item["level"]) * 2) / 2: float(item["multiplier"])
            for item in payload["mechanics"]["cp_multiplier_levels"]
        }

    def match(self, record: Mapping[str, Any]) -> KnowledgeMatch:
        dex = record.get("pokemon_number")
        if not isinstance(dex, int):
            return KnowledgeMatch("missing-dex", None, "record has no integer Pokédex number")
        candidates = self.by_dex.get(dex, [])
        if not candidates:
            return KnowledgeMatch("unknown-dex", None, f"Pokédex #{dex} is absent from the pinned knowledge snapshot")

        requested = normalize_form(record.get("form"))
        matching = [
            entry
            for entry in candidates
            if requested == entry.get("form_key") or requested in set(entry.get("form_aliases", []))
        ]
        if requested == "normal":
            ordinary = [
                entry
                for entry in matching
                if entry.get("transformation", {}).get("kind") is None
            ]
            if len(ordinary) == 1:
                return KnowledgeMatch("matched", ordinary[0], "matched normal form by Pokédex number")
            if len(ordinary) > 1:
                matching = ordinary

        if len(matching) == 1:
            return KnowledgeMatch("matched", matching[0], f"matched form {requested!r} by Pokédex number")
        if not matching:
            available = sorted({str(entry.get("form_key")) for entry in candidates})
            return KnowledgeMatch(
                "unknown-form",
                None,
                f"form {requested!r} does not match known forms for Pokédex #{dex}: {', '.join(available)}",
            )
        return KnowledgeMatch(
            "ambiguous-form",
            None,
            f"form {requested!r} matches more than one knowledge entry for Pokédex #{dex}",
        )

    def plausible_cp_hp(self, record: Mapping[str, Any], entry: Mapping[str, Any]) -> tuple[bool | None, list[dict[str, Any]]]:
        ivs = record.get("ivs", {})
        level = record.get("level", {})
        values = (ivs.get("attack"), ivs.get("defense"), ivs.get("stamina"))
        cp = record.get("cp")
        hp = record.get("hp")
        minimum = level.get("minimum")
        maximum = level.get("maximum")
        if not all(isinstance(value, int) for value in values):
            return None, []
        if not isinstance(cp, int) or not isinstance(hp, int):
            return None, []
        if not isinstance(minimum, (int, float)) or not isinstance(maximum, (int, float)):
            return None, []
        if minimum > maximum:
            return False, []

        first = math.ceil(float(minimum) * 2 - 1e-9) / 2
        last = math.floor(float(maximum) * 2 + 1e-9) / 2
        if first > last:
            return False, []

        stats = entry["base_stats"]
        matches: list[dict[str, Any]] = []
        steps = int(round((last - first) * 2)) + 1
        supported = 0
        for offset in range(steps):
            candidate_level = round((first + offset * 0.5) * 2) / 2
            cpm = self.cpms.get(candidate_level)
            if cpm is None:
                continue
            supported += 1
            calculated_cp = max(
                10,
                math.floor(
                    (stats["attack"] + values[0])
                    * math.sqrt(stats["defense"] + values[1])
                    * math.sqrt(stats["stamina"] + values[2])
                    * cpm * cpm
                    / 10
                ),
            )
            calculated_hp = max(10, math.floor((stats["stamina"] + values[2]) * cpm))
            if calculated_cp == cp and calculated_hp == hp:
                matches.append(
                    {
                        "level": candidate_level,
                        "cp": calculated_cp,
                        "hp": calculated_hp,
                    }
                )
        if supported == 0:
            return None, []
        return bool(matches), matches


def load_repository_knowledge(repository_root: Path) -> KnowledgeBase:
    knowledge_dir = repository_root / "knowledge"
    payload_path = knowledge_dir / "pokemon-go.json"
    schema_path = knowledge_dir / "pokemon-go.schema.json"
    lock_path = knowledge_dir / "source-lock.json"
    if not payload_path.is_file() or not schema_path.is_file() or not lock_path.is_file():
        raise ValueError("Committed Pokémon GO knowledge snapshot is incomplete; run scripts/sync_knowledge.py")

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise ValueError(f"Committed Pokémon GO knowledge snapshot fails schema: {errors[0].message}")
    if payload.get("dataset_version") != lock.get("dataset_version"):
        raise ValueError("Committed knowledge dataset version differs from source-lock.json")
    if payload.get("source", {}).get("commit") != lock.get("source", {}).get("commit"):
        raise ValueError("Committed knowledge source commit differs from source-lock.json")
    return KnowledgeBase(payload)


def _finding(record: Mapping[str, Any], *, reason_code: str, action: str, message: str) -> dict[str, Any]:
    provenance = record.get("provenance", {})
    return {
        "severity": "warning",
        "reason_code": reason_code,
        "suggested_action": action,
        "message": message,
        "record_id": record.get("identity", {}).get("record_id"),
        "source_rows": list(provenance.get("source_rows", [])),
        "source_indices": [value for value in provenance.get("source_indices", []) if value is not None],
    }


def augment_scan_quality(
    report: dict[str, Any],
    records: Sequence[Mapping[str, Any]],
    knowledge: KnowledgeBase,
) -> dict[str, Any]:
    """Add knowledge-backed semantic findings without inventing missing source facts."""
    findings = list(report.get("findings", []))
    matched = 0
    plausibility_checked = 0
    plausibility_skipped = 0

    for record in records:
        match = knowledge.match(record)
        if match.status != "matched" or match.entry is None:
            findings.append(
                _finding(
                    record,
                    reason_code="unrecognized_species_form",
                    action="review" if match.status in {"unknown-form", "ambiguous-form"} else "parser_update",
                    message=(
                        f"Pinned Pokémon GO knowledge could not resolve {record.get('name')} "
                        f"(Pokédex #{record.get('pokemon_number')}, form {record.get('form') or 'normal'}): {match.detail}."
                    ),
                )
            )
            continue

        matched += 1
        plausible, _matches = knowledge.plausible_cp_hp(record, match.entry)
        if plausible is None:
            plausibility_skipped += 1
        else:
            plausibility_checked += 1
            if not plausible:
                findings.append(
                    _finding(
                        record,
                        reason_code="implausible_cp_hp_level",
                        action="rescan",
                        message=(
                            "Exported CP/HP/level combination does not match any supported half-level "
                            f"for {match.entry['display_name']} using the pinned base stats, CP multipliers, and exact IVs."
                        ),
                    )
                )

    severity_counts = Counter(item["severity"] for item in findings)
    action_counts = Counter(item["suggested_action"] for item in findings)
    reason_counts = Counter(item["reason_code"] for item in findings)
    report["findings"] = findings
    report["summary"] = {
        "finding_count": len(findings),
        "severity_counts": dict(sorted(severity_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
    }
    report["coverage"]["species_and_form_semantics"] = (
        f"validated against repository knowledge dataset {knowledge.dataset_version}"
    )
    report["coverage"]["species_specific_cp_hp_plausibility"] = (
        "validated when a species/form match, exact IVs, HP, CP, and level range are available"
    )
    report["knowledge"] = {
        "dataset_version": knowledge.dataset_version,
        "classification": knowledge.classification,
        "source_name": knowledge.source.get("name"),
        "source_commit": knowledge.source.get("commit"),
        "matched_record_count": matched,
        "plausibility_checked_count": plausibility_checked,
        "plausibility_skipped_count": plausibility_skipped,
    }
    return report
