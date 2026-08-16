# Browser support contract

The collection companion is a static progressive web app. Browser support is defined by the workflows that must remain usable, not by a promise that every browser exposes every optional web-platform capability.

## Supported engines

Pull-request validation runs the critical browser suite against the Playwright-pinned versions of:

- Chromium on desktop;
- Firefox on desktop;
- WebKit on desktop as the automated Safari-engine approximation;
- Chromium on a representative mobile viewport;
- WebKit using Playwright's iPhone 13 / Mobile Safari profile.

The repository pins `@playwright/test`, so the exact automated browser revisions are reproducible from `package-lock.json`.

Real Safari and installed iOS PWA behavior cannot be proven completely by Linux CI. WebKit CI is therefore a release gate for the browser engine, while the manual iOS checklist below covers lifecycle behaviors that require a real Apple device.

## Critical supported workflows

The following are part of the browser compatibility contract and must not depend on a Chromium-only API:

- load the current collection and connectivity state;
- search, filter, paginate, sort, and inspect exact records;
- open mobile record details;
- compare records across pagination;
- save, rename, duplicate, export, import, and delete saved views;
- generate and inspect Pokémon GO search strings;
- load the PWA manifest and service worker;
- retain a previously loaded collection for supported offline use;
- load Collection, Insights, Tools, and their canonical resources without fatal JavaScript errors.

A failure in one of these workflows on a supported engine is a release-blocking browser compatibility defect unless the support contract is deliberately changed in review.

## Capability-aware progressive enhancement

Optional browser APIs must be feature-detected. Their absence must not make the core collection/reference/planning experience unusable.

Examples include:

- clipboard APIs;
- Web Share;
- installation prompts;
- storage persistence requests and storage-estimate APIs;
- other PWA-specific convenience APIs.

When an optional capability is unavailable, the product should use the simplest safe fallback available for that feature, such as ordinary browser navigation, explicit download/export, selectable text/manual copy, or an explanatory disabled control. A missing optional capability must not be represented as a data error.

This document does not claim that every future optional API fallback already exists. New features that rely on unevenly supported APIs must add the corresponding detection, fallback, and tests before they become part of the supported product.

## Graceful degradation policy

The following hierarchy applies:

1. Preserve correctness and safety.
2. Preserve access to the same canonical data and decision evidence.
3. Preserve the primary workflow with an alternate interaction when practical.
4. Disable only the unsupported convenience capability and explain why.
5. Never silently change a recommendation, freshness state, or destructive-safety rule because the browser lacks an API.

Browser-specific visual differences that do not reduce readability, accessibility, interaction, or semantic meaning are not compatibility defects.

## Automated validation

`playwright.config.js` defines the supported browser projects. `npm run test:browser` executes the same critical regression/accessibility suite across those projects. CI installs Chromium, Firefox, and WebKit explicitly.

Lighthouse and Chromium-specific production smoke may remain Chromium-only where the underlying tooling is Chromium-specific. They do not replace the cross-engine regression suite.

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

Record the tested iOS/Safari version and any known limitation in the release-readiness evidence rather than generalizing one device test to all Safari versions.

## Updating this contract

Browser support changes require an explicit pull request that updates this document, the Playwright project matrix, and affected tests together. Removing an engine merely because it exposes a defect is not an acceptable fix.
