# Pokémon GO Collection

A static, searchable Pokémon GO collection companion generated from the newest archived Poke Genie CSV export. The project is designed to remain fully usable on GitHub Free, with no required backend, database, paid API, or local development environment for the basic workflow.

Site: `https://stevenfarless.github.io/pokemon-go-collection/`

## Human-facing pages

The published companion has three primary pages:

- `/` — searchable collection dashboard, filters, sorting, record details, comparison, Data Health, saved views, and Pokémon GO search helpers.
- `/insights.html` — collection-wide summaries, duplicate distribution, PvP/CP summaries, scan health, and drill-downs back to the collection.
- `/tools.html` — owned-only team building, resource optimization/what-if scenarios, collection goals, trade/duplicate review, browser-local notes/labels, unsupported-attribute enrichment, unified local backup/restore, and freshness-gated event preparation.

The generated build cross-links Collection, Insights, and Tools. `tools.html` and its hashed assets are included in the versioned PWA precache.

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

The build pipeline normalizes the newest valid Poke Genie export, assigns canonical record identity/provenance, reconciles conservative duplicate scans, generates diagnostics and public schemas, derives collection intelligence resources, normalizes reviewed current-game inputs, publishes hashed browser assets, stages the complete Pages artifact, and validates it before promotion.

Production remains one static application. Build modules are separated by responsibility but are not independent products.

## Data authority layers

The project deliberately keeps different kinds of information separate.

1. **Owned collection facts** come from the selected Poke Genie export and normalize into `data/pokemon.json`.
2. **Stable species/mechanics knowledge** comes from a pinned, versioned, provenance-carrying community snapshot under `data/knowledge/`.
3. **Derived collection intelligence** includes deterministic views, recommendations, candidate feeds, investment inputs, reasoning traces, species/family resources, and bounded history calculated from owned facts plus stable knowledge.
4. **Current rotating game data** belongs to `data/external/` snapshots with source authority, timestamps, validity, version, and freshness. Current-event/meta/raid consumers must block or degrade when required data is stale, expired, failed, or unavailable.
5. **Browser-local annotations** include notes, review labels, goals, saved views, and preferences.
6. **Browser-local enrichment** records explicit user-confirmed facts that Poke Genie does not reliably export, such as shiny/costume/background/Dynamax/Gigantamax/trade-review state, while remaining separate from canonical owned facts.

A Poke Genie PvP IV percentile is not a current-meta ranking. A browser-local fact is not a Poke Genie fact. Missing information is treated as uncertainty rather than evidence that a Pokémon is unimportant.

## Canonical identity and provenance

Every normalized owned record has canonical build identity under `identity.record_id` plus provenance and best-effort cross-build matching semantics.

Repeated scans reconciled by the normalization pipeline do not become independent owned Pokémon. Distinct identical-looking Pokémon remain distinct canonical records when source evidence supports that conclusion.

Record-local annotations and enrichment use canonical record IDs. Cross-build migration accepts compatibility evidence only when it resolves uniquely. Ambiguous or missing matches remain unresolved/orphaned rather than being silently assigned.

## Published machine resources

`data/build-manifest.json` is the authoritative inventory of the active build and public data resources.

Important entry points include:

- `/data/llm-bootstrap.json` — small machine bootstrap with build identity and retrieval paths.
- `/llms.txt` — concise LLM/tool retrieval guidance and source-boundary rules.
- `/data/pokemon.json` — canonical complete normalized owned collection.
- `/data/pokemon-index.json` and `/data/pokemon/chunk-NNNN.json` — bounded collection-wide retrieval.
- `/data/latest-export.csv` — unmodified selected Poke Genie export.
- `/data/collection-summary.json` — aggregate collection statistics.
- `/data/data-health.json` and `/data/scan-quality-report.json` — data-health and record-linked diagnostics.
- `/data/insights.json` — collection-wide calculated summaries.
- `/data/species-index.json` and `/data/pokemon/species/` — selective owned-species resources.
- `/data/family-index.json` and `/data/pokemon/families/` — evolutionary-family resources.
- `/data/views-index.json` and `/data/views/` — deterministic derived collection subsets.
- `/data/history-index.json` and `/data/collection-diff.json` — bounded retained history and conservative cross-build change intelligence.
- `/data/recommendations/`, `/data/candidates/`, `/data/investments/`, `/data/reasoning/` — explainable deterministic decision-support families.
- `/data/knowledge/` — pinned stable species/mechanics knowledge and provenance.
- `/data/external/index.json` — rotating-data discovery/freshness boundary.
- `/data/external/snapshots/` — generated source-attributed current-game snapshots when a valid reviewed provider input exists.
- `/api/v1/` — stable versioned static API path surface for selective machine consumers.

Consumers should prefer the smallest resource family that fits the question rather than assuming the complete `pokemon.json` endpoint is always necessary.

## Static API

`api/v1/` mirrors selected generated resources behind stable versioned paths. It is an ordinary static GitHub Pages interface, not a runtime API server. Start with `api/v1/index.json` and `api/v1/manifest.json`.

