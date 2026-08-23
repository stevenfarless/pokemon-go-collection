# Decision and action workflows

Issues #129-#132 add human workflow surfaces without changing the canonical collection or inventing unsupported game facts.

## Exact-record decisions

`data/decisions/records.json` is keyed by canonical `identity.record_id`. A decision card always presents the same recommendation regardless of Essential, Detailed, or Expert guidance. Higher guidance levels only reveal additional evidence. Missing or stale evidence can block a consequential recommendation, but absence of a protection flag is never interpreted as safe-to-transfer evidence.

Explicit protections are limited to fields represented by the normalized export. Shiny, costume, background, Max/Gigantamax state, trade reservations, legacy-move status, and other unsupported owned states remain unknown unless another supported source explicitly represents them.

## What changed?

`changes.html` consumes `data/change-timeline.json`. Its lanes are intentionally different evidence types:

- collection history uses the conservative #63 cross-build matcher;
- local planning is summarized in-browser by namespace health/count/version only, never by publishing note or goal contents;
- mechanics uses the reviewed #123 registry with source, authority, and applicability dates;
- current game uses only snapshots that #124 marks fresh;
- app entries are user-facing release notes, not raw commit noise.

A record missing from the latest export is described only as no longer present in the normalized export. It is never asserted to have been transferred. Each lane is bounded to keep rendering predictable.

## Action Packs

`action-packs.html` converts supported app recommendations into Pokémon GO handoffs. Generated search text uses the reviewed official inventory-search contract from #123. Every generated record search is labeled a locator rather than an exact record selector because Pokémon GO cannot search the companion's canonical IDs.

Each pack includes a warning, optional temporary tag, ordered steps, narrow search batches, and representational gaps. Duplicate review is not a blind transfer list. Evolution, TM, trade, and resource-spend actions remain explicitly consequential. Current move-window and Frustration packs fail closed unless a fresh reviewed external snapshot supplies the needed opportunity evidence.

## Scan Inbox and local preflight

`scan-inbox.html` combines the published scan-quality/recommendation blockers with a browser-only CSV preflight. The preflight contract is generated from the same `schema_contracts`, `semantic_validation`, and filename rules used by the production Python build. Shared fixtures exercise both implementations.

Selected CSV bytes are read with `File.text()` and are not posted or uploaded by the application. A passing local preflight is advisory only. The selected export becomes canonical only after it is committed under `exports/`, passes the existing production validation workflow, and is deployed.

When GitHub Pages hosting reveals the repository owner/name from the `github.io` URL, the UI may offer a normal GitHub `exports/` upload-page link after preflight passes. Otherwise it gives repository-neutral manual instructions. Web Share Target or file-handler support is optional progressive enhancement and is not required for the standard file picker/drop workflow.
