# Performance contract and dashboard benchmark

The dashboard uses the current archived collection as its repeatable real-world startup fixture. Performance is protected at three scales: the current collection, a deterministic 2× synthetic collection, and a 10,000-record stress collection.

## Startup strategy

The production builder precomputes unique species, form, move, evolution, and gender options. Only the small gender list is embedded in HTML. Larger datalists are stored in a content-hashed JSON file and loaded when the Filters drawer is first opened. The application yields one animation frame before the initial full filter and sort pass, keeping the toolbar paint and interaction path separate from collection processing.

Playwright records wall-clock startup, search interaction latency, and Chromium JS heap use for the current, 2×, and 10k fixtures. These are lab regression budgets on a pinned GitHub Actions browser profile. They are intentionally looser than a local developer-machine benchmark because shared runners vary.

## Protected budgets

`config/performance-budgets.json` is the reviewable source of truth. Initial browser ceilings are:

| Fixture | Startup | Search interaction | JS heap |
| --- | ---: | ---: | ---: |
| Current collection | 5,000 ms | 1,200 ms | 160 MB |
| 2× current | 8,000 ms | 1,800 ms | 240 MB |
| 10,000 records | 15,000 ms | 3,000 ms | 400 MB |

The current Lighthouse mobile budgets are a performance score of at least 90, LCP at or below 2.5 seconds, CLS at or below 0.1, and TBT at or below 350 ms. Lighthouse's TBT is retained as a controlled lab responsiveness signal. Search interaction timing in Playwright gives this application a direct user-action regression gate; lab tests do not claim to be field INP measurements.

Static generated-resource ceilings protect the initial Collection JavaScript/CSS path, total generated JavaScript/CSS, `pokemon.json`, and any single generated file. Heavy knowledge and planning resources may remain outside the initial critical path and are measured separately from the initial Collection assets.

A budget change requires review and a reason. Feature work should first reduce eager loading, indexing, or work performed on the main thread before raising a ceiling.

## Controlled Lighthouse comparison

Pull request #27 added a repeatable Lighthouse 13.4.0 mobile comparison. CI builds both the pre-optimization commit and current code from the same export, serves both locally on the same runner, and audits both with the same Chromium build, 412 × 823 mobile emulation, and simulated throttling profile.

The historical controlled result was:

| Metric | Pre-optimization | Optimized | Change |
| --- | ---: | ---: | ---: |
| Performance score | 91 | 99 | +8 points |
| Total Blocking Time | 348 ms | 84 ms | -75.8% |
| Main-thread work | 940 ms | 661 ms | -29.7% |
| JavaScript execution | 323 ms | 128 ms | -60.4% |
| Long tasks | 3 | 3 | unchanged |
| First Contentful Paint | 902 ms | 904 ms | +2 ms |
| Largest Contentful Paint | 1,836 ms | 1,843 ms | +7 ms |

The controlled comparison remains useful for detecting relative regressions. Absolute budgets now add a second guard so a gradually worsening baseline cannot legitimize an already poor current build.

## CI artifacts

`npm run test:performance` writes full Lighthouse reports and the controlled comparison to `performance-results/`. `node scripts/check_lighthouse_budgets.mjs` adds `lighthouse-budget.json` and `lighthouse-budget.md`. `python scripts/check_performance_budgets.py` adds static generated-resource budget reports. Playwright attaches the current/2×/10k measurements to its HTML report.

Visual and browser performance tests remain limited to one pinned Linux Chromium project to avoid platform noise and unnecessary Actions cost. Firefox, WebKit, and mobile Safari compatibility remain covered by the separate compatibility contract.