See `docs/public-data-api.md` for endpoint templates and compatibility rules.

## Pokémon GO knowledge and semantic diagnostics

The repository carries a committed, versioned Pokémon GO knowledge snapshot generated from a pinned PvPoke commit and classified **Verified community data**. Normal production builds consume the committed snapshot and require no runtime network access.

The stable knowledge layer provides species/form identity, base stats, typing, family relationships where available, buddy distance, a versioned move-pool snapshot, Mega/Primal metadata, and CP multipliers. Unsupported mechanics remain explicit unknowns rather than guessed values.

Stable move pools are not claims about current event availability, PvP meta strength, raid rotations, Rocket lineups, or other rotating game state.

## Current external game data

The provider-independent freshness framework supports `pvp`, `raids`, `moves`, `events`, `rocket`, `max-battles`, and `mechanics` categories.

Production now publishes reviewed **Official** event and raid inputs from `external/providers/` through the common external snapshot contract. The initial provider stores source-attributed factual metadata reviewed from named official Pokémon GO announcements. It does not copy article prose/images and explicitly records `automated_source_scraping: false`.

Generated event/raid snapshots carry build ID, source references, dataset/retrieval timestamps, validity, freshness policy/state, join keys, and classification. Pokémon references are validated against stable repository identifiers where available. Newly announced forms are not assigned invented pinned identifiers.

If a candidate provider input is malformed, the corresponding committed `external/last-known-good/` input is preserved and independently freshness-checked. Stale or expired snapshots remain provenance only and cannot silently serve as current instructions.

See `docs/external-game-data.md` for the acquisition, review, freshness, and fallback model.

## Search and filtering

Ordinary text search supports words, quoted phrases, exclusions, structured fields, bounded typo tolerance, and inspectable natural-language shortcuts.

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

Unsupported canonical source facts such as shiny, costume, background, Dynamax, or Gigantamax are not fabricated from species knowledge. Those attributes can instead be explicitly user-confirmed in browser-local enrichment.

## Planning and safety tools

`tools.html` runs entirely in the browser and consumes canonical generated resources.

Current tools include:

- owned-only Great, Ultra, Little, and Master League team composition;
- raid/Rocket/Mega inventory grouping without presenting static inventory rankings as current boss/meta simulations;
- Stardust/Candy budget optimization and level/league what-if scenarios;
- versioned local collection goals;
- safety-first trade and duplicate review;
- browser-local labels/notes keyed by canonical identity;
- browser-local enrichment for unsupported owned-record attributes;
- unified local-data backup/restore;
- event preparation that requires a fresh external event snapshot.

No duplicate/trade queue means “safe to transfer.” Local enrichment may add a protection reason, but never makes another Pokémon automatically safe. Irreversible actions are never silently executed.

## Local browser state and backup

The browser stores saved views, column preferences, goals, goal exclusions, notes/review labels, enrichment, and planner budget state in separate versioned namespaces.

`Export all local data` writes one human-readable versioned JSON envelope while preserving namespace boundaries. Restore validates every supported namespace before mutation and previews added/replaced/absent/ignored state. Unknown future major versions fail closed. A storage write failure triggers best-effort rollback to the pre-restore values.

Record-local migrations preserve ambiguous/orphan states instead of guessing.

## PWA and offline behavior

The installable PWA uses content-hashed assets and a build-versioned service worker. Static shell resources, including Tools and its local-data asset, are precached. Collection resources use the project’s versioned network-first strategy.

When offline, the UI exposes offline state so cached data is not mistaken for a freshly fetched build. Browser-local state is separate from service-worker caches.

## Validation and deployment safety

Pull requests and production deployment run Python tests, JavaScript tests, generated-schema/resource validation, browser/accessibility checks, performance/Lighthouse gates, architecture checks, and staged promotion guards.

Production is built into an isolated candidate directory. A failed staging candidate never replaces the current Pages site. Validated candidates are retained for a bounded period as `pages-lkg-*` rollback artifacts.

After Pages promotion, production smoke verification runs against the actual public site. It checks root/Insights/Tools routes, build-ID/count agreement across machine resources, first/last shards, static API discovery, external snapshots, service-worker/manifest resources, real browser JavaScript loading, exact search, impossible zero-result search, and Tools resource/navigation behavior. Pages propagation is retried only for a bounded window; an older deployed build is never accepted as the promoted candidate.

Before deployment the workflow captures the current live build ID. If production smoke fails, the workflow reports that previous build and attempts to resolve its retained rollback artifact/run.

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

No custom domain, paid backend, database, secret API key, or owner-specific infrastructure is required for the core path.

## Privacy

The repository and site are public. Poke Genie exports can reveal the Pokémon inventory, IVs, CP, levels, moves, dates, and statuses included by the export. Do not commit credentials, private notes, precise personal location data, or unrelated personal files.

Browser-local notes, goals, and enrichment are not published by the normal collection build unless a user deliberately exports and commits them, which is not part of the supported workflow. Precise location is never required by the enrichment model.
