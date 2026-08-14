# Pokémon GO Collection

A static, searchable Pokémon GO collection companion generated from the newest archived Poke Genie CSV export. The project is designed to remain fully usable on GitHub Free, with no required backend, database, paid API, or local development environment for the basic workflow.

Site: `https://stevenfarless.github.io/pokemon-go-collection/`

## Human-facing pages

The published companion has three primary pages:

- `/` — searchable collection dashboard, filters, sorting, record details, comparison, Data Health, saved views, and Pokémon GO search helpers.
- `/insights.html` — collection-wide summaries, duplicate distribution, PvP/CP summaries, scan health, and drill-downs back to the collection.
- `/tools.html` — owned-only team building, resource optimization and what-if scenarios, collection goals, trade planning, duplicate review, browser-local notes/labels, and freshness-gated event preparation.

The generated build cross-links Collection, Insights, and Tools so visitors do not need to know filenames manually. `tools.html` is also included in the versioned PWA precache.

## Updating the collection

1. Export the collection from Poke Genie.
2. Upload the new CSV directly to `exports/` without renaming it.
3. Confirm the filename matches exactly:

```text
shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv
```

4. Commit the file to `main`, or open and merge a pull request.

Older exports remain archived. The filename timestamp determines the export used by the public site. Git commit dates, upload order, and filesystem modification times do not affect selection. Matching files outside `exports/` are ignored.

If the newest validly named export is malformed, empty, ambiguous, or missing required core columns, deployment fails instead of silently falling back to an older export.

## Canonical production build

The complete production site has one supported build command:

```bash
python scripts/build_dashboard.py
```

The build pipeline normalizes the newest valid Poke Genie export, assigns canonical record identity/provenance, reconciles conservative duplicate scans, generates diagnostics and public schemas, derives collection intelligence resources, publishes hashed browser assets, stages the complete Pages artifact, and validates it before promotion.

Production remains one static application. Build modules are separated by responsibility but are not independent products.

## Data authority layers

The project deliberately keeps different kinds of information separate.

1. **Owned collection facts** come from the selected Poke Genie export and normalize into `data/pokemon.json`.
2. **Stable species/mechanics knowledge** comes from a pinned, versioned, provenance-carrying community snapshot under `data/knowledge/`.
3. **Derived collection intelligence** includes deterministic views, recommendations, candidate feeds, investment inputs, reasoning traces, species/family resources, and bounded history calculated from owned facts plus stable knowledge.
4. **Current rotating game data** belongs to `data/external/` snapshots with authority, timestamps, validity, and freshness. Current-event/meta/raid consumers must block or degrade when required data is stale, expired, failed, or unavailable.
5. **Browser-local user state** such as saved views, goals, annotations/review labels, and column preferences stays separate from generated public collection data.

A Poke Genie PvP IV percentile is not a current-meta ranking. A browser-local note is not a Poke Genie fact. Missing information is treated as uncertainty rather than evidence that a Pokémon is unimportant.

## Canonical identity and provenance

Every normalized owned record has canonical build identity under `identity.record_id` plus provenance and best-effort cross-build matching semantics.

Repeated scans reconciled by the normalization pipeline do not become independent owned Pokémon. Distinct identical-looking Pokémon remain distinct canonical records when the source evidence supports that conclusion.

Browser-local annotations from the Tools page use canonical record IDs and versioned migration logic. Ambiguous legacy matches are not silently guessed; unresolved entries remain ambiguous/orphaned for review. Local annotations never modify generated `pokemon.json`.

## Published machine resources

`data/build-manifest.json` is the authoritative inventory of the active build and all public data resources.

Important entry points include:

- `/data/llm-bootstrap.json` — small machine bootstrap with build identity and retrieval paths.
- `/llms.txt` — concise LLM/tool retrieval guidance and source-boundary rules.
- `/data/pokemon.json` — canonical complete normalized owned collection.
- `/data/pokemon-index.json` — bounded shard discovery for collection-wide retrieval.
- `/data/pokemon/chunk-NNNN.json` — deterministic shards that reconstruct the canonical record sequence.
- `/data/latest-export.csv` — unmodified selected Poke Genie export.
- `/data/collection-summary.json` — aggregate collection statistics.
- `/data/data-health.json` — export freshness/completeness and scan-health metrics.
- `/data/scan-quality-report.json` — record-linked parser and semantic diagnostics.
- `/data/insights.json` — collection-wide calculated summaries.
- `/data/species-index.json` and `/data/pokemon/species/` — selective owned-species resources.
- `/data/family-index.json` and `/data/pokemon/families/` — evolutionary-family resources.
- `/data/views-index.json` and `/data/views/` — deterministic derived collection subsets.
- `/data/history-index.json` and `/data/collection-diff.json` — bounded retained history and conservative cross-build change intelligence.
- `/data/recommendations/` — explainable review/recommendation queues derived without embedding stale current-meta claims.
- `/data/candidates/` — owned-only PvP/PvE candidate feeds.
- `/data/investments/` — collection-aware investment inputs and explicit unknown costs.
- `/data/reasoning/` — deterministic rule traces and blockers.
- `/data/knowledge/` — pinned species/mechanics knowledge and provenance.
- `/data/external/index.json` — freshness/authority boundary for rotating game data.
- `/api/v1/` — stable versioned static API path surface for selective machine consumers.

