# Dashboard startup benchmark

The dashboard uses the current archived collection as its repeatable startup fixture. The benchmark contains 4,571 Pokémon records.

## Startup strategy

The production builder precomputes unique species, form, move, evolution, and gender options. Only the small gender list is embedded in HTML. Larger datalists are stored in a content-hashed JSON file and loaded when the Filters drawer is first opened. The application yields one animation frame before the initial full filter and sort pass, keeping the toolbar paint and interaction path separate from collection processing.

Playwright runs the generated site in desktop Chromium and a narrow mobile Chromium viewport. The suite records the `collection-initialize` performance measure and protects the primary workflow, lazy option loading, URL restoration, drawers, pagination, sorting, empty results, data failure, and automated accessibility.

## Controlled Lighthouse comparison

Pull request #27 added a repeatable Lighthouse 13.4.0 mobile comparison. CI builds both the pre-optimization commit and the current code from the same 4,571-record export, serves both locally on the same GitHub Actions runner, and audits both with the same Chromium build, 412 × 823 mobile emulation, and simulated throttling profile.

| Metric | Pre-optimization | Optimized | Change |
| --- | ---: | ---: | ---: |
| Performance score | 91 | 99 | +8 points |
| Total Blocking Time | 348 ms | 84 ms | -75.8% |
| Main-thread work | 940 ms | 661 ms | -29.7% |
| JavaScript execution | 323 ms | 128 ms | -60.4% |
| Long tasks | 3 | 3 | unchanged |
| First Contentful Paint | 902 ms | 904 ms | +2 ms |
| Largest Contentful Paint | 1,836 ms | 1,843 ms | +7 ms |

The optimized build did not reach the aspirational 50 ms Total Blocking Time threshold on the shared CI runner. It satisfies issue #16's alternative acceptance condition by recording a substantial controlled improvement with full before-and-after Lighthouse traces. First and Largest Contentful Paint remained effectively unchanged.

The separately supplied production Lighthouse audit from August 6, 2026 measured 100 ms Total Blocking Time before the latest startup optimization. That result and the controlled CI result are not directly interchangeable because hardware and serving conditions differ. The controlled comparison is the regression baseline because both versions run under identical conditions.

## Regression policy

`npm run test:performance` writes the following files to `performance-results/`:

- `baseline-lighthouse.json`
- `current-lighthouse.json`
- `comparison.json`
- `comparison.md`

Pull-request validation fails when the optimized build's Total Blocking Time exceeds the pre-optimization baseline. Validation artifacts retain the full reports for 14 days. Lighthouse remains the source of truth for Total Blocking Time; the Playwright initialization measurement is a broader functional ceiling intended to catch severe startup regressions on shared CI hardware.
