# Dashboard startup benchmark

The dashboard uses the current archived collection as its repeatable startup fixture. The current baseline contains 4,571 Pokémon records.

The production builder precomputes unique species, form, move, evolution, and gender options. Only the small gender list is embedded in HTML. Larger datalists are stored in a content-hashed JSON file and loaded the first time the Filters drawer opens. The application yields one animation frame before the initial full filter and sort pass, keeping the toolbar paint and interaction path separate from collection processing.

Playwright runs the generated site in desktop Chromium and a narrow mobile Chromium viewport. The suite records the `collection-initialize` performance measure and protects the primary workflow, lazy option loading, URL restoration, drawers, pagination, sorting, empty results, data failure, and automated accessibility. Lighthouse remains the source of truth for production Total Blocking Time because GitHub Actions hardware is not equivalent to the Lighthouse mobile profile.

Before this change, the August 6, 2026 mobile Lighthouse audit measured 100 ms Total Blocking Time and a 223 ms application task. The target for the next equivalent Lighthouse run is 50 ms or lower Total Blocking Time. CI uses a broader 1.5-second initialization ceiling to catch severe regressions without treating shared-runner variance as a production metric.
