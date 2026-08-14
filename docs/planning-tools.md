# Local search and planning tools

This document describes the browser-side features implemented for roadmap issues #72, #74, #75, #76, and #77.

## Architecture boundary

The planning layer is a consumer of existing canonical resources. It does not define a second record identity, species database, freshness model, or recommendation engine.

Inputs include:

- `data/pokemon.json` for exact owned canonical records and record IDs;
- `data/knowledge/pokemon-go.json` and `data/knowledge/species-index.json` for the pinned species/mechanics model from #71;
- `data/candidates/` for owned-only PvP/PvE candidate feeds from #66;
- `data/investments/` for versioned Poke Genie build-cost inputs from #67;
- `data/reasoning/` for deterministic decision traces from #73;
- `data/history-index.json` for bounded retained collection history from #63;
- `data/external/index.json` for the #69 authority/freshness boundary.

All computation occurs in static JavaScript in the browser. No runtime server, account backend, paid API, hosted database, embedding service, or model API is required.

## #72 Structured search

`site/advanced-search.js` wraps the existing field-qualified grammar from #36. Existing supported qualified and ordinary queries remain the base parser.

The extension adds:

- deterministic fields such as `type:dragon`, `family:gible`, `dex:445`, `attack:15`, and `mega:yes`;
- bounded Levenshtein typo tolerance for ordinary unquoted tokens;
- compact natural-language shortcuts such as `shadow dragons under 1500 cp`;
- an inspectable compiled interpretation and a button that replaces the original phrase with the explicit structured query;
- explicit unsupported-term reporting for source facts such as shiny/costume/background/Dynamax/Gigantamax when the normalized collection cannot answer them reliably.

Type, family, and Mega/Primal semantics are loaded lazily from the versioned #71 species index. They are not maintained as a competing handwritten species mapping.

## #74 Owned-only team builder

`tools.html#team-builder` consumes the candidate feeds from #66.

The deterministic fallback can compose:

- Great, Ultra, Little, and Master League owned teams;
- raid-attacker inventory groups;
- Rocket inventory groups;
- Mega/Primal candidate selections.

The current fallback ordering uses Poke Genie IV/build facts, IV/CP facts, or stable base-attack facts depending on the mode. It does not present these as current meta or boss-specific rankings.

When current game data is unavailable or stale, the page says so. A future current-meta integration can join through #69 without changing owned-record semantics.

The builder can lock up to two exact owned record IDs. PvP fallback teams avoid duplicate species. Results include exact canonical record IDs and a best-effort Pokémon GO species-name search helper with an exactness warning.

## #75 Resource optimizer and what-if simulator

The browser-local optimizer consumes #67 investment records. Missing cost fields remain unknown and are excluded from budget feasibility rather than treated as zero.

Current budget objectives are deterministic priorities:

- complete the most known-cost builds;
- prefer higher Poke Genie IV percentile;
- prefer Poke Genie percentile per known Stardust/Candy cost.

These objectives are local planning heuristics. They are not current-meta rankings.

### Power-up cost model

The level 1-50 power-up table in `site/planning.js` is versioned as `2026-08-14.1` and classified as **Verified community data**.

The table was verified on August 14, 2026 against Pokémon GO Hub's published power-up and XL Candy guides. The model stores the source URLs in its output metadata.

The model applies per-power-up cost modifiers for supported Lucky, Shadow, and Purified status. It returns a cost range when the source record has a level range instead of an exact level.

Level-40/50 and capped-league CP scenarios use the pinned #71 base stats, exact IVs, and CP multiplier table. If those inputs are missing, the resulting CP/cost stays unavailable.

The simulator never mutates `pokemon.json`. Evolution and second-move scenarios are review calculations with irreversible-step warnings. Elite TM use is not automatically selected.

## #76 Goals and progress

Goals are stored in browser `localStorage` using a versioned local schema and can be exported/imported as JSON.

Supported built-in predicates include:

- living species/form count;
- hundo species/form count;
- Lucky species/form count;
- Great/Ultra/Little League candidates above a chosen Poke Genie percentile;
- owned Mega/Primal-capable species.

Shiny and costume goal templates intentionally render as unsupported because those statuses are not reliably represented by the normalized Poke Genie contract.

Where the same predicate can be evaluated from the previous bounded #63 history snapshot, the goal card displays the retained-snapshot delta.

## #77 Trade planner

The trade planner groups distinct canonical owned records by species, form, and supported Shadow/Purified/Normal boundary. Reconciled repeated scans do not reappear because it operates on canonical `pokemon.json` records.

Supported protection reasons include:

- hundo or nundo;
- favorite;
- Lucky;
- Shadow or Purified;
- unlocked second Charged Move;
- high Poke Genie PvP percentile;
- incomplete scans.

Every output is a review state. `trade_review_candidate` does not mean safe to trade. Unsupported shiny, costume, background, trade-history, and missing location/distance facts remain explicit limitations.

Pokémon GO helper searches use species names only when that is the representable level of precision. Canonical record IDs cannot be encoded in Pokémon GO inventory search, so the UI states that limitation.

## Offline behavior

`tools.html` and its hashed JavaScript/CSS assets are included in the existing versioned service-worker precache. Required data resources use the repository's existing network-first data strategy and become available from the current service-worker cache after successful retrieval.
