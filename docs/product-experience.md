# Product experience: Today, guidance, global search, and Reference

This document defines the static product surfaces introduced for issues #125 through #128. They reuse existing canonical data, decision-support, mechanics, privacy, and freshness contracts rather than creating parallel rules.

## Today / Action Center

`today.html` reads `data/today.json`. The build elevates records from the existing recommendation queues, collection history, data-health resource, and fresh external snapshots. It does not recalculate PvP quality, evolution desirability, transfer safety, raid value, or roster strength.

The top-action list is capped at five deterministic items. Each card identifies why it exists, its evidence layer, its source resource, and a drill-down route. Current-data cards include source/freshness metadata and are rechecked in the browser against the external snapshot index before display. A snapshot that has aged past `freshness.max_age_hours` or its validity window is no longer shown as current even if the static site has not rebuilt yet.

Informational cards can be dismissed or snoozed in browser-local storage. Cards carrying warnings, and the Data Health blocker section, are not dismissible. The Roster Gaps section deliberately reports unavailable until a dedicated roster-readiness engine exists rather than inventing a new heuristic inside Today.

## Guidance levels and onboarding

The three presentation levels are `essential`, `detailed`, and `expert`. The selection is stored only under `pokemon-go-collection:guidance:v1`. CSS progressive disclosure changes visible explanation depth only. It does not alter calculations, data retrieval, filters, URLs, recommendation queues, or current-data eligibility.

Safety-critical elements use `data-safety-critical` and are outside guidance suppression. First-run orientation is stored under `pokemon-go-collection:onboarding:v1`. Definitions for IV %, exact IVs, PvP rank, stat product, Shadow, Mega/Max, build cost, freshness, and uncertainty are available from the global guidance/definition UI and contextual term buttons.

## Global search and commands

Every top-level generated page receives the product experience script through the shared platform publisher. The global palette opens from its button or Ctrl/Cmd+K. Collection's existing filter search remains separate.

`data/global-search-index.json` contains deterministic entries for known actions, exact owned records, owned species groups, every reference species/form, families, types, moves, mechanics domains, and only build-verified fresh current-data categories. Browser-local saved views are appended at runtime and are never published into the static index. Recent queries/selections are browser-local under `pokemon-go-collection:global-search-recent:v1` and can be cleared.

The palette lazily loads the generated search index. Current entries are additionally reconciled with the live `data/external/index.json` freshness state before they can appear. No LLM or remote search service is used.

## Species and form Reference Encyclopedia

`reference.html?species={canonical_species_id}` is the deterministic route for every supported entry in the versioned knowledge snapshot. `data/reference/index.json` is compact discovery metadata and deliberately does not duplicate the full `data/knowledge/pokemon-go.json` payload.

A reference route joins:

- stable, versioned knowledge such as dex/form identity, types, base stats, buddy distance, family/evolution/transformation data, move pools, second-move costs, Shadow eligibility, and Dynamax/Gigantamax eligibility where the knowledge schema supports them;
- exact owned copies by canonical `identity.record_id`;
- current external facts only when a published external snapshot remains fresh at view time and the fact contains an exact canonical `species_id` or Pokédex join key.

Stable knowledge, owned collection facts, calculated outputs, browser-local preferences, and current external facts are labeled as separate evidence layers. Missing current data degrades explicitly instead of falling back to stale facts.

Type, family, and free-text reference routes use the same compact index. The page fetches the larger versioned knowledge payload only when a specific species/form is opened, keeping the global search and initial reference browse path bounded.

## Static and privacy boundaries

All new functionality remains compatible with GitHub Pages and forks. No runtime server, paid service, proprietary asset, or automated official-site scraping is required. Browser-local guidance, onboarding, recent search state, Today dismissals/snoozes, and saved views are not publication inputs. Existing privacy profiles still run after product-resource generation so record-shaped data follows the same redaction boundary as the rest of the site.
