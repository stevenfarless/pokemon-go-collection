"use strict";

const { expect, test } = require("@playwright/test");

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection", { timeout: 20_000 });
  await expect.poll(() => page.locator("#pokemon-body tr").count(), { timeout: 20_000 }).toBeGreaterThan(0);
}

async function openMobileMoreIfNeeded(page) {
  const more = page.locator("#mobile-more");
  if (await more.isVisible() && !(await more.evaluate((element) => element.open))) {
    await more.locator(":scope > summary").click();
  }
}

function isConnectivityProbeResponse(response) {
  try {
    const url = new URL(response.url());
    return url.pathname.endsWith("/data/build-manifest.json") && url.searchParams.has("connectivity");
  } catch {
    return false;
  }
}

async function loadCollection(page) {
  const connectivityProbe = page.waitForResponse(isConnectivityProbeResponse, { timeout: 20_000 });
  await page.goto("/");
  await waitForCollection(page);
  const response = await connectivityProbe;
  expect(response.ok()).toBeTruthy();
  await expect(page.locator("#offline-status")).toBeHidden();
}

test("@compat collection search, pagination, and exact-record access work", async ({ page }, testInfo) => {
  await loadCollection(page);
  await page.locator("#search").fill("name:pikachu");
  await expect(page.locator("#result-count")).not.toContainText("0 results");

  if (testInfo.project.name.includes("mobile")) {
    const card = page.locator(".pokemon-card").first();
    await expect(card).toBeVisible();
    await card.getByRole("button", { name: "Details" }).click();
    await expect(page.locator("#pokemon-detail-dialog")).toBeVisible();
    await expect(page.locator("#pokemon-detail-dialog .record-fields")).toContainText("pokemon_number");
    await page.keyboard.press("Escape");
  } else {
    const row = page.locator("#pokemon-body tr").first();
    await expect(row).toBeVisible();
    await expect(row).toContainText(/Pikachu/i);
    await expect(row.getByRole("button", { name: "Compare" })).toBeVisible();
  }

  await page.locator("#search").fill("");
  await waitForCollection(page);
  await page.locator("#next-page").click();
  await expect(page).toHaveURL(/page=2/);
});

test("@compat Tools and browser-local planning controls initialize", async ({ page }) => {
  await page.goto("/tools.html");
  await expect(page.locator("#planner-load-status")).toContainText("canonical owned records", { timeout: 20_000 });
  await expect(page.locator("#goal-exclusions")).toBeAttached({ timeout: 20_000 });
  await expect(page.locator("#team-locks option").first()).toBeAttached({ timeout: 20_000 });
  await expect(page.locator("#local-data-backup")).toBeAttached();
  await expect(page.locator("#enrichment")).toBeAttached();
});

test("@compat clipboard denial falls back to selected text for manual copy", async ({ page }) => {
  await loadCollection(page);
  await page.locator("#advanced-filters > summary").click();
  await page.locator("#status-filter").selectOption("shadow");
  await page.keyboard.press("Escape");
  await expect(page.locator("#advanced-filters")).not.toHaveAttribute("open", "");
  await openMobileMoreIfNeeded(page);
  await page.locator("#go-search-builder").click();

  const dialog = page.locator("#go-search-dialog");
  await expect(dialog).toBeVisible();
  const output = dialog.locator("#go-search-output");
  await expect(output).not.toHaveValue("");

  await page.evaluate(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText() {
          return Promise.reject(new Error("clipboard unavailable in compatibility test"));
        },
      },
    });
  });

  await dialog.locator("#copy-go-search").click();
  await expect(dialog.locator("#go-search-copy-status")).toHaveText(
    "Clipboard permission was unavailable. The text is selected for manual copy.",
  );

  const selection = await output.evaluate((element) => ({
    start: element.selectionStart,
    end: element.selectionEnd,
    length: element.value.length,
  }));
  expect(selection.start).toBe(0);
  expect(selection.end).toBe(selection.length);
});

test("@compat PWA manifest, service worker, and coherent cache install", async ({ page }) => {
  await loadCollection(page);
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute("href", "manifest.webmanifest");
  const pwa = await page.evaluate(async () => {
    if (!("serviceWorker" in navigator) || !("caches" in globalThis)) {
      return { supported: false, controlled: false, cacheCount: 0 };
    }
    const registration = await navigator.serviceWorker.ready;
    const names = await caches.keys();
    return {
      supported: true,
      controlled: Boolean(navigator.serviceWorker.controller || registration.active),
      cacheCount: names.filter((name) => name.startsWith("pokemon-go-collection-")).length,
    };
  });
  expect(pwa.supported).toBeTruthy();
  expect(pwa.controlled).toBeTruthy();
  expect(pwa.cacheCount).toBeGreaterThan(0);
});