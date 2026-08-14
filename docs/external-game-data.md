# External game-data framework

This document defines the provider-independent current-game data boundary introduced by #69 and populated for events/raids by #95. Owned collection facts remain under `data/pokemon.json` and its derived resources. Time-sensitive PvP, raid, move, event, Rocket, and Max Battle facts belong to a separate external snapshot layer.

## Current production status

The production build now accepts reviewed provider inputs under `external/providers/` and publishes normalized event and raid snapshots under `data/external/snapshots/`. `data/external/index.json` is the discovery and freshness boundary.

The initial production provider is `pokemon-go-official-human-reviewed`. Its repository inputs contain only reviewed factual metadata from named Pokémon GO official announcements, not copied article prose or images. Acquisition is explicitly marked `human-reviewed-factual-transcription` with `automated_source_scraping: false`.

This design is deliberate. The project does not operate a crawler against the official Pokémon GO news site. When official announcements change, a maintainer reviews the factual provider input and commits the updated metadata. The build then validates, joins, normalizes, and publishes it. If a reviewed input is malformed, the previous committed last-known-good input is preserved by the refresh transaction.

The current production categories are:

- `events`
- `raids`

Other current-game categories remain legitimately unavailable until a separately reviewed provider is added.

## Architectural boundary

The core collection must build and function even when `data/external/index.json` reports `overall_freshness: unavailable`. No external provider, account, API key, runtime server, database, paid API, or SaaS subscription is required. This preserves the permanent zero-cost GitHub-only architecture from #70.

Provider inputs are repository data. Build-time adapters normalize those inputs into the common snapshot contract. Consumers read normalized metadata rather than provider-specific source fields.

## Production input and output paths

Reviewed inputs:

- `external/providers/official-events.json`
- `external/providers/official-raids.json`

Committed fallback inputs:

- `external/last-known-good/official-events.json`
- `external/last-known-good/official-raids.json`

Generated outputs:

- `data/external/index.json`
- `data/external/snapshots/events-pokemon-go-official-human-reviewed.json`
- `data/external/snapshots/raids-pokemon-go-official-human-reviewed.json`

The generated files include the canonical build ID. They are also registered in the build manifest/resource registry, so mixed-build publication is detectable.

## Normalized snapshot contract

Every publishable snapshot records:

- `provider`: human-readable provider identity;
- `source_reference` and optional `source_references`;
- `retrieved_at` and `dataset_timestamp`;
- `effective_game_context`;
- `validity.valid_from` and `validity.valid_until` when defined;
- `data_category`;
- `classification`: `Official`, `Verified community data`, `Simulation result`, `Datamined`, or `Reported`;
- `data_version` and provider `schema_version`;
- explicit acquisition metadata;
- explicit license/redistribution metadata;
- `join_keys`;
- `freshness_policy.max_age_hours` and failure behavior;
- normalized `facts`;
- calculated `freshness`;
- current build ID and generated snapshot path.

`Outdated` and `Unavailable` are consumer states, not source claims.

## Authority classifications

`Official` means the factual metadata was reviewed against an official Pokémon GO source and source-attributed. `Verified community data` identifies maintained community data with verified provenance and usable terms. `Simulation result` identifies modeled outputs. `Datamined` and `Reported` remain explicitly distinct from official confirmation.

Consumers must preserve the classification when advice depends on a snapshot.

## Freshness and review cadence

The framework computes freshness from the reviewed dataset timestamp, optional validity window, and provider policy:

- `fresh`: within the configured maximum age and validity window;
- `stale`: older than `max_age_hours`;
- `expired`: outside an explicit validity window;
- `unavailable`: no usable snapshot exists;
- `failed-update`: an attempted replacement failed validation.

The initial event/raid inputs use their explicit event/rotation validity windows plus a bounded age policy. A maintainer should update the reviewed input whenever the official announcement changes or before extending a snapshot beyond the facts that were actually reviewed. Merely rebuilding the site must never change the reviewed `dataset_timestamp`.

`.github/workflows/refresh-external-freshness.yml` runs on a six-hour schedule and dispatches the normal validated Pages workflow. This does not scrape or acquire new facts. It rebuilds from the unchanged reviewed provider inputs so `age_hours`, validity, and `fresh`/`stale`/`expired` state are recalculated even when no new Poke Genie export or provider edit occurs. The scheduled job therefore cannot make old source facts look newer by changing `dataset_timestamp`.

A stale or expired snapshot may remain published for provenance, but freshness-gated consumers must refuse to present it as current.

## Update and fallback transaction

A reviewed provider update follows this sequence:

1. Review the named official source and update factual metadata in `external/providers/`.
2. Do not copy article prose or images into the repository.
3. Validate required metadata, category, classification, explicit redistribution flag, join keys, timestamps, validity, and freshness policy.
4. Normalize the candidate into the provider-independent schema.
5. Validate Pokémon references against the pinned species index when a stable key exists.
6. Publish the normalized snapshot only after validation.
7. On malformed candidate input, preserve the corresponding committed last-known-good snapshot and recalculate its freshness.
8. If neither candidate nor previous input is usable, degrade to unavailable.

This is a static build transaction. There is no background application server.

## New or not-yet-pinned forms

Current official game facts can appear before the pinned stable species dataset knows a new form/transformation identifier. In that case the provider must not invent a `species_id`. It may join by a stable Pokédex number and preserve the current form text as source-attributed external metadata, while explicitly indicating that a pinned stable species ID is not yet available.

## Cache and retention

Generated consumers should use build ID, dataset timestamp, data version, and freshness metadata as cache identity. The repository keeps one current reviewed provider input and one committed fallback input per category. Unbounded provider caches are not required.

GitHub Pages HTTP caching is outside this contract. Production smoke tests compare build IDs and use bounded retry/backoff so a temporarily stale CDN response is never accepted as the just-deployed build.

## Join keys

Adapters declare normalized join keys such as `species_id` or Pokédex number/form. `validate_snapshot_join_keys()` recursively rejects unknown stable identifiers and unknown Pokédex numbers where those fields are present.

A newly announced form that lacks a pinned identifier must remain explicit rather than being coerced into an invented stable key.

## Failure behavior for recommendations

A deterministic rule that requires current game data must expose snapshot classification, dataset timestamp, freshness state, and version. If the required category is stale, expired, unavailable, or failed, the rule returns a blocker/review state.

Collection-only rules continue to work without external data.

## Test and deployment coverage

`tests/fixtures/external-game-data-example.json` remains a synthetic contract fixture, not game truth.

Production adapter tests additionally verify:

- event and raid inputs normalize as `Official`;
- automated official-site scraping is disabled;
- redistribution metadata is explicit;
- stable Pokémon joins validate;
- event and raid snapshots are generated and registered;
- malformed refreshes preserve last-known-good data;
- stale/expired states are explicit.

The post-deployment #97 smoke verifier then checks the public `data/external/index.json` and every listed generated snapshot against the promoted build ID.

## Adding another provider

A provider-specific change must document acquisition method, source terms, attribution, review/update cadence, expected failure modes, authority classification, validity, and freshness policy. It must not introduce a paid dependency or silently merge rotating facts into canonical ownership data.
