# Mechanics coverage architecture

`knowledge/mechanics-registry.json` is the reviewed source of truth for stable/current mechanics coverage. It records authority, review date, source references, implementation status, affected modules, and short normalized facts. It intentionally does not copy official help prose.

`data/mechanics/index.json` is generated from that registry and carries the active build ID plus supported/partial/unsupported counts and review age. `mechanics-coverage.md` is the human-readable generated report.

The scheduled/manual `Mechanics source change detection` workflow fingerprints normalized text from the small reviewed source list. A changed or missing baseline creates visible maintenance work. Source changes never modify facts automatically. Human review must update the normalized registry and then accept a new fingerprint.

Decision tools must treat `partial`, `unsupported`, or review-due mechanics as a prerequisite/blocker when the missing mechanic controls a consequential recommendation.
