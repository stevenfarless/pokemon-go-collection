# Local search and planning tools

This document describes the browser-side planning/review workspace at `tools.html` and the advanced search layer on the Collection page.

## Architecture boundary

The planning layer consumes existing canonical resources. It does not define a second owned-record identity, species database, freshness model, or recommendation engine.

Inputs include:

- `data/pokemon.json` for exact owned canonical records and `identity.record_id` values;
- `data/knowledge/pokemon-go.json` and `data/knowledge/species-index.json` for pinned stable species/mechanics;
- `data/candidates/`, `data/investments/`, and `data/reasoning/` for deterministic decision support;
- `data/history-index.json` for bounded retained collection history;
- `data/external/index.json` and listed snapshots for current-game source authority/freshness;
- browser-local annotations, enrichment, goals, and preferences for user-confirmed local state.

All planning/local-state computation occurs in static JavaScript. No runtime server, account backend, paid API, hosted database, or model API is required.

## Structured search

Advanced search extends the field-qualified grammar with stable knowledge-backed fields, bounded typo tolerance, natural-language shortcuts, inspectable interpretation, and unsupported-term reporting.

The canonical search layer still does not fabricate shiny, costume, background, Dynamax, or Gigantamax state from species knowledge. Those exact owned-record attributes may instead be recorded separately through browser-local enrichment and filtered within the Enrichment workspace.

## Owned-only team builder

The team builder consumes owned candidate feeds and canonical records. It supports Great, Ultra, Little, and Master League team composition plus raid/Rocket/Mega inventory grouping.

Static candidate ranking is not presented as current PvP meta or a current raid-boss simulation. Current rotating data is used only through the freshness-aware external boundary when a tool explicitly supports it.

## Resource optimizer and what-if simulator

The optimizer consumes versioned investment records. Missing costs remain unknown rather than zero. Deterministic objectives can maximize known-cost builds, prefer Poke Genie percentile, or prefer percentile per known cost.

Level/CP/cost scenarios use pinned stable mechanics and exact owned facts. The simulator never mutates `pokemon.json` and never silently chooses an Elite TM, purification, evolution, or other irreversible action.

## Collection goals

Goals are versioned browser-local state. Canonical predicates include living, hundo, Lucky, league-candidate, and Mega/Primal-capable goals.

Shiny and costume remain unsupported as canonical Poke Genie predicates. When explicit browser-local enrichment exists, Tools adds a separate progress line counting only records whose local field is explicitly `yes`. Unknown records are not treated as `no`.

## Safety-first trade and duplicate review

Trade and duplicate review operate only on distinct canonical records left after conservative scan reconciliation and preserve supported form/status boundaries.

Canonical/Poke Genie protection signals include hundos/nundos, Favorite, Lucky, Shadow/Purified, second Charged Move, strong Poke Genie PvP percentile, unusual forms, and incomplete scans.

Browser-local enrichment can additionally display protection reasons for user-confirmed shiny, costume/event appearance, special/location/background, Dynamax, Gigantamax, reserved-for-trade, or manual legacy/exclusive-move review state.

Local enrichment can protect a record from an aggressive review decision. It never makes another copy automatically safe to transfer or trade.

## Browser-local notes and review labels

Annotations use canonical `identity.record_id`, schema v2, and conservative migration. Exact canonical identity is preferred; compatibility evidence is accepted only when unique; ambiguous/missing mappings remain unresolved.

## Browser-local enrichment

Enrichment uses its own versioned namespace and canonical record IDs. Initial tri-state fields are `unknown`, `yes`, or `no` for:

- shiny;
- costume/event appearance;
- special/location/background;
- Dynamax;
- Gigantamax;
- reserved for trade;
- already traded;
- manual legacy/exclusive-move review.

Optional short notes cover costume label, background, trade/history, and origin/distance without requiring precise location.

Changed fields record `user-confirmed` provenance and timestamps. Migration carries a compatibility tuple but remaps only on a unique match. Ambiguous and missing matches remain unresolved.

The enrichment workspace can filter explicit yes/no/unknown states, export/import enrichment alone, clear one record, or clear all enrichment.

## Unified local-data backup

The unified backup envelope preserves separate namespaces for saved views, goals, goal exclusions, annotations, enrichment, column preferences, and planner budget state.

Restore validates all supported namespaces and version metadata before any write. A preview reports what would be added, replaced, absent, or ignored. Unsupported future major versions fail closed. Supported old versions use explicit migrations.

If storage throws during an applied restore, already-written namespaces are rolled back to their previous values where browser storage permits it. Record-local ambiguous/orphan state is preserved.

## Freshness-gated event preparation

Event preparation consumes only normalized `events` snapshots whose calculated freshness state is `fresh`.

Production #95 event inputs are reviewed from named official Pokémon GO announcements and normalized into `data/external/snapshots/` with source references, classification, dataset timestamp, validity, freshness policy, and exact join metadata. The initial production event source is classified **Official** and explicitly records that automated official-site scraping is disabled.

When a fresh snapshot exists, the planner derives collection-specific Before/During/After actions from source-supported fields such as featured Pokédex targets, evolution windows, raid targets, and exact owned featured records.

If event data is stale, expired, malformed, or unavailable, the planner refuses to reuse old instructions.

## Source-boundary rules

The planning UI distinguishes:

- Poke Genie/owned collection facts;
- pinned stable species/mechanics knowledge;
- deterministic calculated facts/reasoning;
- freshness-aware current external facts;
- browser-local annotations/goals/preferences;
- browser-local user-confirmed enrichment;
- unsupported or unknown data.

A current-data blocker is preferable to plausible-looking stale advice.

## Offline and production behavior

`tools.html` and its hashed planning/final/local-data JavaScript assets are included in the versioned service-worker precache. Data resources use the network-first strategy and expose cached/offline state.

Production deployment additionally runs #97 smoke verification against the public Pages site. The browser smoke must load Tools, its canonical collection/local-data resources, navigation, exact Collection search, and an impossible zero-result search without fatal JavaScript errors.
