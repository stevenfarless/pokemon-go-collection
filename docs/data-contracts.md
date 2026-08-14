# Public data contracts

The generated `data/` directory is a public, machine-readable interface. `data/build-manifest.json` is the authoritative inventory for the currently published build.

## Contract rules

Every public JSON data resource in the current build must:

1. appear in `build-manifest.json.resources`;
2. point to a published JSON Schema through its registry entry;
3. validate against that schema before deployment;
4. agree with the active build on coordinated counts, identity, and references where applicable.

Schema files are themselves declared resources. Future resource types are optional until their implementing feature actually publishes them. The validator never requires placeholder files for unimplemented features.

## Versioning

The normalized Pokémon payload and build manifest use explicit schema/manifest versions. Resource-specific reports may also expose their own `schema_version`, `data_version`, or policy version.

Compatibility policy:

- Additive optional fields may be introduced without invalidating existing consumers when the documented meaning of existing fields does not change.
- Adding a new optional resource is additive. It becomes required only for builds that declare it in the resource registry.
- A breaking change to required fields, field types, identity semantics, or existing field meaning requires the appropriate schema/manifest version to change.
- Consumers should discover resources through the manifest instead of assuming every future resource exists.
- Consumers should reject or explicitly degrade when a required schema version is unsupported rather than silently interpreting incompatible data.

## Canonical owned-record identity

`data/pokemon.json` is the authoritative complete owned-record dataset for a build. Every normalized record carries canonical identity/provenance metadata.

`identity.record_id` is the exact within-build record identifier used by record-specific browser tools and derived resources. Cross-build matching uses the separately documented best-effort fingerprint/provenance semantics and must preserve ambiguity rather than silently claiming two records are the same physical Pokémon.

Repeated scans reconciled during normalization do not become independent canonical owned records. Distinct identical-looking Pokémon remain separate when the canonical import pipeline cannot safely collapse them.

Browser-local annotations, goals, and preferences are not part of this public data contract and are never written into `pokemon.json` by the normal build.

## Bounded collection retrieval

`data/pokemon.json` remains the canonical complete collection. Clients that do not need or cannot safely retrieve that full payload should first request `data/llm-bootstrap.json`, `data/pokemon-index.json`, or a more selective resource.

The shard index declares the active build ID, normalized schema version, canonical dataset path, normalized record count, shard strategy, target and hard byte limits, and an ordered list of shard descriptors. Each descriptor includes path, byte size, SHA-256, record count, and first/last canonical record IDs.

Collection shards are published under `data/pokemon/chunk-NNNN.json`. Each shard contains normalized records from exactly one build and carries its own build/schema metadata. Shard order is canonical record order. Concatenating every shard's `records` array in index order reconstructs the canonical `pokemon.json.records` sequence exactly.

The default target is 700 KiB and the hard maximum is 900 KiB. The target is a packing goal rather than a provider-specific limit; the hard maximum is enforced by the generator, schemas, and CI. A single canonical record that cannot fit under the hard maximum fails the build instead of silently producing an oversized shard.

The shard directory is deleted and regenerated on every canonical build. Stale shard files, missing shard files, duplicate paths, wrong build IDs, checksum/size drift, duplicate or omitted record IDs, and reconstruction differences all fail validation.

## Selective collection resources

The build publishes smaller resources for common bounded questions:

- `data/species-index.json` plus `data/pokemon/species/` for exact owned species resources;
- `data/family-index.json` plus `data/pokemon/families/` for evolutionary-family resources using the versioned knowledge family semantics;
- `data/views-index.json` plus `data/views/` for deterministic owned-record subsets such as hundos, nundos, Shadow, Purified, Lucky, Favorites, league candidates, and rescan candidates;
- `data/history-index.json` and `data/collection-diff.json` for bounded retained history and conservative cross-build change intelligence.

Unsupported source categories are marked unavailable rather than inferred from species knowledge.

## Derived intelligence resources

The current build also publishes collection-intelligence families that remain traceable to canonical owned records:

- `data/recommendations/` for explainable review/recommendation queues;
- `data/candidates/` for owned-only PvP/PvE candidate feeds;
- `data/investments/` for versioned investment inputs and explicit unknown costs;
- `data/reasoning/` for deterministic rule outputs, blockers, and traceable factors.

These resources may combine owned facts with stable versioned mechanics knowledge. They must not embed stale rotating-game claims as if they were current facts. Missing inputs remain unknown rather than becoming zero or false.

## Stable knowledge versus current external data

`data/knowledge/` contains pinned, versioned species/mechanics knowledge with provenance. It is not the owned collection and is not a source of current event/meta/raid rotation truth.

`data/external/` uses the separate #69 freshness-aware snapshot contract. Publishable external snapshots declare category, source/classification, timestamps, validity, licensing/attribution, join keys, and freshness policy. Consumers that require current game state must block or degrade when the required snapshot is stale, expired, failed, or unavailable.

The current external framework may legally publish zero active provider snapshots. Unavailable is a valid, explicit state.

## Static API v1

`api/v1/` provides stable versioned static paths for selected generated resources. API copies preserve the same underlying canonical contracts; they do not create a runtime database or query service.

Breaking endpoint-template or required-field changes require a new API major version. See `docs/public-data-api.md`.

## Build invariants

`scripts/validate_generated.py` validates both individual schemas and coordinated-build invariants. The current checks include:

- the manifest registry exactly matches all files published recursively under `data/`;
- declared resources exist and belong to the active build;
- declared byte sizes and checksums match where applicable;
- every public JSON data resource has a declared schema and validates against it;
- normalized record counts agree across canonical and aggregate resources where those resources exist;
- diagnostic warning/error counts reconcile;
- raw, normalized, and collapsed duplicate counts reconcile;
- duplicate-group and scan-quality references resolve to canonical record IDs;
- canonical record IDs are present and unique within a build;
- selective species/family/view resources resolve to canonical records and obey their partition/subset contracts;
- recommendation/candidate/investment/reasoning references resolve and preserve explicit unknown/current-data boundaries;
- collection shards reconstruct canonical records exactly with no duplicates or omissions;
- every collection shard stays under its configured hard byte maximum;
- stale or undeclared generated files cause validation to fail.

A validation failure blocks the normal Pages deployment. Issue #80 builds on these invariants for staging, promotion, last-known-good behavior, and rollback rather than defining a separate validation model.

## Determinism

Build timestamps and build IDs may legitimately differ between two executions. Canonical collection facts derived from the same source export must remain equivalent, including normalized records, collection summary, duplicate reconciliation, scan-quality findings, selective resources, deterministic reasoning, and shard record boundaries for the same configured target.

## Self-referential resources

`pokemon.json` embeds the active manifest, and the manifest describes itself. To avoid impossible recursive hashes, the resource registry intentionally omits a checksum for `build-manifest.json` and for the self-referential `pokemon.json` payload. Other generated resources use byte sizes and SHA-256 checksums where useful.

## Failure behavior

Malformed or internally inconsistent resources must never be treated as a healthy build. Validation errors are expected to be actionable in GitHub Actions logs. The deployment workflow runs these checks before publishing the Pages artifact.
