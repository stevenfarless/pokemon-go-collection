# Quality engineering contract

This project treats tests as executable safety constraints around deterministic collection logic. The contract is intentionally small enough to run on GitHub Free and is designed to ratchet upward as the codebase grows.

## Coverage gates

Python coverage is measured with branch coverage enabled. Pull requests must keep the protected build/normalization modules at or above the initial 55% aggregate line/branch threshold. Full repository coverage is still emitted as an artifact so uncovered high-risk areas remain visible instead of disappearing outside the gate.

JavaScript coverage uses c8 over the collection search, dashboard query engine, and browser-local data/migration logic. The initial floor is deliberately conservative: 30% lines/statements and 20% branches/functions. The floor is a regression guard, not a quality target. Raising it is expected when tests are added; lowering it requires an explicit reviewed configuration change.

Generated files, vendored data, HTML templates, and trivial glue are excluded from coverage accounting. A passing percentage never overrides a failed deterministic safety test.

## Mutation testing

`scripts/run_mutation_checks.py` performs a bounded mutation pass over build logic whose failure could publish the wrong export or weaken reproducibility. The seeded mutations currently alter:

- content-hash width;
- required-column rejection;
- hidden export exclusion.

Each mutation is applied in an isolated temporary copy and the focused build test suite is executed. CI fails if any seeded mutant survives. This makes the assertions prove that they detect a real behavioral weakening rather than merely executing lines.

The mutation set should stay selective. Add a mutant when a high-risk deterministic rule gains a meaningful invariant; avoid broad brute-force mutation that consumes Actions minutes without improving confidence.

## Deterministic property and fuzz tests

Property tests use fixed seeds and bounded case counts so failures are reproducible. Current properties cover:

- export filename round-trip and malformed filename rejection;
- invalid required numeric values never becoming plausible defaults;
- normalization determinism;
- unknown status values failing closed;
- structured/natural-language search remaining deterministic and bounded under arbitrary strings;
- browser-local enrichment never inventing a protected `yes` state;
- malformed enrichment payload shapes being rejected instead of partially accepted.

When a fuzz/property failure exposes a new edge case, keep the minimized example as a normal regression fixture if it communicates the bug more clearly than the randomized generator.

## Artifacts and review

Pull-request validation retains:

- Python HTML/JSON coverage reports;
- JavaScript c8 summaries;
- Playwright traces/screenshots/diffs;
- visual-baseline candidates when a new baseline is intentionally introduced;
- Lighthouse and static performance budget reports.

Coverage or baseline changes are code-review changes. Do not regenerate them merely to make CI green without confirming the behavioral change is intended.
