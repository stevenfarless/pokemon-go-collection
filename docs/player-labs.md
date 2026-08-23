# Player labs contracts

Issues #133 through #137 share one rule: canonical owned facts, versioned static knowledge, reviewed mechanics, and freshness-checked rotating data must remain distinguishable. Missing information is never converted to a negative fact, and irreversible actions are never automated.

## Naming Studio

`data/naming-studio.json` publishes exact owned-record inputs and fixed-width encodings. `iv45` is 00-45, `ivpct3` is 000-100, and `iv1000` is 0000-1000 so lexical sorting preserves their numeric order. The browser counts Unicode code points in the exact generated nickname and warns above the configured 12-character field budget. The built-in symbol palette is deliberately conservative ASCII. Additional symbols are stored only after the user paste-tests them on their own device.

General, PvP, Raid, Trade, and Cleanup presets are browser-local. The Action Pack index may recommend one of those presets, but recommendation and copy are the end of the integration. There is no account control, batch rename automation, custom keyboard claim, or Terms-of-Service-sensitive automation.

## Collection Gap Radar

The published Living Dex denominators are tied to the pinned knowledge dataset and source commit. Unreleased entries and transformations such as Mega/Primal forms are excluded from ordinary species/form denominators. Browser-local goal exclusions recompute the effective denominator without modifying canonical data.

Canonical fields support Lucky, hundo, nundo, and exported PvP evidence. Shiny, costume, background, Dynamax, and Gigantamax remain Unknown until explicitly supplied by local enrichment. Unknown never means no. Fresh event, raid, research, or egg facts are shown only when the external-data framework marks their snapshot fresh and the fact has a canonical numeric Pokémon identifier.

## Roster Readiness

Roster score version 1.0.0 is a deterministic collection-readiness heuristic, not a battle simulation. Known components are weighted CP 50%, IV percentage 20%, level 15%, and move completeness 15%. Missing components are omitted from the weighted mean rather than treated as zero, while confidence is reduced and the missing fact is shown. The usable threshold is 65 and the strong threshold is 80.

The page always provides a text equivalent for the 18-type matrix and a Show my six drilldown. Preferred exact records can be locked locally by type. Current raid, Max, or Rocket overlays remain disabled even when fresh matchup data exists until a supported simulator is connected. Static type readiness must not masquerade as current boss performance.

## Evolution Lab

Evolution branches come from the pinned family graph. Candy and special requirements remain Unknown if the knowledge snapshot does not provide them. Unknown requirements block a definitive evolve-now recommendation. CP projection is produced only when exact IVs, exact level, target base stats, and the pinned CP multiplier are all available. Projection states its assumptions and reports generic 500/1500/2500 cap crossings without claiming cup eligibility.

A current exclusive-move/evolution window requires a fresh external event or move fact with an explicit move-availability signal. Static move pools cannot create that claim. Gigantamax or other no-evolve blocking is applied only when the reviewed mechanics registry explicitly publishes the relevant restriction and the owned state is explicitly known.

## Move Lab

Stable learnable move pools are versioned reference data only. Ordinary TM, Elite TM, evolution/event availability, Frustration-removal windows, and move-change relevance require fresh explicit rotating evidence. Purification is never recommended merely to remove Frustration because it permanently changes Shadow state.

The Elite TM Vault is a browser-local planning queue containing exact record ID, desired move, rationale, wait/event alternative, freshness state, owned alternatives, and an exact Action Pack handoff. The application does not infer the trainer's Elite TM count and does not spend resources.

## Local backup

The lab namespaces are `pokemon-go-collection:naming-presets:v1`, `pokemon-go-collection:gap-goals:v1`, `pokemon-go-collection:roster-locks:v1`, and `pokemon-go-collection:elite-tm-vault:v1`. On the Tools page, the player-labs compatibility bridge extends the existing unified local-data envelope with these namespaces. Restore validates both the base namespaces and lab namespaces before applying them and rolls back the known local keys if a write fails.
