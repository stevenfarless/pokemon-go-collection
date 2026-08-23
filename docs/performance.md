# Performance contract and dashboard benchmark

The dashboard uses the current archived collection as its repeatable real-world fixture. Performance is protected at three deterministic scales: the current collection, a 2× synthetic collection, and a 10,000-record stress collection. A fourth gate runs the 10,000-record fixture through the repository's mobile Chromium profile.

## Startup and loading strategy

The production builder precomputes unique species, form, move, evolution, and gender options. Only the small gender list is embedded in HTML. Larger datalists are stored in a content-hashed JSON file and loaded when the Filters drawer is first opened. The application yields one animation frame before the initial full filter and sort pass, keeping the toolbar paint and interaction path separate from collection processing.

The Collection startup check records requested JSON resources before any advanced surface is opened. Secondary JSON larger than 250 KB is treated as an eager-loading regression unless it is the canonical collection, build manifest, or collection summary. Static generated-resource budgets separately protect initial JavaScript/CSS, total JavaScript/CSS, `pokemon.json`, and the largest generated file.

## Browser workflow budgets

Playwright measures the same user workflow at current, 2×, and 10k sizes: startup, ordinary search, advanced filter plus sort, record-detail open, Tools initialization, local-data migration, JS heap, Event Timing duration, long-task count, and longest long task. The local migration fixture contains up to 5,000 user-confirmed annotation/enrichment records and runs against the full current synthetic collection.

`config/performance-budgets.json` is the reviewable source of truth. Key initial ceilings are:

| Fixture | Startup | Search | Filter + sort | Detail | Tools | Local migration | Heap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Current | 5,000 ms | 1,200 ms | 1,800 ms | 1,200 ms | 7,000 ms | 1,000 ms | 160 MB |
| 2× current | 8,000 ms | 1,800 ms | 2,600 ms | 1,600 ms | 10,000 ms | 1,800 ms | 240 MB |
| 10,000 | 15,000 ms | 3,000 ms | 4,500 ms | 2,500 ms | 15,000 ms | 3,500 ms | 400 MB |
| Mobile 10,000 | 20,000 ms | 4,000 ms | 5,500 ms | 3,000 ms | 18,000 ms | 4,000 ms | 450 MB |

The same configuration limits the longest observed Event Timing interaction to 300/500/800/1,000 ms across those four fixtures, and limits longest long task to 1.0/1.5/2.5/3.0 seconds. These are shared-runner regression ceilings. They are expected to tighten after repeated CI measurements establish lower stable baselines.

## Core Web Vitals and interaction interpretation

The Lighthouse mobile gate requires a performance score of at least 90, LCP at or below 2.5 seconds, CLS at or below 0.1, and TBT at or below 350 ms. Lighthouse's TBT remains a controlled lab main-thread signal.

Playwright also observes browser Event Timing entries while executing search, filter, sort, and detail interactions. This supplies a deterministic interaction-regression signal near the mechanism used by INP. It is a lab proxy and is not labeled as a field INP measurement because INP is defined from real-user interaction distributions over a page visit. The project therefore protects both a repeatable interaction mechanism in CI and the Core Web Vitals paint/layout targets available from the mobile Lighthouse profile.

## Budget-change policy

A material regression fails CI. Raising a ceiling, increasing an initial-resource allowance, or removing a protected interaction requires an explicit reviewed configuration change with a reason. Feature work should first reduce eager loading, repeated indexing, DOM work, local-state migration cost, or main-thread work before a budget is raised.

No advanced knowledge, planning, or recommendation dataset should move into Collection's initial critical path merely because a new feature consumes it. If a feature needs a large resource, prefer precomputation, bounded indexes, lazy loading, or a worker when measurements show main-thread work is material.

## Controlled Lighthouse comparison

Pull request #27 added a repeatable mobile Lighthouse comparison. CI builds both the pre-optimization commit and current code from the same export, serves both locally on the same runner, and audits both with the same Chromium build and mobile emulation profile.

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

The controlled comparison provides before/after evidence for pull requests. Absolute budgets provide a second guard so a gradually worsening baseline cannot legitimize an already slow current build.

## CI artifacts

`npm run test:performance` writes full Lighthouse reports and the controlled comparison to `performance-results/`. `node scripts/check_lighthouse_budgets.mjs` adds `lighthouse-budget.json` and `lighthouse-budget.md`. `python scripts/check_performance_budgets.py` adds static generated-resource budget reports. Playwright attaches JSON measurements for the current/2×/10k matrix and the mobile 10k stress run to its HTML report; traces and screenshots remain available when a browser budget fails.

The scaling matrix is pinned to Linux Chromium to reduce noise. The additional mobile Chromium stress run exercises the compact touch layout. Firefox, desktop WebKit, and mobile Safari remain covered by the separate compatibility suite, while Safari/VoiceOver performance and accessibility remain part of manual release verification.
