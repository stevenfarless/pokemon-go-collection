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

The normalized Pokémon payload and build manifest use explicit schema/manifest versions. Resource-specific reports may also expose their own `schema_version` or policy version.

Compatibility policy:

- Additive optional fields may be introduced without invalidating existing consumers when the documented meaning of existing fields does not change.
- Adding a new optional resource is additive. It becomes required only for builds that declare it in the resource registry.
- A breaking change to required fields, field types, identity semantics, or existing field meaning requires the appropriate schema/manifest version to change.
- Consumers should discover resources through the manifest instead of assuming every future resource exists.
- Consumers should reject or explicitly degrade when a required schema version is unsupported rather than silently interpreting incompatible data.

## Build invariants

`scripts/validate_generated.py` validates both individual schemas and coordinated-build invariants. The current checks include:

- the manifest registry exactly matches the files published under `data/`;
- declared resources exist and belong to the active build;
- declared byte sizes and checksums match where applicable;
- every public JSON data resource has a declared schema and validates against it;
- normalized record counts agree across the canonical collection, summary, Data Health, Insights, manifest, deduplication report, and scan-quality report where those resources exist;
- diagnostic warning/error counts reconcile;
- raw, normalized, and collapsed duplicate counts reconcile;
- duplicate-group and scan-quality references resolve to canonical record IDs;
- canonical record IDs are present and unique within a build;
- precomputed filter species agree with canonical collection records;
- stale or undeclared generated files cause validation to fail.

A validation failure blocks the normal Pages deployment. Issue #80 builds on these invariants for staging, promotion, last-known-good behavior, and rollback rather than defining a separate validation model.

## Determinism

Build timestamps and build IDs may legitimately differ between two executions. Canonical collection facts derived from the same source export must remain equivalent, including normalized records, collection summary, duplicate reconciliation, and scan-quality findings. CI regression tests compare those deterministic outputs directly.

## Self-referential resources

`pokemon.json` embeds the active manifest, and the manifest describes itself. To avoid impossible recursive hashes, the resource registry intentionally omits a checksum for `build-manifest.json` and for the self-referential `pokemon.json` payload. Other generated resources use byte sizes and SHA-256 checksums where useful.

## Failure behavior

Malformed or internally inconsistent resources must never be treated as a healthy build. Validation errors are expected to be actionable in GitHub Actions logs. The deployment workflow runs these checks before publishing the Pages artifact.
