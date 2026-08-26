"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { expect, test } = require("@playwright/test");

test.describe.configure({ retries: 0 });
test.use({ serviceWorkers: "block" });

const BASELINE_DIR = path.resolve(__dirname, "..", "visual-baselines");
const CANDIDATE_DIR = path.resolve(process.cwd(), "test-results", "visual-baseline-candidates");

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection", { timeout: 20_000 });
  await expect.poll(() => page.locator("#pokemon-body tr").count(), { timeout: 20_000 }).toBeGreaterThan(0);
  const viewport = page.viewportSize();
  if (viewport && viewport.width <= 700) {
    await expect(page.locator(".pokemon-card").first()).toBeVisible({ timeout: 20_000 });
  }
}

async function freezeVisualNoise(page) {
  await page.addStyleTag({ content: `
    *, *::before, *::after { caret-color: transparent !important; }
    #friend-code-status, [aria-live="polite"]:empty { visibility: hidden !important; }
    #product-utility-bar { display: none !important; }
  ` });
}

async function compareSnapshot(page, testInfo, name, options = {}) {
  const encodedPath = path.join(BASELINE_DIR, `${name}.png.b64`);
  const expectedPath = testInfo.snapshotPath(`${name}.png`);
  const screenshotOptions = { animations: "disabled", caret: "hide", scale: "device", ...options };

  if (!fs.existsSync(encodedPath)) {
    fs.mkdirSync(CANDIDATE_DIR, { recursive: true });
    const actual = await page.screenshot(screenshotOptions);
    fs.writeFileSync(path.join(CANDIDATE_DIR, `${name}.png.b64`), actual.toString("base64") + "\n", "utf8");
    return false;
  }

  fs.mkdirSync(path.dirname(expectedPath), { recursive: true });
  fs.writeFileSync(expectedPath, Buffer.from(fs.readFileSync(encodedPath, "utf8").trim(), "base64"));
  await expect(page).toHaveScreenshot(`${name}.png`, {
    animations: "disabled",
    caret: "hide",
    scale: "device",
    fullPage: Boolean(options.fullPage),
    maxDiffPixelRatio: 0.001,
  });
  return true;
}

async function capture(page, testInfo, missing, name) {
  await freezeVisualNoise(page);
  if (!await compareSnapshot(page, testInfo, name, { fullPage: false })) missing.push(name);
}

function desktopChromiumOnly(testInfo) {
  test.skip(testInfo.project.name !== "desktop-chromium", "Desktop Chromium owns viewport, density, offline, error, Insights, and Tools baselines.");
}

function expectNoMissing(missing) {
  expect(missing, "Visual baseline candidates were generated under test-results/visual-baseline-candidates; review and commit their .png.b64 files.").toEqual([]);
}

async function prepareDesktopCollection(page) {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  await waitForCollection(page);
}

test("responsive collection viewport and empty states", async ({ page }, testInfo) => {
  desktopChromiumOnly(testInfo);
  test.setTimeout(90_000);
  const missing = [];

  for (const [name, viewport] of [
    ["collection-phone", { width: 393, height: 851 }],
    ["collection-tablet", { width: 820, height: 1000 }],
    ["collection-desktop", { width: 1280, height: 800 }],
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await waitForCollection(page);
    await capture(page, testInfo, missing, name);
  }

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/?q=definitely-no-such-pokemon-987654");
  await expect(page.locator("#result-count")).toContainText("0 results", { timeout: 20_000 });
  await capture(page, testInfo, missing, "collection-empty");

  expectNoMissing(missing);
});

test("collection density edge-case visual state", async ({ page }, testInfo) => {
  desktopChromiumOnly(testInfo);
  // This test owns pixel correctness only. The dedicated performance suite owns
  // startup and interaction budgets, so allow the same bounded setup window as
  // the other multi-state desktop visual test instead of conflating the gates.
  test.setTimeout(90_000);
  const missing = [];
  await prepareDesktopCollection(page);
  await page.evaluate(() => {
    const active = document.querySelector("#active-filters");
    if (active) {
      active.innerHTML = "";
      for (const label of [
        "IV %: ≥ 96", "Status: Shadow", "Lucky: No", "Great League: Ranked",
        "Current level: 40+", "Move: Extremely Long Community Day Move Name", "Needs rescan: No",
      ]) {
        const button = document.createElement("button");
        button.className = "filter-chip";
        button.type = "button";
        button.textContent = `${label} ×`;
        active.appendChild(button);
      }
    }
    const total = document.querySelector("#total-count");
    if (total) total.textContent = "99,999";
    const row = document.querySelector("#pokemon-body tr");
    if (row?.children?.length) {
      row.children[0].textContent = "Darmanitan (Galarian Zen Mode) — Extremely Long Form Name";
      if (row.children[4]) row.children[4].textContent = "Missing scan data — needs rescan";
    }
  });
  await capture(page, testInfo, missing, "collection-density-edge-cases");
  expectNoMissing(missing);
});

test("collection offline visual state", async ({ page }, testInfo) => {
  desktopChromiumOnly(testInfo);
  test.setTimeout(60_000);
  const missing = [];
  await prepareDesktopCollection(page);
  await page.locator("#offline-status").evaluate((element) => {
    element.hidden = false;
    element.textContent = "Offline: showing the last cached collection. Some freshness checks are unavailable.";
  });
  await capture(page, testInfo, missing, "collection-offline");
  expectNoMissing(missing);
});

test("collection error visual state", async ({ page }, testInfo) => {
  desktopChromiumOnly(testInfo);
  test.setTimeout(60_000);
  const missing = [];
  await prepareDesktopCollection(page);
  await page.evaluate(() => {
    const count = document.querySelector("#result-count");
    if (count) count.textContent = "Collection could not be loaded";
    const body = document.querySelector("#pokemon-body");
    if (body) body.innerHTML = '<tr><td colspan="9">Dashboard data failed to load. Download links and Data Health remain available.</td></tr>';
  });
  await capture(page, testInfo, missing, "collection-error");
  expectNoMissing(missing);
});

test("Insights and Tools visual states", async ({ page }, testInfo) => {
  desktopChromiumOnly(testInfo);
  test.setTimeout(60_000);
  const missing = [];
  await page.setViewportSize({ width: 1280, height: 900 });

  await page.goto("/insights.html");
  await expect(page.locator("#insights-status")).toHaveText("Collection insights loaded", { timeout: 20_000 });
  await capture(page, testInfo, missing, "insights-at-a-glance");

  await page.goto("/tools.html");
  await expect(page.locator("#planner-load-status")).toContainText("canonical owned records", { timeout: 20_000 });
  await page.locator("#local-data-preview").evaluate((element) => {
    element.textContent = "Restore preview: add goals; replace annotations; absent none; ignore none. No local data has changed yet.";
  });
  await capture(page, testInfo, missing, "tools-backup-preview");

  expectNoMissing(missing);
});

test("mobile record detail visual state", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "The configured mobile Chromium profile owns the interactive phone-detail baseline.");
  const missing = [];
  await page.goto("/");
  await waitForCollection(page);
  const card = page.locator(".pokemon-card").first();
  await card.getByRole("button", { name: "Details" }).click();
  await expect(page.locator("#pokemon-detail-dialog")).toBeVisible({ timeout: 20_000 });
  await capture(page, testInfo, missing, "record-detail-phone");
  expect(missing, "The mobile record-detail baseline candidate was generated; review and commit it with the viewport matrix.").toEqual([]);
});
