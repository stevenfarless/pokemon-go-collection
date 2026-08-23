# Advanced current-game and battle labs

Issues #138 through #142 add five collection-aware planners while preserving the repository's static GitHub Pages architecture and existing evidence boundaries.

## Shared evidence model

The labs distinguish four kinds of input:

1. **Owned canonical facts** come from the active Poke Genie export and canonical normalized records.
2. **Versioned static knowledge** comes from the pinned, license-reviewed knowledge snapshot. It can describe species stats, types, buddy distance, move pools, family relationships, and transformation capability, but does not prove a rotating current-game state.
3. **Reviewed mechanics/current facts** come from `data/mechanics/index.json` and freshness-checked `data/external/` snapshots. Current event, raid, or Max claims fail closed when no fresh reviewed snapshot exists.
4. **Browser-local user facts** are explicit planning state. They are never promoted into canonical owned facts and are included in the unified local-data backup.

Species capability is never treated as proof that an exact owned record has Mega history, Dynamax/Gigantamax status, Max Move progress, Hyper Training state, or another unexported property.

## Mega / Primal Lab

`mega-lab.html` and `data/mega-lab.json` expose exact owned records with versioned Mega/Primal transformation capability. The local namespace `pokemon-go-collection:mega-state:v1` can store first-Mega confirmation, Mega Level including Super Max, local Energy, cooldown/next-free notes, and project priority.

Super Max is intentionally represented separately from ordinary Mega Level progression. Current event/raid type matching is derived only from fresh external snapshots. A current objective recommendation is blocked when the exact record's Mega history/level is unknown or the required current snapshot is unavailable.

## Max Battle Lab

`max-battle-lab.html` and `data/max-battle-lab.json` keep Max Battle planning separate from ordinary raid readiness. The local namespace `pokemon-go-collection:max-state:v1` tracks exact-record Dynamax/Gigantamax confirmation, Max Attack/Guard/Spirit level, explicit Fast Attack type, optional G-Max attack type, local Max Particle balance, and priority.

A species being capable of a Max form does not make an owned record Max-eligible. The browser party builder uses only locally confirmed Max records. Current-boss planning is blocked without a fresh `max-battles` snapshot. Normal raid rankings and static roster scores are never labeled as Max simulations.

## Hyper Training Planner

`hyper-training.html` and `data/hyper-training.json` implement deterministic next-stat CP projection using the pinned base stats and CP multiplier table. Shadow and existing 4-star records are marked ineligible from the reviewed mechanic. Other records require explicit local Good Buddy-or-higher confirmation.

The local namespace `pokemon-go-collection:hyper-training:v1` stores optional Bottle Cap inventory/expiration, active training, buddy confirmation, targets/completed points, and training deadlines. User-entered dates remain visibly local and are not inferred from game state.

Every completed point is treated as irreversible. The planner shows the next point's CP and 500/1500/2500 cap warnings and compares known better-IV owned alternatives. Higher IV is never equated with better capped-league performance.

## Buddy Queue

`buddy-queue.html` and `data/buddy-queue.json` seed exact-record buddy projects from supported evolution and known build-resource inputs. Browser-local state at `pokemon-go-collection:buddy-queue:v1` adds user priority, pin, skip, completion, and optional deadlines.

Ranking is transparent: user priority, objective base priority, deadline urgency, pins, active Hyper Training, and locally favored Mega projects are explicit score components. Known buddy distance may be displayed, but it is not converted into guaranteed Candy, XL Candy, Adventure Sync, or Mega Energy outcomes.

## Raid Readiness

`raid-readiness.html` and `data/raid-readiness.json` define an independent deterministic readiness estimator. It does not copy Poke Genie or Pokebattler algorithms and does not require either service.

The current raid snapshot supplies only fresh reviewed boss identity/tier facts when available. If boss HP, defense, battle timer, or other model inputs are not in a reviewed source, the app requires explicit local assumptions rather than inventing them. Stale/expired current-boss data blocks simulation entirely.

The model uses only exact owned records. Versioned species stats, exact IVs/level when available, and move completeness produce transparent DPS-style and TDO-style proxies. TTW/range, faint pressure, relobby risk, and practical/not-practical wording are simulation outputs, not Official facts or guarantees. Every result includes model version and assumptions.

The local namespace `pokemon-go-collection:raid-assumptions:v1` stores user-entered assumptions per boss. Investment advice links back to existing investment inputs and Move Lab rather than creating a second opaque spending engine.

## Backup and recovery

Advanced namespaces extend the existing unified local-data envelope instead of replacing it. `site/advanced-labs.js` validates base local data, player-lab extensions, and advanced-lab extensions before writing. Restore snapshots all known keys and rolls back best-effort if any write fails.

The advanced Tools bridge is inserted before the earlier player-lab bridge so one capture-phase handler can compose the base, player-lab, and advanced namespaces into a single export/restore workflow.

## Current-data failure behavior

- Missing current snapshot: current recommendation unavailable.
- Stale/expired current snapshot: retained as provenance where applicable, but blocked from current planning.
- Missing exact owned/local fact: displayed as unknown, not false.
- Missing raid model input: simulation blocked, not guessed.
- Missing Max owned-state confirmation: excluded from Max party selection.
- Missing Mega history/level: Energy/cooldown recommendation blocked.

No lab performs Pokémon GO account access, in-game automation, automated renaming, automated transfers, or automated resource spending.
