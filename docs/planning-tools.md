# Local search and planning tools

This document describes the browser-side planning and review workspace now published at `tools.html`, plus the advanced search layer used by the main collection page.

## Architecture boundary

The planning layer consumes existing canonical resources. It does not define a second record identity, species database, freshness model, or recommendation engine.

Inputs include:

- `data/pokemon.json` for exact owned canonical records and `identity.record_id` values;
- `data/knowledge/pokemon-go.json` and `data/knowledge/species-index.json` for the pinned stable species/mechanics model;
- `data/candidates/` for owned-only PvP/PvE candidate feeds;
- `data/investments/` for versioned investment inputs;
- `data/reasoning/` for deterministic decision traces and blockers;
- `data/history-index.json` for bounded retained collection history;
- `data/external/index.json` for the current-game source authority/freshness boundary.

All computation occurs in static JavaScript in the browser. No runtime server, account backend, paid API, hosted database, embedding service, or model API is required.

The generated Collection, Insights, and Tools pages are cross-linked and use the same active build identity.

## Structured search

Advanced search extends the existing field-qualified grammar instead of replacing it.

It adds:

- deterministic fields such as `type:dragon`, `family:gible`, `dex:445`, `attack:15`, and `mega:yes`;
- bounded Levenshtein typo tolerance for ordinary unquoted tokens;
- compact natural-language shortcuts such as `shadow dragons under 1500 cp`;
- an inspectable compiled interpretation;
- explicit unsupported-term reporting for source facts such as shiny, costume, background, Dynamax, or Gigantamax when the normalized owned collection cannot answer them reliably.

Type, family, and Mega/Primal semantics are loaded from the versioned stable knowledge layer rather than a competing handwritten mapping.

## Owned-only team builder

The team builder consumes owned candidate feeds and canonical records.

The deterministic fallback can compose:

- Great, Ultra, Little, and Master League owned teams;
- raid-attacker inventory groups;
- Rocket inventory groups;
- Mega/Primal candidate selections.

The fallback ordering uses Poke Genie IV/build facts, IV/CP facts, or stable base-stat facts depending on mode. It does not present these as current PvP meta, current Rocket matchup, or current raid-boss rankings.

When current game data is unavailable or stale, the page says so. Exact owned record IDs remain visible, and up to two exact records can be locked into a team where supported.

## Resource optimizer and what-if simulator

The browser-local optimizer consumes versioned investment records. Missing cost fields remain unknown and are excluded from budget feasibility rather than treated as zero.

Current deterministic budget objectives include:

- complete the most known-cost builds;
- prefer higher Poke Genie IV percentile;
- prefer Poke Genie percentile per known Stardust/Candy cost.

These are planning heuristics, not current-meta rankings.

### Power-up cost model

The level 1-50 power-up table in `site/planning.js` is versioned as `2026-08-14.1` and classified as **Verified community data**. Its source metadata travels with calculated scenarios.

The model applies supported Lucky, Shadow, and Purified cost modifiers and returns a range when the source record has a level range instead of an exact level.

Level-40/50 and capped-league CP scenarios use pinned base stats, exact IVs, and the versioned CP multiplier table. If required inputs are missing, CP/cost remains unavailable.

The simulator never mutates `pokemon.json`. Evolution and second-move scenarios remain review calculations with irreversible-step warnings. Elite TM use, purification, evolution, and spending are never silently selected.

## Collection goals

Goals are stored in browser `localStorage` using a versioned local schema and can be exported/imported as JSON.

Supported built-in predicates include:

- living species/form count;
- hundo species/form count;
- Lucky species/form count;
- Great/Ultra/Little League candidates above a chosen Poke Genie percentile;
- owned Mega/Primal-capable species.

Shiny and costume goal templates intentionally render as unsupported because those statuses are not reliably represented by the normalized Poke Genie contract.

Where the same predicate can be evaluated from the previous bounded history snapshot, the goal card displays the retained-snapshot delta.

## Safety-first trade planner

The trade planner groups distinct canonical owned records by species, form, and supported status boundaries. Reconciled repeated scans do not reappear because it operates on canonical owned records.

Supported protection reasons include:

- hundo or nundo;
- favorite;
- Lucky;
- Shadow or Purified;
- unlocked second Charged Move;
- high Poke Genie PvP percentile;
- incomplete scans.

Every output is a review state. `trade_review_candidate` does not mean safe to trade. Unsupported shiny, costume, background, trade-history, and distance/origin facts remain explicit limitations.

## Safety-first duplicate review

Duplicate review operates only on distinct canonical records that remain after conservative duplicate-scan reconciliation.

Groups do not cross supported meaningful boundaries such as form, Shadow/Purified state, or Lucky state. Review rows expose useful comparison factors such as IVs, CP, level, PvP percentile/cost, scan completeness, and protection reasons.

Protected conditions include supported facts such as hundos, nundos, Favorites, Lucky, Shadow/Purified status, second Charged Moves, strong Poke Genie PvP candidates, unusual forms, and incomplete scans.

Missing attributes are treated as uncertainty. The current source contract cannot reliably prove every shiny, costume, background, legacy-move, Dynamax, Gigantamax, trade-history, or location fact. Duplicate review therefore never emits an automatic or guaranteed-safe transfer list.

## Browser-local notes and review labels

Record-specific annotations use canonical `identity.record_id` values rather than the older temporary browser identifier.

The annotation store is versioned and separate from generated collection data. It supports local labels, a short free-text note, JSON backup/restore, clearing, migration handling, and unresolved orphan/ambiguity states.

Migration rules are conservative:

- exact canonical identity is preferred;
- compatibility metadata may be used only when it resolves uniquely;
- ambiguous matches are never silently attached to one duplicate;
- records that no longer resolve remain orphaned for review.

Annotations are browser-local facts. They are visibly separate from Poke Genie facts and do not make network writes or modify generated `pokemon.json`.

## Freshness-gated event preparation

Event preparation consumes only normalized external snapshots whose `data_category` is `events` and whose calculated freshness state is `fresh`.

When a valid fresh snapshot is available, the planner can derive collection-specific Before/During/After actions from source-supported event facts, including owned/missing featured species and source-supported evolution, raid, Mega, PvP, or action targets.

The planner exposes provider/source classification, timestamps, freshness, and exact owned record IDs where relevant. Pokémon GO search helpers are species-level approximations when exact canonical record identity cannot be represented in the game search language.

If event data is stale, expired, failed, or unavailable, the planner refuses to reuse old event instructions. As of August 14, 2026, production provider adapters are not guaranteed; issue #95 tracks the first official event/raid adapters.

## Source-boundary rules

The planning UI distinguishes:

- Poke Genie/owned collection facts;
- pinned stable species/mechanics knowledge;
- deterministic calculated facts and reasoning;
- current external facts with freshness/authority metadata;
- browser-local goals and annotations;
- unsupported or unknown data.

A current-data blocker is preferable to a plausible-looking stale recommendation.

## Offline behavior

`tools.html` and its hashed JavaScript/CSS assets are included in the versioned service-worker precache. Required data resources use the repository's network-first data strategy and can be served from the current service-worker cache after successful retrieval.

Offline/cached state is surfaced so users do not mistake an older cached collection for a fresh build.
