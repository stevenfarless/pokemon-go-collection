# Pokémon GO knowledge snapshot

This directory contains a repository-local, versioned mechanics/species layer that is separate from the owned Pokémon collection.

## Authority and provenance

The current source lock is `source-lock.json`. It pins a full PvPoke commit and the exact upstream Pokémon game-master and mechanics files used to generate the snapshot. The generated data is classified **Verified community data**, not official Niantic data.

PvPoke is distributed under the MIT License. The required attribution and license text are preserved in `PVPOKE-LICENSE.txt`.

The source is intentionally pinned rather than fetched from an unversioned `main` URL. A knowledge update is therefore an explicit repository change with a reviewable upstream commit and effective date.

## Generated resources

- `pokemon-go.json`: complete normalized species/form/mechanics snapshot
- `pokemon-go.schema.json`: JSON Schema for the complete snapshot
- `species-index.json`: compact dex/species/form/family/type index for browsers and LLMs
- `species-index.schema.json`: JSON Schema for the compact index

Run `python scripts/sync_knowledge.py` to regenerate these files from the pinned source. The GitHub workflow `.github/workflows/sync-knowledge.yml` runs the same synchronizer and commits deterministic generated changes when the source lock or synchronizer changes.

## What is included

Where the pinned source supplies reliable fields, the snapshot includes Pokédex identity, PvPoke species/form IDs, display names, normalized form keys/aliases, Pokémon GO base stats, typing, family relationships, buddy distance, move-pool snapshot, second Charged Move Stardust cost, Mega/Primal transformation entries, release state, source tags, and the CP multiplier table used for deterministic CP/HP plausibility checks.

Shadow entries in PvPoke are deliberately not duplicated as separate species/forms. Shadow/Purified remains an owned-record status in this project.

## Explicit unknowns

The snapshot does not invent fields absent from the pinned source. Evolution Candy/special requirements, second Charged Move Candy cost, Shadow/Purified investment modifiers, and Dynamax/Gigantamax eligibility remain `null` or explicitly described as unknown until a redistribution-compatible source is adopted.

Move pools are a versioned snapshot, not a claim about current event-exclusive availability, raid rotations, PvP meta strength, or current event bonuses. Those belong to the future freshness-aware current-game-data layer.

## Updating the source

1. Review a newer PvPoke commit and its license/provenance.
2. Update `source-lock.json` with a full 40-character commit and effective date.
3. Push the source-lock change. The knowledge sync workflow regenerates the snapshot.
4. Review the generated diff, especially new/removed forms, base-stat changes, family changes, move-pool changes, and CP multiplier changes.
5. Run the normal repository validation before merging.

Do not replace the pinned source with a runtime API dependency. Production builds consume the committed snapshot and require no network access.