Consumers should prefer the bootstrap, manifest, API discovery, species/family resources, views, or shards that fit the question rather than assuming the monolithic `pokemon.json` endpoint is always necessary.

## Static API

`api/v1/` mirrors selected generated resources behind stable versioned paths. It is an ordinary static GitHub Pages interface, not a runtime API server. There is no server-side filtering or account/session state.

Start with:

```text
api/v1/index.json
api/v1/manifest.json
```

See `docs/public-data-api.md` for endpoint templates, compatibility rules, and selective retrieval guidance.

## Pokémon GO knowledge and semantic diagnostics

The repository carries a committed, versioned Pokémon GO knowledge snapshot generated from a pinned PvPoke commit and classified **Verified community data**. Normal production builds consume the committed snapshot and require no runtime network access.

The stable knowledge layer provides species/form identity, base stats, typing, family relationships where available, buddy distance, a versioned move-pool snapshot, Mega/Primal metadata, and CP multipliers. Unsupported mechanics remain explicit unknowns rather than guessed values.

Move pools in this layer are versioned knowledge, not claims about current event availability, current PvP meta strength, raid rotations, Rocket lineups, or other rotating game state.

## Current external game data

The repository has a provider-independent freshness framework for `pvp`, `raids`, `moves`, `events`, `rocket`, `max-battles`, and `mechanics` snapshots. Each publishable snapshot must expose source authority/classification, timestamps, validity, version, licensing/attribution, join keys, and freshness policy.

As of August 14, 2026, the framework exists but production provider adapters are not yet a guaranteed source of current game truth. Consumers therefore correctly report current data as unavailable when no fresh production snapshot exists. Issue #95 tracks the first production official event and raid adapters.

Stale, expired, failed, reported, or datamined material is never silently promoted to current official fact.

## Search and filtering

Ordinary text search supports words, quoted phrases, and exclusions. Optional structured fields include core exported values plus deterministic knowledge-backed extensions.

Examples:

```text
pikachu "wild charge" -shadow
name:pikachu
form:alolan
move:"shadow ball"
cp:1500-2500
iv:96-100
level:40+
status:shadow
pvp:great
rank:1-100
type:dragon
family:gible
dex:445
attack:15
mega:yes
```

Advanced search also supports bounded typo tolerance and inspectable natural-language shortcuts. Unsupported source facts such as shiny, costume, background, Dynamax, or Gigantamax are not fabricated from species knowledge.

## Planning and safety tools

`tools.html` runs entirely in the browser and consumes canonical generated resources.

Current tools include:

- owned-only Great, Ultra, Little, and Master League team composition;
- raid/Rocket/Mega inventory grouping without pretending static collection rankings are current boss/meta simulations;
- Stardust/Candy budget optimization and level/league what-if scenarios;
- versioned local collection goals with retained-history deltas where supported;
- safety-first trade review;
- safety-first duplicate review over distinct canonical records;
- browser-local labels and notes keyed by canonical record identity;
- event preparation that requires a fresh external event snapshot.

No duplicate/trade queue means “safe to transfer.” Missing shiny/costume/background/legacy/current-event facts remain explicit limitations. Irreversible actions such as transfer, purification, Elite TM use, evolution, or spending are not silently executed.

## Local browser state

Saved views, column preferences, collection goals, and annotations/review labels are browser-local. Several features expose their own JSON export/import today. Browser storage can be cleared by the browser or operating system, so exported JSON is the current backup mechanism.

Issue #97 tracks a unified all-local-data backup/restore envelope and expanded post-deployment production smoke testing.

## PWA and offline behavior

The installable PWA uses content-hashed assets and a build-versioned service worker. Static shell resources, including the Tools page, are precached. Collection resources use the project’s versioned network-first strategy.

When offline, the UI exposes offline state so cached data is not mistaken for a freshly fetched build. Old application caches are removed only after a new service worker activates.

## Validation and deployment safety

Pull requests and production deployment run Python tests, JavaScript tests, generated-schema/resource validation, browser/accessibility checks, performance/Lighthouse gates, architecture checks, and staged promotion guards.

Production is built into an isolated candidate directory. A failed candidate never replaces the current Pages site. Validated successful candidates are retained for a bounded period as last-known-good rollback artifacts.

See:

- `docs/architecture.md`
- `docs/data-contracts.md`
- `docs/data-validation.md`
- `docs/deployment-safety.md`
- `docs/external-game-data.md`
- `docs/planning-tools.md`
- `docs/public-data-api.md`
- `docs/static-companion-features.md`

## Fork this project

A new player can fork the repository, enable GitHub Actions, configure GitHub Pages to use **GitHub Actions**, upload a valid Poke Genie export under `exports/`, and run the included fork/bootstrap self-test.

No custom domain, paid backend, database, secret API key, or owner-specific infrastructure is required for the core path. See `docs/fork-bootstrap.md` for the complete setup checklist.

## Privacy

The repository and site are public. Poke Genie exports can reveal the Pokémon inventory, IVs, CP, levels, moves, dates, and statuses included by the export. Do not commit credentials, private notes, precise personal location data, or unrelated personal files.

Browser-local notes and goals are not published by the normal collection build unless the user manually exports and commits them, which is not part of the supported workflow.
