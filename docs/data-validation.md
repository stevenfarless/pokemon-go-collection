# Poke Genie export validation policy

The production build validates CSV values before normalization and then applies semantic/contract validation to the normalized collection and all generated public resources.

## Source-level CSV validation

Diagnostics identify the CSV row number, Poke Genie source index, Pokémon name when available, column, offending value, severity, and the action taken.

Fatal errors stop deployment. They include a missing Pokémon name and missing, non-numeric, decimal, or non-positive values for `Pokemon Number` and `CP`. The build never falls back to an older export when the newest selected export is invalid.

Malformed optional fields create warnings. The affected field is replaced with a missing value before normalization, preventing corrupted data from being published as a legitimate number. This covers HP, IVs, IV percentage, levels, dimensions, dust and candy costs, PvP ranks, stat products, status codes, and booleans. Blank optional fields are treated as intentionally missing and do not create warnings.

Recognized Shadow/Purified codes are `0` normal, `1` Shadow, and `2` Purified. Unknown codes are never silently treated as ordinary data. Supported level values are validated against the collection contract and expected half-level increments. IV components must be integers from 0 through 15, and percentages must be from 0 through 100.

Each successful build publishes source/build diagnostics and records warning/error counts in the authoritative manifest.

## Canonical identity and duplicate reconciliation

Normalization assigns canonical record IDs and preserves scan provenance. Conservative duplicate-scan reconciliation occurs before downstream duplicate/trade review tools operate.

Validation proves that:

- canonical record IDs are unique within a build;
- reconciled repeated scans do not reappear as independent owned records;
- provenance links remain internally consistent;
- ambiguous cross-build matching is preserved as ambiguity rather than silently reassigned;
- distinct identical-looking canonical records remain independently addressable.

Browser-local annotations are outside the generated public dataset, but their migration logic is tested against canonical identity semantics.

## Semantic species/form and CP/HP validation

The build consumes the pinned, versioned stable knowledge snapshot to validate recognized species/forms and, when sufficient exact inputs exist, test CP/HP/level plausibility.

Semantic findings include review/rescan warnings such as unresolved species/form identity or implausible CP/HP/level combinations. Missing inputs skip a plausibility check rather than fabricating a result.

Stable knowledge validation is not used to infer rotating-game facts such as current event move availability, raid rotations, PvP meta strength, Rocket lineups, or Max Battle rotations.

## Generated-resource validation

After normalization, CI validates the complete generated static data product. This includes:

- canonical `pokemon.json` and build manifest contracts;
- bounded shard reconstruction and size/checksum rules;
- species/family resources and derived views;
- bounded history and collection diffs;
- recommendation, candidate, investment, and reasoning references;
- stable knowledge schemas/provenance;
- external-data snapshot metadata/freshness contracts when snapshots exist;
- static API copies and build-ID consistency;
- required hashed assets and human-facing pages.

Missing values remain explicit unknowns rather than becoming zero or false merely to satisfy a downstream calculation.

## Current external-data validation

The #69 external framework validates provider metadata, authority classification, timestamps, validity windows, licensing/redistribution fields, join keys, and category-specific freshness policy before a candidate snapshot can replace the last-known-good snapshot.

A malformed or failed refresh preserves the previous structurally valid snapshot, but its freshness is recalculated honestly. If no usable snapshot exists, the published consumer state is `unavailable`.

Current-data consumers must not reuse stale, expired, failed, reported, or datamined material as current official fact.

## Deployment behavior

Validation runs before Pages promotion. A candidate that fails source parsing, semantic checks, generated schemas/invariants, browser regression/accessibility testing, architecture policy, or promotion guards never replaces the current deployed site.

Tests cover malformed source values, duplicate/identity behavior, semantic plausibility, generated-resource cross-links, stale/malformed current-data behavior, and the no-provider external-data state.
