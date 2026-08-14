# Public collection data and static API

The published GitHub Pages site exposes two related machine interfaces:

- `data/` contains the canonical generated resources and their JSON Schemas.
- `api/v1/` provides a stable, versioned static path surface for third-party scripts and machine clients.

Both interfaces are generated entirely by GitHub Actions and served as ordinary static files. There is no runtime database, server-side filtering, account session, query service, or required paid dependency.

## Recommended discovery order

Machine clients should prefer bounded discovery instead of assuming `data/pokemon.json` must always be downloaded first.

Recommended entry points:

1. `data/llm-bootstrap.json` for a compact build/retrieval bootstrap.
2. `data/build-manifest.json` or `api/v1/manifest.json` for authoritative build identity and the public resource registry.
3. `api/v1/index.json`, species/family resources, derived views, or `data/pokemon-index.json` depending on the question.
4. `data/pokemon.json` only when the complete canonical collection is genuinely required and the client can safely handle it.

`llms.txt` and `data/assistant-context.md` describe the same source/freshness boundaries for automated consumers.

## Authority and freshness

The build ID and export timestamp identify the active owned collection build. `data/pokemon.json` remains the canonical complete normalized collection.

Aggregate resources cannot prove ownership or state of one exact Pokémon by themselves. Exact record-specific decisions should resolve to canonical records and `identity.record_id` values.

Stable knowledge under `data/knowledge/` is versioned species/mechanics data, not current event/meta/raid truth. Rotating game facts belong under `data/external/` and must expose authority, timestamps, validity, and freshness.

## Selective collection resources

`data/species-index.json` lists every owned species and points to one small resource under `data/pokemon/species/`. A client can answer a species-specific ownership question with the manifest, species index, and one species resource.

`data/family-index.json` groups owned records by the versioned evolutionary-family semantics in `data/knowledge/species-index.json`. Family resources live under `data/pokemon/families/` and preserve every distinct canonical owned record.

`data/views-index.json` documents generated subsets such as hundos, nundos, Shadow, Purified, Lucky, Favorites, league candidates, and records needing a rescan. Categories the Poke Genie export does not explicitly support are marked unavailable instead of inferred from species knowledge.

For genuine collection-wide scans, `data/pokemon-index.json` remains the bounded shard discovery resource. Concatenating its shards in index order reconstructs the canonical record sequence exactly.

## Collection intelligence resources

The generated data product includes additional static families for explainable planning:

- `data/recommendations/` — review/recommendation queues with traceable reasons and blockers;
- `data/candidates/` — owned-only PvP/PvE candidate feeds;
- `data/investments/` — collection-aware investment inputs and explicit unknown costs;
- `data/reasoning/` — deterministic decision traces and current-data blockers;
- `data/knowledge/` — pinned stable species/mechanics knowledge;
- `data/external/` — freshness-aware rotating game data when a valid provider snapshot exists.

These resources do not redefine canonical ownership. Record-specific references resolve back to canonical owned record IDs.

## Bounded history

`data/history-index.json` lists retained snapshots, with bounded retention. `data/collection-diff.json` compares the newest retained snapshot with its predecessor.

Cross-build matching first uses the canonical best-effort fingerprint/provenance semantics. Conservative secondary matching is accepted only when evidence is unique. Non-unique evidence remains ambiguous.

A record listed as removed means it is no longer present in the current normalized export. That does not by itself prove that the Pokémon was transferred in Pokémon GO.

## Static API v1

The v1 root is `api/v1/`. Canonical schemas remain under `data/`; API copies preserve the same payload contracts.

| Endpoint | Purpose | Canonical schema | Example | Size guidance |
| --- | --- | --- | --- | --- |
| `index.json` | API discovery, compatibility policy, and endpoint templates | Self-describing API index | `api/v1/index.json` | Tiny; read first for API consumers |
| `manifest.json` | Build identity and freshness | `data/build-manifest.schema.json` | `api/v1/manifest.json` | Small |
| `species/index.json` | Owned-species discovery | `data/species-index.schema.json` | `api/v1/species/index.json` | Small to medium |
| `species/{dex}.json` | Exact owned records for one Pokédex number | `data/collection-resource.schema.json` | `api/v1/species/150.json` | Small; preferred for species questions |
| `families/index.json` | Owned evolutionary-family discovery | `data/family-index.schema.json` | `api/v1/families/index.json` | Small to medium |
| `families/{root_dex}.json` | Exact owned records in one family | `data/collection-resource.schema.json` | `api/v1/families/696.json` | Small; preferred for evolution decisions |
| `views/index.json` | Available/unavailable derived view discovery | `data/views-index.schema.json` | `api/v1/views/index.json` | Small |
| `views/{name}.json` | One deterministic collection subset | `data/collection-view.schema.json` | `api/v1/views/shadow.json` | Varies with subset size |
| `history/latest-diff.json` | Changes from the preceding retained export | `data/collection-diff.schema.json` | `api/v1/history/latest-diff.json` | Usually smaller than two full collections |

The API copies compact generated resources into versioned paths after the authoritative manifest is finalized.

Not every generated intelligence resource is required to have an `api/v1` alias. Consumers may use its canonical `data/` path when the manifest declares it. The API surface is intentionally stable and selective rather than a second copy of every generated file.

## Compatibility policy

Within API major version v1, endpoint templates and required top-level meanings remain compatible. A breaking path or required-field change requires a new API major version. Deprecations should remain documented before removal unless the old contract is unsafe or invalid.

Consumers should compare the current build ID before trusting cached collection facts. GitHub Pages controls HTTP caching and CORS behavior; this project does not claim server-side behavior beyond the static files GitHub Pages actually serves.

## Current-game data caveat

The external-data framework can validly report that no fresh provider snapshot exists. A client must not infer current events, raids, PvP meta, Rocket lineups, or Max Battles from the stable collection API when `data/external/index.json` says the required current category is unavailable/stale/expired.

As of August 14, 2026, issue #95 tracks production event and raid adapters. Until a fresh validated snapshot exists, current-game consumers should degrade clearly.

## LLM and agent guidance

`llms.txt` gives the shortest retrieval sequence. `data/assistant-context.md` explains authority, provenance, unsupported source fields, exact-record citation, and the boundary between static collection facts and time-sensitive Pokémon GO information.

For ownership questions, prefer the smallest resource that still contains exact canonical records. For current-game questions, combine owned collection resources with a separately fresh external snapshot rather than embedding rotating facts into the static owned-data contract.
