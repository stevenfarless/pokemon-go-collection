# Browser support contract

The collection companion is a static progressive web app. Browser support is defined by workflows that must remain usable, not by a promise that every browser exposes every optional web-platform capability.

## Supported engines

Pull-request validation covers the Playwright-pinned versions of:

- Chromium on desktop;
- Chromium on a representative mobile viewport;
- Firefox on desktop;
- WebKit on desktop as the automated Safari-engine approximation;
- WebKit using Playwright's iPhone 13 / Mobile Safari profile.

The repository pins `@playwright/test`, so the exact automated browser revisions are reproducible from `package-lock.json`.

Real Safari and installed iOS PWA behavior cannot be proven completely by Linux CI. WebKit CI is therefore a release gate for browser-engine compatibility, while the manual iOS checklist below covers lifecycle behaviors that require a real Apple device.

## Critical supported workflows

The cross-engine compatibility contract covers:

- loading the current collection and healthy connectivity state;
- exact collection search and pagination;
- accessing an exact owned record, including mobile detail UI;
- loading the Tools workspace and its browser-local planning controls;
- clipboard-denial graceful fallback for generated Pokémon GO search text;
- loading the PWA manifest, registering the service worker, and installing a coherent application cache.

The exhaustive Chromium suites additionally cover deeper filtering/sorting, comparison, saved-view import/export, offline reload, accessibility, error-state, optimizer, trade, goals, and other regression behavior.

A failure in a critical compatibility workflow on a supported engine is release-blocking unless the support contract is deliberately changed in review.

## Why the cross-engine suite is focused

The first full five-engine run was intentionally used as a discovery pass. It demonstrated that blindly replaying every Chromium-oriented test on every engine creates duplicate runtime and false portability failures from test-harness assumptions such as Chromium clipboard permissions. It also exposed a Playwright WebKit internal error when forcing an offline `page.reload()` on Linux, which is not a reliable basis for claiming real iOS standalone-PWA lifecycle behavior.

Accordingly:

- desktop and mobile Chromium continue to run the exhaustive browser suite;
- Firefox, desktop WebKit, and Mobile Safari/WebKit run a focused `@compat` contract containing the browser-independent critical workflows above;
- real-device Safari/iOS offline/update lifecycle remains a required manual release check;
- a feature that relies on a new unevenly supported API must extend the `@compat` contract rather than assuming Chromium behavior.

This is a scope distinction, not an exception that lets known product defects pass.

## Capability-aware progressive enhancement

Optional browser APIs must be feature-detected. Their absence must not make the core collection/reference/planning experience unusable.

Examples include:

- clipboard APIs;
- Web Share;
- installation prompts;
- storage persistence requests and storage-estimate APIs;
- other PWA-specific convenience APIs.

When an optional capability is unavailable, the product should use the simplest safe fallback available for that feature, such as ordinary browser navigation, explicit download/export, selectable text/manual copy, or an explanatory disabled control. A missing optional capability must not be represented as a data error.

This document does not claim that every future optional API fallback already exists. New features that rely on unevenly supported APIs must add corresponding detection, fallback, and tests before they become part of the supported product.

## Graceful degradation policy

The following hierarchy applies:

1. Preserve correctness and safety.
2. Preserve access to the same canonical data and decision evidence.
3. Preserve the primary workflow with an alternate interaction when practical.
4. Disable only the unsupported convenience capability and explain why.
5. Never silently change a recommendation, freshness state, or destructive-safety rule because the browser lacks an API.

Browser-specific visual differences that do not reduce readability, accessibility, interaction, or semantic meaning are not compatibility defects.

## Automated validation

`playwright.config.js` defines the supported browser projects. `npm run test:browser` runs the full suite on desktop/mobile Chromium and the focused `@compat` suite on Firefox/WebKit/Mobile Safari. CI installs Chromium, Firefox, and WebKit explicitly.

Lighthouse and Chromium-specific production smoke remain Chromium-only where the underlying tooling is Chromium-specific. Chromium's existing automated offline-reload test remains part of the exhaustive regression suite. Those checks do not replace the cross-engine compatibility contract or the real-device iOS checklist.

## Manual real-device checklist

Run this checklist on a current supported iPhone/Safari combination before a gold-standard release and after material PWA/service-worker changes:

1. Open the public site in Safari and load Collection, Insights, and Tools.
2. Search for a known Pokémon, clear the search, paginate, and open record details.
3. Add the site to the Home Screen and launch it in standalone mode.
4. Confirm safe-area/layout behavior in portrait and landscape where the device permits it.
5. Confirm saved views/local settings persist across ordinary close/reopen cycles.
6. Load the collection online, disable connectivity, reopen/reload the installed app, and verify the explicit offline state plus cached collection behavior.
7. Restore connectivity and confirm the application returns to online/current-state behavior without clearing local data.
8. After deploying a newer build, reopen the installed app and confirm it does not remain indefinitely stuck on mixed old/new resources.
9. Exercise any clipboard/share/install/storage feature that is currently exposed on iOS and confirm its documented fallback when unavailable.
10. Confirm VoiceOver can reach the primary navigation, search, record detail, dialogs, status messages, and close controls.

Record the tested iOS/Safari version and any known limitation in release-readiness evidence rather than generalizing one device test to all Safari versions.

## Updating this contract

Browser support changes require an explicit pull request that updates this document, the Playwright project matrix, and affected tests together. Removing an engine merely because it exposes a product defect is not an acceptable fix.
