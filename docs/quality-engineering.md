# Quality engineering contract

This project treats tests as executable safety constraints around deterministic collection logic. The contract is intentionally small enough to run on GitHub Free and is designed to ratchet upward as the codebase grows.

## Coverage gates

Python coverage is measured with branch coverage enabled. Pull requests must keep the protected build/normalization modules at or above the initial 55% aggregate line/branch threshold. Full repository coverage is still emitted as an artifact so uncovered high-risk areas remain visible instead of disappearing outside the gate.

JavaScript coverage uses c8 over the collection search, dashboard query engine, Pokémon GO search-string generator, and browser-local data/migration logic. The initial floor is deliberately conservative: 30% lines/statements and 20% branches/functions. The floor is a regression guard, not a quality target. Raising it is expected when tests are added; lowering it requires an explicit reviewed configuration change.

Generated files, vendored data, HTML templates, and trivial glue are excluded from coverage accounting. A passing percentage never overrides a failed deterministic safety test.

## Mutation testing

`scripts/run_mutation_checks.py` performs a bounded mutation pass over build logic whose failure could publish the wrong export or weaken reproducibility. The seeded mutations currently alter:

- content-hash width;
- required-column rejection;
- hidden export exclusion.

Each mutation is applied in an isolated temporary copy and the focused build test suite is executed. CI fails if any seeded mutant survives. This makes the assertions prove that they detect a real behavioral weakening rather than merely executing lines.

The mutation set should stay selective. Add a mutant when a high-risk deterministic rule gains a meaningful invariant; avoid broad brute-force mutation that consumes Actions minutes without improving confidence.

## Deterministic property and fuzz tests

Property tests use fixed seeds and bounded case counts so failures are reproducible. Current properties cover every safety target from #112:

- Poke Genie export timestamps round-trip and malformed filenames do not select as valid exports;
- randomized source-column sets report exactly which required CSV fields are missing;
- invalid required numeric values never become plausible zero/default facts;
- normalization is deterministic and unknown status values fail closed;
- duplicate reconciliation collapses equivalent rescans while conflicting exact IVs remain separate for review;
- normalized IV structures satisfy the JSON Schema contract and out-of-range values are rejected by that contract;
- structured and natural-language search remain deterministic and bounded under arbitrary strings;
- generated Pokémon GO search strings remain deterministic and structurally valid under randomized supported filters;
- browser-local enrichment never invents a protected `yes` state;
- malformed migrations are rejected and a failed multi-namespace restore leaves prior durable state unchanged;
- external-data freshness moves from fresh to stale to expired as time advances through policy windows;
- missing collection facts always retain blockers for irreversible actions such as transfer.

The PR suite is intentionally bounded. A deeper scheduled fuzz job should be added only after a concrete failure mode justifies the additional Actions cost.

When a fuzz/property failure exposes a new edge case, keep the minimized example as a normal regression fixture if it communicates the bug more clearly than the randomized generator.

## Visual regression review

`tests/browser/visual-regression.spec.js` owns a pinned Linux Chromium matrix for Collection phone/tablet/desktop layouts, mobile record detail, empty/density/offline/error states, Insights, and Tools restore preview. Baselines are stored as text-encoded PNGs under `tests/visual-baselines/*.png.b64`, keeping deterministic binary snapshots reviewable through ordinary repository changes.

When a baseline is missing, Playwright writes a candidate under `test-results/visual-baseline-candidates/` and fails once after collecting every missing state. Existing baselines are decoded at test time and compared with `maxDiffPixelRatio: 0.001`; animations and the caret are disabled to remove irrelevant rendering noise.

To update a baseline:

1. Download the `validation-reports` artifact from the pinned Linux Chromium CI run.
2. Decode and inspect the candidate PNG at full size alongside the previous baseline and any Playwright diff.
3. Confirm the changed layout or content is intentional and that there is no clipping, overlap, missing state, blank responsive region, or unexpected viewport shift.
4. Replace only the approved `.png.b64` files.
5. Rerun CI and require the baseline comparison to pass.

Do not accept a candidate solely because CI produced it. If a diff exposes a product regression, fix the product and regenerate the affected candidate from the corrected state.

## Artifacts and review

Pull-request validation retains:

- Python HTML/JSON coverage reports;
- JavaScript c8 summaries;
- Playwright traces, screenshots, and visual diffs;
- visual-baseline candidates when a baseline is missing or intentionally replaced;
- Lighthouse and static performance budget reports;
- large-collection browser timing and memory measurements attached to Playwright reports.

Coverage, performance-budget, or baseline changes are code-review changes. Do not regenerate or loosen them merely to make CI green without confirming the behavioral change is intended and documented.
