"""Publish the Today surface, reference catalog, and global-search contracts."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from . import manifest_registry
except ImportError:
    import manifest_registry

PRODUCT_VERSION = "1.0.0"
TODAY_SCHEMA_VERSION = "1.0.0"
REFERENCE_INDEX_VERSION = "1.0.0"
SEARCH_INDEX_VERSION = "1.0.0"
GUIDANCE_LEVELS = ("essential", "detailed", "expert")
CURRENT_SAFE_STATE = "fresh"


def _load(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold()).strip("-") or "item"


def _form_key(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if text in {"", "normal", "none", "ordinary"}:
        return "normal"
    aliases = {"alolan": "alola", "galarian": "galar", "hisuian": "hisui", "paldean": "paldea"}
    text = aliases.get(text, text)
    text = re.sub(r"\bforme?\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return aliases.get(text, text or "normal")


def _record_id(record: Mapping[str, Any]) -> str:
    return str(record.get("identity", {}).get("record_id") or "")


def _record_route(record_id: str) -> str:
    return f"index.html?record={record_id}"


def _reference_route(species_id: str) -> str:
    return f"reference.html?species={species_id}"


def _current_snapshot_metadata(external_index: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Return only snapshots explicitly marked fresh by the #124 contract."""
    snapshots = (external_index or {}).get("snapshots") or []
    output = []
    for raw in snapshots:
        if not isinstance(raw, Mapping):
            continue
        freshness = raw.get("freshness") or {}
        if freshness.get("state") != CURRENT_SAFE_STATE or not raw.get("path"):
            continue
        output.append(
            {
                "provider": raw.get("provider"),
                "data_category": raw.get("data_category"),
                "classification": raw.get("classification"),
                "source_reference": raw.get("source_reference"),
                "source_references": list(raw.get("source_references") or []),
                "dataset_timestamp": raw.get("dataset_timestamp"),
                "validity": dict(raw.get("validity") or {}),
                "freshness": dict(freshness),
                "path": raw.get("path"),
            }
        )
    return output


