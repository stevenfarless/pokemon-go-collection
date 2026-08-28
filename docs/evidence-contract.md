# Trust and evidence contract

The site uses one typed evidence vocabulary for consequential claims. The contract is published as `data/evidence-contract.json`, individual evidence objects follow `data/evidence.schema.json`, and `data/evidence-index.json` maps important UI surfaces to the same machine semantics.

## Evidence kinds

| Kind | Meaning |
| --- | --- |
| `canonical-owned` | A fact from the normalized owned collection, normally originating in Poke Genie export data. |
| `official-current` | A current fact from a reviewed Official source. |
| `verified-community` | Reviewed community data that is not an Official source. |
| `simulation` | A model result under explicit assumptions. It is never presented as an Official outcome. |
| `calculated` | A deterministic calculation or inference from supported inputs. |
| `browser-local` | A user-confirmed fact stored only in browser-local state. |
| `reported` | Reported information with lower source authority than reviewed Official/community data. |
| `datamined` | Datamined information, explicitly labeled as such. |
| `outdated` | Evidence whose source is stale or expired. It is retained for provenance, not treated as current. |
| `unknown` | Missing, unsupported, or unclassified evidence. Unknown never means false, zero, or not valuable. |

## Independent dimensions

Evidence type, freshness, and confidence answer different questions.

- **Evidence type** says what kind of claim this is and who or what produced it.
- **Freshness** says whether time-sensitive external data is still inside its declared age and validity window.
- **Confidence** says how strongly the available inputs support a calculated or simulated result.
- **Prerequisites** name requirements that are satisfied, missing, stale, unsupported, or unknown.
- **Uncertainty** preserves known limits instead of silently converting them into negative values.

A fresh source can still support a low-confidence calculation if owned inputs are incomplete. A high-confidence deterministic calculation can still be based on no current-game data at all. These states must not be collapsed into one score.

## Consequential actions

Irreversible or high-cost guidance must expose the relevant prerequisites one disclosure away. Examples include evolution, Hyper Training, and resource-heavy build decisions. The static site cannot confirm the final Pokémon GO screen, account balance, or eligibility at action time, so the evidence contract keeps that prerequisite explicit and supplies a remediation step.

## Browser presentation

`site/evidence.js` exposes `CollectionEvidence` and renders an accessible `<details>` disclosure with:

- visible evidence wording in addition to styling,
- source authority,
- freshness and its reason,
- confidence and its reason,
- source URL, timestamps, data/model version,
- assumptions and rule trace,
- prerequisites and remediation,
- uncertainty.

The component also provides compatibility upgrades for older `.ds-source-chip` surfaces and for runtime simulation cards while roadmap features migrate to native typed evidence.

## Machine-readable integration

During the canonical build, `scripts/evidence_contract.py` annotates Today cards and Event Calendar entries with typed `evidence` objects. It also publishes page-level evidence for consequential planning surfaces and a central evidence index for clients and LLMs.

The evidence asset is injected globally by `scripts/evidence_integration.py`, added to the canonical asset manifest, and included in offline precache. This keeps the trust vocabulary available on every generated page without introducing a runtime backend.
