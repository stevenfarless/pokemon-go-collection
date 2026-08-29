# Source, license, and attribution registry

The canonical external-input review record is [`knowledge/source-registry.json`](../knowledge/source-registry.json). The production build validates that registry through `scripts/source_registry.py` before current external-provider data is published.

This document describes the repository's maintenance policy. It records the basis used by this project and is not a substitute for legal advice.

## Build contract

The build fails when any of these conditions is true:

- a committed production provider under `external/providers/` has no single active reviewed registry owner;
- a provider marked for redistribution lacks both provider-level permission metadata and a reviewed central redistribution record;
- an active registry provider ID has no production provider file, preventing a discontinued source from leaving an orphaned current-data claim;
- the pinned PvPoke commit, date, or license no longer matches its reviewed registry entry;
- a required license/notice or governed source path is missing;
- a direct Python build/test dependency changes without updating its reviewed package/version/license record;
- source HTML or CSS loads a remote script, stylesheet, font, image, or similar runtime asset without a future reviewed exception.

The same registry generates:

- `credits.html`, the human-readable Credits & Data Sources page linked from the built collection footer;
- `data/provenance/index.json`, the machine-readable provenance and dependency inventory;
- an exact npm dependency inventory from `package-lock.json` and the reviewed direct Python dependency inventory from `requirements-dev.txt`.

The final build resource registry automatically indexes the generated provenance JSON under `data/`.

## Current production external inputs

### PvPoke stable/versioned knowledge

PvPoke supplies the pinned stable Pokémon GO reference inputs described by `knowledge/source-lock.json`. The exact reviewed commit and date must match the source registry. The repository retains `knowledge/PVPOKE-LICENSE.txt` and republishes that notice with the generated knowledge resources.

The project intentionally excludes rotating meta rankings from the stable knowledge snapshot and does not import PvPoke UI, article prose, artwork, or other visual assets.

### Official Pokémon GO announcements

Official announcement pages are used only for human-reviewed factual transcription into the committed provider snapshots. The repository does not automatically scrape official pages. Provider records retain per-record source URLs and review metadata.

The current source review records the Scopely Explore terms state reviewed on August 29, 2026. The repository policy remains narrower than simply copying publicly visible material: article prose, artwork, sprites, icons, logos, screenshots, and other official visual Content are excluded.

If official terms or access rules change, current-data updates stop until the registry is reviewed again. Removing or replacing the source must also remove or deactivate its provider IDs so the build cannot silently retain an orphaned claim.

### Poke Genie user-export compatibility

The repository accepts user-supplied Poke Genie CSV exports and normalizes collection facts plus Poke Genie-calculated fields contained in those exports. It does not redistribute Poke Genie application code, artwork, screenshots, prose, or proprietary visual assets.

A format change should be handled as a parser and source-policy change together. Existing user-owned collection data can then be migrated to a documented replacement format if necessary.

### Pokémon identifiers and trademarks

Species and character names are used descriptively to identify records. The registry does not assert a license to Pokémon trademarks, logos, sprites, artwork, icons, or other visual assets. The application uses repository-authored UI and identifies itself as an unofficial fan-maintained project without implied endorsement.

## Dependencies and assets

`package-lock.json` is the exact npm dependency source for CI/browser test tooling. `data/provenance/index.json` publishes every locked package name, version, declared lockfile license identifier, resolved source, and integrity value available in the lockfile. These packages are build/test tooling and are not third-party runtime resources for the static site.

`requirements-dev.txt` contains exact direct Python pins. Their reviewed names, versions, and license identifiers live in the source registry. A pin change fails source-registry validation until the review record changes with it.

The current application has no registered remote runtime asset provider. A new remote script, stylesheet, font, icon, or image therefore fails the source audit. Prefer repository-authored local UI assets. If a future third-party asset is necessary, add its exact source/version, license or terms basis, notice requirements, redistribution/modification boundaries, acquisition method, and removal plan before enabling it.

## Adding a new external provider

Before a production feature adopts a new source:

1. Add a reviewed `knowledge/source-registry.json` entry with the source/project, exact revision or review target/date, license or terms basis, attribution, redistribution/modification boundaries, excluded prose/images/assets, classification, authority, acquisition/refresh method, active provider IDs, governed paths, and removal/replacement plan.
2. Keep factual data, compilation rights, API/access terms, rate limits, and redistribution permissions as separate review questions. Public visibility alone is not treated as redistribution permission.
3. Add or retain any required license/notice file in the repository and reference it from the registry.
4. Add the normalized provider only after the registry record exists. Official-site sources remain human-reviewed/manual unless a future terms review explicitly supports another acquisition method and the repository policy is intentionally changed.
5. Add focused tests for the new provider and run the canonical build so the provenance index and Credits page are generated from the reviewed record.

## Removing or replacing a source

A source removal is one change set: remove or deactivate the registry provider claim, remove/replace the provider input and derived current-data consumers, update required notices, and run the canonical build. The orphan-provider check exists so a discontinued source cannot continue to appear as an active reviewed basis after its production data has been removed.

For pinned reference knowledge, replace the source lock and reviewed registry metadata together. For dependency changes, update the lock/pin and its reviewed license inventory together.