def _owned_by_species(records: Iterable[Mapping[str, Any]]) -> dict[tuple[int, str], list[Mapping[str, Any]]]:
    grouped: dict[tuple[int, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        try:
            dex = int(record["pokemon_number"])
        except (KeyError, TypeError, ValueError):
            continue
        grouped[(dex, _form_key(record.get("form")))].append(record)
    return grouped


def _family_id(entry: Mapping[str, Any]) -> str | None:
    family = entry.get("family")
    if isinstance(family, Mapping):
        value = family.get("family_id") or family.get("id") or family.get("root_species_id")
        if value:
            return str(value)
    value = entry.get("family_id")
    return str(value) if value else None


def _move_names(value: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(value, str):
        text = value.strip()
        if text and len(text) <= 80:
            names.add(text)
    elif isinstance(value, list):
        for item in value:
            names.update(_move_names(item))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in {
                "energy",
                "power",
                "duration",
                "turns",
                "type",
                "legacy",
                "elite",
                "available",
                "kind",
            }:
                continue
            names.update(_move_names(item))
    return names


def build_reference_index(
    knowledge: Mapping[str, Any],
    records: Iterable[Mapping[str, Any]],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a compact all-species/form index without duplicating the large knowledge payload."""
    owned = _owned_by_species(records)
    entries: list[dict[str, Any]] = []
    for raw in knowledge.get("entries") or []:
        if not isinstance(raw, Mapping):
            continue
        dex = int(raw["dex"])
        form = _form_key(raw.get("form_key") or raw.get("form_label"))
        species_id = str(raw.get("species_id") or f"dex-{dex}-{form}")
        copies = owned.get((dex, form), [])
        entries.append(
            {
                "dex": dex,
                "species_id": species_id,
                "display_name": raw.get("display_name"),
                "base_name": raw.get("base_name"),
                "form_label": raw.get("form_label"),
                "form_key": form,
                "form_aliases": list(raw.get("form_aliases") or []),
                "types": list(raw.get("types") or []),
                "family_id": _family_id(raw),
                "released": bool(raw.get("released")),
                "transformation_kind": (raw.get("transformation") or {}).get("kind")
                if isinstance(raw.get("transformation"), Mapping)
                else None,
                "owned_count": len(copies),
                "owned_record_ids": [_record_id(record) for record in copies if _record_id(record)],
                "route": _reference_route(species_id),
            }
        )
    entries.sort(key=lambda item: (item["dex"], str(item["display_name"] or "").casefold(), item["form_key"]))
    return {
        "schema_version": REFERENCE_INDEX_VERSION,
        "product_version": PRODUCT_VERSION,
        "build_id": manifest["build_id"],
        "knowledge_dataset_version": knowledge.get("dataset_version"),
        "classification": knowledge.get("classification"),
        "route_pattern": "reference.html?species={canonical_species_id}",
        "knowledge_resource": "data/knowledge/pokemon-go.json",
        "entry_count": len(entries),
        "owned_entry_count": sum(1 for item in entries if item["owned_count"]),
        "entries": entries,
        "current_data_contract": {
            "index": "data/external/index.json",
            "required_freshness": CURRENT_SAFE_STATE,
            "rule": "Only exact species/form facts from snapshots explicitly marked fresh may be presented as current.",
        },
    }


def _search_item(
    item_id: str,
    domain: str,
    title: Any,
    subtitle: Any,
    route: str,
    terms: Iterable[Any] = (),
    **extra: Any,
) -> dict[str, Any]:
    clean_terms = [str(value) for value in terms if value not in (None, "")]
    return {
        "id": item_id,
        "domain": domain,
        "title": str(title or ""),
        "subtitle": str(subtitle or ""),
        "route": route,
        "terms": clean_terms,
        **extra,
    }


def build_search_index(
    reference: Mapping[str, Any],
    records: Iterable[Mapping[str, Any]],
    mechanics: Mapping[str, Any],
    fresh_snapshots: Iterable[Mapping[str, Any]],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    reference_entries = list(reference.get("entries") or [])
    ref_by_key = {(int(item["dex"]), str(item["form_key"])): item for item in reference_entries}

    actions = (
        ("today", "Today / Action Center", "Highest-value things to do now", "today.html", ("now", "action", "home")),
        ("collection", "Collection", "Owned Pokémon filters and exact records", "index.html", ("owned", "pokemon")),
        ("reference", "Reference Encyclopedia", "All supported species and forms", "reference.html", ("species", "forms")),
        ("insights", "Insights", "Collection-wide summaries and drill-downs", "insights.html", ("analysis",)),
        ("tools", "Tools", "Planning, backup, and collection utilities", "tools.html", ("event prep", "backup")),
        ("data-health", "Data Health", "Freshness and scan-quality checks", "index.html#data-health-panel", ("diagnostics", "rescan")),
        ("style-guide", "Design system", "Interface patterns and accessibility examples", "style-guide.html", ("appearance",)),
    )
    for key, title, subtitle, route, terms in actions:
        items.append(_search_item(f"action:{key}", "action", title, subtitle, route, terms))

    species_group_counts: Counter[tuple[int, str]] = Counter()
    species_group_names: dict[tuple[int, str], tuple[str, str | None]] = {}
    for record in records:
        record_id = _record_id(record)
        dex = int(record.get("pokemon_number") or 0)
        form = _form_key(record.get("form"))
        key = (dex, form)
        species_group_counts[key] += 1
        species_group_names[key] = (str(record.get("name") or "Unknown"), record.get("form"))
        ivs = record.get("ivs") or {}
        items.append(
            _search_item(
                f"record:{record_id}",
                "owned-record",
                record.get("name"),
                f"CP {record.get('cp') or '?'} · IV {ivs.get('average_percent') if ivs.get('average_percent') is not None else '?'}% · {record.get('form') or 'Normal'}",
                _record_route(record_id),
                (
                    record.get("pokemon_number"),
                    record.get("form"),
                    record.get("moves", {}).get("fast"),
                    record.get("moves", {}).get("charged"),
                    record.get("moves", {}).get("charged_second"),
                    record.get("status", {}).get("shadow_purified"),
                    record_id,
                ),
                canonical_record_id=record_id,
            )
        )

    for key, count in sorted(species_group_counts.items()):
        name, original_form = species_group_names[key]
        ref = ref_by_key.get(key)
        route = ref["route"] if ref else f"index.html?species={name}"
        items.append(
            _search_item(
                f"owned-species:{key[0]}:{key[1]}",
                "owned-species",
                name,
                f"{count} owned · {original_form or 'Normal'}",
                route,
                (key[0], original_form, "owned copies"),
                owned_count=count,
            )
        )

    type_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    for ref in reference_entries:
        items.append(
            _search_item(
                f"reference:{ref['species_id']}",
                "reference",
                ref.get("display_name"),
                f"#{int(ref['dex']):04d} · {ref.get('form_label') or ref.get('form_key') or 'Normal'} · {' / '.join(ref.get('types') or [])}",
                ref["route"],
                (
                    ref.get("species_id"),
                    ref.get("base_name"),
                    ref.get("form_key"),
                    *(ref.get("form_aliases") or []),
                    *(ref.get("types") or []),
                ),
                canonical_species_id=ref["species_id"],
                owned_count=ref.get("owned_count", 0),
            )
        )
        for pokemon_type in ref.get("types") or []:
            type_counts[str(pokemon_type)] += 1
        if ref.get("family_id"):
            family_counts[str(ref["family_id"])] += 1

    for pokemon_type, count in sorted(type_counts.items()):
        items.append(
            _search_item(
                f"type:{_slug(pokemon_type)}",
                "type",
                f"{pokemon_type} type",
                f"{count} supported species/forms",
                f"reference.html?type={pokemon_type}",
                (pokemon_type,),
            )
        )
    for family_id, count in sorted(family_counts.items()):
        items.append(
            _search_item(
                f"family:{_slug(family_id)}",
                "family",
                family_id.replace("_", " ").replace("-", " ").title(),
                f"{count} supported species/forms",
                f"reference.html?family={family_id}",
                (family_id, "evolution family"),
            )
        )

    for domain in mechanics.get("domains") or []:
        if not isinstance(domain, Mapping):
            continue
        items.append(
            _search_item(
                f"mechanic:{domain.get('id')}",
                "mechanic",
                domain.get("label"),
                f"{domain.get('status', 'unknown')} mechanics coverage",
                f"mechanics-coverage.md#{_slug(domain.get('label'))}",
                (domain.get("id"), *(domain.get("normalized_facts") or [])),
                mechanics_status=domain.get("status"),
            )
        )

    for snapshot in fresh_snapshots:
        category = str(snapshot.get("data_category") or "current")
        items.append(
            _search_item(
                f"current:{category}:{_slug(snapshot.get('provider'))}:{_slug(snapshot.get('dataset_timestamp'))}",
                "current",
                f"Current {category.replace('-', ' ').title()}",
                f"{snapshot.get('provider') or 'Source'} · current as of {snapshot.get('dataset_timestamp') or 'unknown'}",
                f"today.html#current-{_slug(category)}",
                (category, snapshot.get("provider"), snapshot.get("classification")),
                freshness="fresh",
                source_reference=snapshot.get("source_reference"),
                dataset_timestamp=snapshot.get("dataset_timestamp"),
            )
        )

    domain_counts = Counter(item["domain"] for item in items)
    return {
        "schema_version": SEARCH_INDEX_VERSION,
        "product_version": PRODUCT_VERSION,
        "build_id": manifest["build_id"],
        "knowledge_resource": reference.get("knowledge_resource"),
        "item_count": len(items),
        "domain_counts": dict(sorted(domain_counts.items())),
        "domain_order": [
            "action",
            "owned-record",
            "owned-species",
            "reference",
            "family",
            "type",
            "move",
            "mechanic",
            "current",
            "saved-view",
        ],
        "current_data_policy": "Only build-verified fresh snapshots are indexed as current results.",
        "items": items,
    }


def add_move_search_items(search_index: dict[str, Any], knowledge: Mapping[str, Any]) -> None:
    moves: set[str] = set()
    for entry in knowledge.get("entries") or []:
        if isinstance(entry, Mapping):
            moves.update(_move_names(entry.get("moves")))
    for move in sorted(moves, key=str.casefold):
        search_index["items"].append(
            _search_item(
                f"move:{_slug(move)}",
                "move",
                move,
                "Move in the versioned Pokémon GO knowledge snapshot",
                f"reference.html?search={move}",
                (move, "move"),
            )
        )
    counts = Counter(item["domain"] for item in search_index["items"])
    search_index["item_count"] = len(search_index["items"])
    search_index["domain_counts"] = dict(sorted(counts.items()))


def _queue_records(output_dir: Path, queue_name: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    index = _load(output_dir / "data" / "recommendations" / "index.json", {}) or {}
    entry = next((item for item in index.get("queues") or [] if item.get("name") == queue_name), None)
    if not entry or not entry.get("path"):
        return entry, []
    queue = _load(output_dir / str(entry["path"]), {}) or {}
    return entry, list(queue.get("records") or [])


def _record_card(
    queue_name: str,
    label: str,
    record: Mapping[str, Any],
    source_path: str,
    priority: int,
    *,
    dismissible: bool = True,
) -> dict[str, Any]:
    record_id = str(record.get("record_id") or "")
    reasons = list(record.get("reasons") or [])
    warnings = list(record.get("warnings") or [])
    return {
        "id": f"{queue_name}:{record_id}",
        "kind": "collection",
        "title": f"{label}: {record.get('name') or 'Pokémon'}",
        "summary": f"CP {record.get('cp') or '?'} · {record.get('form') or 'Normal form'}",
        "why": reasons or [f"Included by the shared {queue_name} decision-support queue."],
        "warnings": warnings,
        "priority": priority,
        "deadline": None,
        "cost": (record.get("inputs") or {}).get("pvp"),
        "reversibility": "review-before-action",
        "route": _record_route(record_id) if record_id else "index.html",
        "source_resource": source_path,
        "dismissible": dismissible and not bool(warnings),
        "safety_critical": bool(warnings),
        "evidence_layer": "Calculated from owned collection facts",
    }


def _freshness_card(snapshot: Mapping[str, Any], priority: int, *, event_prep: bool = False) -> dict[str, Any]:
    category = str(snapshot.get("data_category") or "current")
    validity = snapshot.get("validity") or {}
    label = category.replace("-", " ").title()
    return {
        "id": f"current:{category}:{_slug(snapshot.get('provider'))}:{_slug(snapshot.get('dataset_timestamp'))}",
        "kind": "current",
        "title": f"{'Event prep' if event_prep else 'Current window'}: {label}",
        "summary": f"Current as of {snapshot.get('dataset_timestamp') or 'unknown'}",
        "why": ["A reviewed normalized snapshot is fresh under the category freshness policy."],
        "warnings": [],
        "priority": priority,
        "deadline": validity.get("valid_until"),
        "cost": None,
        "reversibility": "informational",
        "route": f"today.html#current-{_slug(category)}",
        "source_resource": snapshot.get("path"),
        "source_reference": snapshot.get("source_reference"),
        "provider": snapshot.get("provider"),
        "dataset_timestamp": snapshot.get("dataset_timestamp"),
        "freshness": snapshot.get("freshness"),
        "dismissible": True,
        "safety_critical": False,
        "evidence_layer": "Current external fact",
    }


def build_today_payload(
    output_dir: Path,
    manifest: Mapping[str, Any],
    fresh_snapshots: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    health = _load(output_dir / "data" / "data-health.json", {}) or {}
    diff = _load(output_dir / "data" / "collection-diff.json", {}) or {}
    fresh = list(fresh_snapshots)

    rescan_entry, rescan = _queue_records(output_dir, "rescan")
    pvp_entry, pvp = _queue_records(output_dir, "pvp-candidates")
    evolution_entry, evolution = _queue_records(output_dir, "evolution-review")
    resource_entry, resource = _queue_records(output_dir, "resource-review")

    my_collection: list[dict[str, Any]] = []
    if rescan:
        source = str((rescan_entry or {}).get("path") or "data/recommendations/rescan.json")
        my_collection.append(_record_card("rescan", "Review scan", rescan[0], source, 10, dismissible=False))

    added = diff.get("added")
    changed = diff.get("changed")
    added_count = len(added) if isinstance(added, list) else int(diff.get("added_count") or 0)
    changed_count = len(changed) if isinstance(changed, list) else int(diff.get("changed_count") or 0)
    if added_count or changed_count:
        my_collection.append(
            {
                "id": "collection:changes",
                "kind": "collection",
                "title": "Collection changed since the previous retained export",
                "summary": f"{added_count} added · {changed_count} changed",
                "why": ["Published history/diff data reports changes between retained canonical snapshots."],
                "warnings": [],
                "priority": 25,
                "deadline": None,
                "cost": None,
                "reversibility": "informational",
                "route": "data/collection-diff.json",
                "source_resource": "data/collection-diff.json",
                "dismissible": True,
                "safety_critical": False,
                "evidence_layer": "Calculated collection history",
            }
        )

    build_opportunities: list[dict[str, Any]] = []
    for queue_name, label, entry, records, priority in (
        ("pvp-candidates", "PvP candidate", pvp_entry, pvp, 40),
        ("evolution-review", "Evolution review", evolution_entry, evolution, 45),
        ("resource-review", "Resource review", resource_entry, resource, 50),
    ):
        if records:
            source = str((entry or {}).get("path") or f"data/recommendations/{queue_name}.json")
            build_opportunities.append(_record_card(queue_name, label, records[0], source, priority))

    now_cards = [_freshness_card(item, 15) for item in fresh if item.get("data_category") != "events"]
    event_cards = [_freshness_card(item, 20, event_prep=True) for item in fresh if item.get("data_category") == "events"]

    health_counts = health.get("counts") or {}
    blockers = []
    for key, label in (
        ("incomplete_scans", "incomplete scans"),
        ("stale_scans", "stale scans"),
        ("missing_scan_dates", "records without scan dates"),
    ):
        count = int(health_counts.get(key) or 0)
        if count:
            blockers.append({"key": key, "label": label, "count": count, "route": (health.get("links") or {}).get(key)})

    data_health = {
        "state": "needs-attention" if blockers else "healthy",
        "blockers": blockers,
        "source_resource": "data/data-health.json",
        "export_timestamp": (health.get("source") or {}).get("export_timestamp"),
    }

    top_candidates = [*now_cards, *my_collection, *event_cards, *build_opportunities]
    top_actions = sorted(top_candidates, key=lambda item: (int(item.get("priority") or 999), item["id"]))[:5]

    return {
        "schema_version": TODAY_SCHEMA_VERSION,
        "product_version": PRODUCT_VERSION,
        "build_id": manifest["build_id"],
        "generated_at": manifest.get("generated_at_utc"),
        "export_timestamp": manifest.get("export_timestamp"),
        "top_actions": top_actions,
        "sections": {
            "now": {
                "status": "available" if now_cards else "limited",
                "cards": now_cards,
                "empty_message": "No fresh non-event rotating snapshot currently creates a time-sensitive card.",
            },
            "my_collection": {
                "status": "available",
                "cards": my_collection,
                "empty_message": "No collection-history or rescan item is currently elevated.",
                "local_augmentation": "Browser-local goals and unresolved storage mappings may be added at runtime without becoming public data.",
            },
            "build_opportunities": {
                "status": "available",
                "cards": build_opportunities,
                "empty_message": "No supported deterministic build opportunity is currently elevated.",
            },
            "event_prep": {
                "status": "available" if event_cards else "limited",
                "cards": event_cards,
                "empty_message": "No fresh reviewed event snapshot is available. Stale event data is not presented as current.",
            },
            "roster_gaps": {
                "status": "unavailable",
                "cards": [],
                "empty_message": "A dedicated roster-readiness engine is not published yet. This surface will not invent coverage gaps from ad hoc heuristics.",
                "planned_dependency": "#135",
            },
            "data_health": data_health,
        },
        "safety": {
            "current_claim_requires": "fresh normalized snapshot",
            "stale_current_data": "excluded from actionable cards",
            "dismissal_policy": "Informational cards may be hidden locally; data-integrity blockers are not dismissible.",
            "business_logic": "Cards point to shared recommendation/history/health/current-data resources instead of reimplementing their rules.",
        },
    }


def _page_shell(title: str, description: str, main_id: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{description}">
  <title>{title}</title>
</head>
<body>
  <a class="skip-link" href="#{main_id}">Skip to content</a>
  <header class="product-page-header">
    <nav aria-label="Primary">
      <a href="today.html">Today</a>
      <a href="index.html">Collection</a>
      <a href="reference.html">Reference</a>
      <a href="insights.html">Insights</a>
      <a href="tools.html">Tools</a>
    </nav>
  </header>
  <main id="{main_id}" class="product-page">
    {body}
  </main>
</body>
</html>
"""


def _write_pages(output_dir: Path) -> None:
    (output_dir / "today.html").write_text(
        _page_shell(
            "Today / Action Center",
            "Highest-value collection actions using canonical collection facts and only fresh current-game data.",
            "today",
            """<header class="product-hero">
      <p class="product-eyebrow">Action Center</p>
      <h1>Today</h1>
      <p>What deserves attention now, without manufacturing urgency from stale or unsupported data.</p>
    </header>
    <div id="today-root" aria-live="polite"><p>Loading current action summary…</p></div>""",
        ),
        encoding="utf-8",
        newline="\n",
    )
    (output_dir / "reference.html").write_text(
        _page_shell(
            "Pokémon GO Reference Encyclopedia",
            "Versioned species and form reference joined to exact owned collection records.",
            "reference",
            """<header class="product-hero">
      <p class="product-eyebrow">Reference</p>
      <h1>Species and form encyclopedia</h1>
      <p>Stable knowledge, owned copies, and fresh current facts remain explicitly separated.</p>
    </header>
    <div id="reference-root" aria-live="polite"><p>Loading reference index…</p></div>""",
        ),
        encoding="utf-8",
        newline="\n",
    )


def publish(repository_root: Path, output_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Publish #125-#128 product resources without introducing a runtime backend."""
    knowledge = _load(repository_root / "knowledge" / "pokemon-go.json", {}) or {}
    pokemon = _load(output_dir / "data" / "pokemon.json", {}) or {}
    records = list(pokemon.get("records") or [])
    mechanics = _load(output_dir / "data" / "mechanics" / "index.json", {}) or {}
    external_index = _load(output_dir / "data" / "external" / "index.json", {}) or {}
    fresh = _current_snapshot_metadata(external_index)

    reference = build_reference_index(knowledge, records, manifest)
    _write(output_dir / "data" / "reference" / "index.json", reference)

    search = build_search_index(reference, records, mechanics, fresh, manifest)
    add_move_search_items(search, knowledge)
    _write(output_dir / "data" / "global-search-index.json", search)

    today = build_today_payload(output_dir, manifest, fresh)
    _write(output_dir / "data" / "today.json", today)
    _write_pages(output_dir)

    manifest_registry._STABLE_NAMES["data/reference/index.json"] = "reference_index"
    manifest_registry._STABLE_NAMES["data/global-search-index.json"] = "global_search_index"
    manifest_registry._STABLE_NAMES["data/today.json"] = "today_action_center"

    return {
        "schema_version": PRODUCT_VERSION,
        "today": "today.html",
        "today_data": "data/today.json",
        "reference": "reference.html",
        "reference_index": "data/reference/index.json",
        "global_search_index": "data/global-search-index.json",
        "guidance_levels": list(GUIDANCE_LEVELS),
        "runtime_backend_required": False,
    }


__all__ = [
    "PRODUCT_VERSION",
    "TODAY_SCHEMA_VERSION",
    "REFERENCE_INDEX_VERSION",
    "SEARCH_INDEX_VERSION",
    "GUIDANCE_LEVELS",
    "build_reference_index",
    "build_search_index",
    "build_today_payload",
    "add_move_search_items",
    "publish",
]
