# External game-data framework

This document defines the provider-independent current-game data boundary introduced by issue #69. Owned collection facts remain under `data/pokemon.json` and its derived resources. Time-sensitive PvP, raid, move, event, Rocket, and Max Battle facts belong to a separate external snapshot layer.

## Architectural boundary

The core collection must build and function when `data/external/index.json` reports `overall_freshness: unavailable`. No external provider, account, API key, runtime server, database, paid API, or SaaS subscription is required. This preserves the permanent zero-cost GitHub-only architecture from #70.

Provider integrations may later run in GitHub Actions when acquisition and redistribution are legally permitted. A provider-specific adapter must normalize its source into the common snapshot contract before publication. Consumers read normalized metadata rather than provider-specific fields.

## Normalized snapshot contract

Every publishable snapshot records:

- `provider`: human-readable provider identity;
- `source_reference`: source URL, repository path, or attribution reference;
- `retrieved_at`: when the source was acquired;
- `dataset_timestamp`: when the dataset represents its facts;
- `effective_game_context`: season/version context when supplied;
- `validity.valid_from` and `validity.valid_until` when a source has a defined window;
- `data_category`: `pvp`, `raids`, `moves`, `events`, `rocket`, `max-battles`, or `mechanics`;
- `classification`: `Official`, `Verified community data`, `Simulation result`, `Datamined`, or `Reported` for accepted provider payloads;
- `data_version` and provider `schema_version`;
- explicit license, attribution, and redistribution permission;
- `join_keys` used to connect facts to canonical species/mechanics or owned-record data;
- `freshness_policy.max_age_hours` and failure behavior;
- normalized `facts`.

`Outdated` and `Unavailable` are consumer states, not source claims. A provider payload cannot self-promote itself into either state or bypass freshness calculation.

## Authority classifications

`Official` means the snapshot is derived from an official Pokémon GO/Niantic source under an acquisition and redistribution method permitted for this project. `Verified community data` identifies maintained community data with verified provenance and usable terms. `Simulation result` identifies modeled outputs. `Datamined` and `Reported` remain explicitly distinct from official confirmation.

Consumers must display or preserve the classification when a recommendation depends on a snapshot. They must not rewrite `Datamined` or `Reported` as confirmed information.

## Freshness states

The framework computes freshness from the dataset timestamp, optional validity window, and provider policy:

- `fresh`: within the configured maximum age and validity window;
- `stale`: older than `max_age_hours`;
- `expired`: outside an explicit validity window;
- `unavailable`: no usable snapshot exists;
- `failed-update`: an update attempt failed validation. The previously published snapshot remains the data source if it is still structurally valid, with its independently recalculated freshness state.

A stale or expired snapshot may remain available for provenance/history, but consumers must degrade explicitly and cannot silently present its time-sensitive claims as current.

## Update and fallback transaction

A provider refresh follows this sequence:

1. Acquire the candidate snapshot without modifying the published last-known-good file.
2. Validate required metadata, license/redistribution permission, category, classification, join keys, timestamps, and freshness policy.
3. Normalize the candidate into the provider-independent schema.
4. Validate the normalized JSON Schema.
5. Only then replace the last-known-good snapshot.
6. On malformed input, licensing failure, network failure, or adapter failure, keep the previous valid snapshot and record the failed-update event.
7. If no previous valid snapshot exists, publish an unavailable state rather than malformed or guessed data.

This is a build-time/static transaction. It requires no runtime service.

## Cache and retention

Generated consumers should use dataset timestamps and data versions as cache identity. Provider adapters should retain one current last-known-good snapshot plus only the bounded history needed for debugging or provenance. Large unbounded caches are prohibited by #70.

GitHub Pages HTTP caching is infrastructure behavior outside this contract. Clients should compare snapshot metadata rather than assuming an HTTP cache hit is current.

## Join keys

Adapters must declare their normalized join keys. Preferred keys are stable identifiers already present in the repository-local mechanics layer, such as `species_id`, Pokédex number plus normalized form, or move identifiers. Owned-record joins should resolve through canonical collection `record_id` only when the external dataset truly addresses one owned record.

Provider adapters must not invent a competing species identity system when a #71 mechanics key is sufficient.

## Failure behavior for recommendations

A deterministic rule that requires current game data must expose the snapshot classification, dataset timestamp, freshness state, and version in its trace. If the required category is stale, expired, unavailable, or failed, the rule returns a blocker/review state.

Static collection-only rules, such as comparing Poke Genie IV percentiles or known exported build costs among owned copies, continue to work without external data.

## Test fixture

`tests/fixtures/external-game-data-example.json` is a repository-authored synthetic contract fixture. It exists only to prove normalization, freshness, validation, and last-known-good fallback behavior. It is not published as Pokémon GO game truth and does not create a provider dependency.

## Adding a provider later

A provider-specific issue must document acquisition method, license/terms, attribution, update cadence, expected failure modes, source authority, and category-specific freshness policy. Its adapter emits the normalized snapshot contract. Adding or replacing a provider does not alter the owned collection schema, deterministic reasoning rules, or core external freshness semantics.
