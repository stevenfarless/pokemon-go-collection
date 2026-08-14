# Static collection companion features

The human-facing companion remains fully static. Collection data, saved views, goals, annotations, enrichment, comparison selections, and preferences are not sent to Firebase or another application server.

## Human-facing pages

The generated Pages site exposes three primary surfaces:

- `/` — Collection dashboard and record details.
- `/insights.html` — Collection-wide summaries and drill-downs.
- `/tools.html` — Owned-only planning, duplicate/trade review, goals, notes/labels, browser-local enrichment/backup, and freshness-gated event preparation.

The production build cross-links these pages and includes Tools plus its hashed assets in the PWA precache.

## Canonical owned-record identity

Record-specific persistent features use `identity.record_id`. Browser-local migration may use the stored compatibility/provenance tuple only when it resolves to exactly one current canonical record. Ambiguous matches remain unresolved instead of being guessed.

Browser-local state never becomes part of `data/pokemon.json`.

## Saved views

Personal saved views contain the current URL query and optional desktop column preferences under a versioned `localStorage` key. They can still be managed independently and are also included in the unified local-data backup.

## Browser-local notes and review labels

Notes and review labels use canonical record IDs and annotation schema v2. Backup/import, clearing, migration, ambiguous-match detection, and orphan states remain supported.

## Browser-local enrichment

The Tools page can record owned-Pokémon attributes that the normalized Poke Genie export does not reliably provide. The initial typed fields are:

- shiny: `unknown`, `yes`, or `no`;
- costume/event appearance plus an optional short label;
- special/location/background plus an optional note;
- Dynamax;
- Gigantamax;
- reserved for trade;
- already traded plus an optional trade/history note;
- optional origin/distance note without requiring precise location;
- manual legacy/exclusive-move review flag.

Absence never means false. An untouched record is `unknown`.

Every saved field records browser-local provenance as `user-confirmed` with an update timestamp. The payload also stores a compatibility tuple for conservative migration. Exact canonical record ID wins; otherwise a compatibility match is accepted only if unique. Ambiguous or missing matches are preserved in the unresolved list.

Enrichment can add protection reasons to duplicate/trade review, such as user-confirmed shiny, costume, background, Dynamax/Gigantamax, or reserved-for-trade state. It never turns a different copy into an automatic transfer-safe candidate.

Shiny and costume goal cards may count explicitly confirmed local enrichment. Unknown records are not counted as explicit no.

## Unified local-data backup

`Export all local data` produces one versioned, human-readable JSON envelope. Namespaces remain separate rather than being flattened together. The initial envelope covers:

- saved views;
- collection goals;
- per-goal exclusions;
- notes/review labels;
- browser-local enrichment;
- desktop column preferences;
- planner budget state.

Restore is two-phase:

1. Parse and validate the complete backup, including namespace/version metadata and supported migrations.
2. Show a preview of namespaces that will be added, replaced, absent, or ignored.
3. Only after explicit apply does the browser write local state.

A malformed namespace rejects the restore before mutation. An unknown future backup major version is rejected. During a storage write failure, the restore attempts to roll back already-written namespaces to their previous values.

Older supported envelope versions use explicit migrations. Record-local ambiguous/orphan states remain unresolved rather than being silently reattached.

## Collection goals

Goals remain browser-local and versioned. Canonical or pinned-source predicates use the canonical data layer. Shiny/costume goals additionally receive browser-local enrichment progress when explicit user confirmations exist.

## Comparison workspace

Two to six Pokémon can be compared side by side. The comparison deliberately does not declare a universal winner. PvP rank, IV percentage, CP, Shadow status, moves, availability, enrichment, and investment cost answer different questions.

## Safety-first duplicate and trade review

Duplicate and trade tools operate on distinct canonical records remaining after conservative duplicate-scan reconciliation.

Canonical/Poke Genie protection reasons include hundos/nundos, Favorites, Lucky, Shadow/Purified state, unlocked second Charged Moves, strong Poke Genie PvP candidates, and incomplete scans. Browser-local enrichment can add user-confirmed protection signals without altering canonical source facts.

No review queue declares another record automatically safe to transfer.

## Pokémon GO search-string generator

The GO Search dialog translates compatible dashboard filters into Pokémon GO inventory search syntax and labels conditions Exact, Approximate, or Not representable. Browser-local annotations/enrichment and canonical record IDs do not become fake in-game operators.

The generator never labels a resulting string safe for blind bulk transfer.

## Planning tools

`tools.html` provides:

- owned-only PvP/PvE team composition;
- deterministic budget optimization and what-if investment scenarios;
- browser-local collection goals;
- safety-first trade planning;
- safety-first duplicate review;
- canonical-ID notes and review labels;
- typed browser-local enrichment;
- unified browser-local backup/restore;
- event preparation that requires a fresh external event snapshot.

Current PvP meta, raid rotations, Rocket lineups, event windows, and similar rotating facts are not inferred from stable collection data.

## Installable offline PWA

The generated site publishes `manifest.webmanifest`, a project-created icon, and a versioned `sw.js`. Hashed application assets, including the local-data asset, and the current collection shell are precached as one build version.

Browser-local views/goals/annotations/enrichment remain separate from service-worker caches and are protected with their own JSON backup path.

## Production deployment verification

Staging validation remains mandatory before promotion. #97 adds a second boundary after GitHub Pages deployment:

- public root, Insights, Tools, manifest, and service-worker routes must resolve;
- machine bootstrap, build manifest, shard index, canonical collection, API manifest, candidate/investment resources, and external-data index must agree on the promoted build ID;
- first and last shards are fetched and verified;
- generated external snapshots are fetched and verified;
- a real Chromium session loads the public collection without fatal JavaScript errors;
- a known exact species search must produce results;
- an impossible query must produce zero rows;
- Tools must load its canonical planning/local-data resources and cross-page navigation.

The verifier retries only for a bounded GitHub Pages propagation window. It never accepts an old build as successful. Before promotion, the workflow captures the currently live build ID. If production smoke fails, the Actions summary identifies that prior build and attempts to resolve its retained `pages-lkg-*` artifact/run for rollback guidance.

## Data-source boundaries

The UI distinguishes:

- Poke Genie owned-record facts;
- stable pinned species/mechanics knowledge;
- deterministic calculated facts/reasoning;
- freshness-aware current external facts;
- browser-local annotations;
- browser-local user-confirmed enrichment;
- unsupported/unknown data.

No layer silently becomes another. This is especially important for destructive or expensive decisions.
