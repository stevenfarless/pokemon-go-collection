# Public collection data and static API

The published GitHub Pages site exposes two related interfaces:

- `data/` contains the canonical generated resources and their JSON Schemas.
- `api/v1/` provides a stable, versioned static path surface for third-party scripts and machine clients.

Both interfaces are generated entirely by GitHub Actions and served as ordinary static files. There is no runtime database, server-side filtering, query language, or required paid service.

## Authority and freshness

Start with `data/build-manifest.json` or `api/v1/manifest.json`. The build ID and export timestamp identify the active collection build. `data/pokemon.json` remains the canonical complete normalized collection. Species, family, view, history, and API resources are derived from that build and are validated against it in CI.

Aggregate resources such as `collection-summary.json` cannot prove ownership of an individual Pokémon. Exact decisions should resolve to canonical records and their `identity.record_id` values.

## Selective collection resources

`data/species-index.json` lists every owned species and points to one small resource under `data/pokemon/species/`. A client can answer a species-specific ownership question with the manifest, species index, and one species file.

`data/family-index.json` groups owned records by the versioned evolutionary-family semantics in `data/knowledge/species-index.json`. Family resources live under `data/pokemon/families/` and preserve every distinct canonical owned record.

`data/views-index.json` documents generated subsets such as hundos, nundos, Shadow, Purified, Lucky, Favorites, league candidates, and records needing a rescan. Categories the Poke Genie export does not explicitly support are marked unavailable instead of inferred from species knowledge.

For genuine collection-wide scans, `data/pokemon-index.json` remains the bounded shard discovery resource. Concatenating its shards in index order reconstructs the canonical record sequence.

## Bounded history

`data/history-index.json` lists retained snapshots, with a maximum of 12 archived exports per build. `data/collection-diff.json` compares the newest retained snapshot with its predecessor.

Cross-build matching first uses the canonical best-effort record fingerprint. A conservative secondary key is used only when exact IVs and a stable date anchor are present and the match is unique. Non-unique evidence is reported as ambiguous.

A record listed as removed means it is no longer present in the current normalized export. That status does not by itself prove that the Pokémon was transferred in Pokémon GO.

## Static API v1

The v1 root is `api/v1/`.

| Endpoint | Purpose | Size guidance |
| --- | --- | --- |
| `index.json` | API discovery, compatibility policy, and endpoint templates | Tiny; read first for API consumers |
| `manifest.json` | Build identity and freshness | Small |
| `species/index.json` | Owned-species discovery | Small to medium |
| `species/{dex}.json` | Exact owned records for one Pokédex number | Small; preferred for species questions |
| `families/index.json` | Owned evolutionary-family discovery | Small to medium |
| `families/{root_dex}.json` | Exact owned records in one family | Small; preferred for evolution decisions |
| `views/index.json` | Available/unavailable derived view discovery | Small |
| `views/{name}.json` | One deterministic collection subset | Varies with subset size |
| `history/latest-diff.json` | Changes from the preceding retained export | Usually smaller than two full collections |

The API copies compact generated resources into versioned paths after the authoritative manifest is finalized. Canonical schemas remain published under `data/`; the v1 copies preserve the same JSON payloads.

## Compatibility policy

Within API major version v1, endpoint templates and required top-level meanings remain compatible. A breaking path or required-field change requires a new API major version. Deprecations should remain documented for at least one repository release before removal unless the old contract is unsafe or invalid.

Consumers should compare the current build ID before trusting cached collection facts. GitHub Pages controls HTTP caching and CORS headers; this project does not claim server-side behavior beyond the static files GitHub Pages actually serves.

## LLM and agent bootstrap

`llms.txt` gives the shortest retrieval sequence. `data/assistant-context.md` explains authority, provenance, unsupported source fields, exact-record citation, and the boundary between static collection facts and time-sensitive Pokémon GO information.
