# Privacy-safe Share and Decision Packets

Share packets are browser-generated, bounded artifacts for discussing one decision without sending the complete collection. They do not alter canonical collection data or durable browser-local planning state.

## Versioned envelope

Current `schema_version`: `1.0.0`.

Every packet contains:

- `schema_version`
- `packet_type`
- `generated_at`
- `build.id`
- optional `build.collection_generated_at`
- `subject.title`
- at most 12 exact canonical `record_ids`
- at most 24 `claims`, with optional evidence metadata
- at most 24 `assumptions`
- at most 24 `unknowns`
- at most 12 public links
- bounded sanitized `context`
- explicit `privacy` metadata

Supported packet types are `pokemon-decision`, `comparison`, `team`, `event-plan`, `resource-plan`, `rescan-request`, `trade-shortlist`, and `diagnostic`.

## Current-view handoff

A lightweight bridge in the already-global glossary experience adds **Share current view** to non-Tools pages. The full Share Packet engine remains Tools-only so this workflow does not add the larger packet bundle to every page.

The bridge transfers a bounded draft to the existing Tools preview through `sessionStorage`. It captures only intentionally narrow state:

- the current page title and relative page path;
- an appropriate packet type inferred from the current tool page;
- exact record IDs only when they are explicitly selected in supported DOM state or supplied by an exact-record URL parameter;
- an explicit unknown when no exact owned record is selected.

It does not scrape arbitrary form fields, private notes, page text, or the full collection. No sensitive user field is read into the bridge draft. The draft is consumed and removed when Tools loads, then the normal packet redaction, build-ID verification, and exact preview run before any copy, download, or Web Share action.

This is session-only handoff state. It is not part of collection data, enrichment data, backup/restore, or durable planning state.

## Evidence semantics

Claim evidence preserves supported fields from the shared evidence contract, including authority, freshness, confidence, status, source, reviewed/retrieved timestamps, dataset/model/version, and rule ID. Missing evidence remains missing. Unknown facts belong in `unknowns`; they are never converted to false or zero.

## Privacy boundary

Default packets remove friend code, trainer identifiers, nicknames, precise location/address fields, source row indexes, scan/catch dates, and private note fields from custom context. Large arrays presented as an entire collection are replaced with an omission marker. Exact canonical record IDs are permitted because they are needed to make a bounded decision auditable.

The UI exposes an explicit sensitive-context opt-in. The exact serialized output is always displayed before copy, download, or Web Share. This opt-in does not change the public deployment privacy profile and must be reviewed for each packet.

## Formats

- Markdown/text for chat, forums, and notes.
- Stable pretty-printed JSON for machine/LLM review.
- Standalone escaped HTML suitable for printing or saving.
- Clipboard and Web Share are progressive browser enhancements.

The machine packet is intended to let an external assistant answer a bounded question without requiring `pokemon.json`.

## Determinism and limits

For identical inputs and an identical supplied `generated_at`, the packet object and machine JSON serialize deterministically by sorted object keys. Runtime generation uses the current timestamp, so packets created at different times intentionally differ in `generated_at`.

Bounds prevent this tool from becoming an alternate full-collection export path. The canonical export and privacy-profile systems remain the authority for collection-wide publication.
