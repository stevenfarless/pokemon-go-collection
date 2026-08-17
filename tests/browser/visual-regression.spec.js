"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { expect, test } = require("@playwright/test");

const BASELINE_DIR = path.resolve(__dirname, "..", "visual-baselines");
const CANDIDATE_DIR = path.resolve(process.cwd(), "test-results", "visual-baseline-candidates");

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection", { timeout: 20_000 });
  await expect.poll(() => page.locator("#pokemon-body tr").count(), { timeout: 20_000 }).toBeGreaterThan(0);
}

async function freezeVisualNoise(page) {
  await page.addStyleTag({ content: `
    *, *::before, *::after { caret-color: transparent !important; }
    #friend-code-status, [aria-live="polite"]:empty { visibility: hidden !important; }
  ` });
}

async function compareSnapshot(page, testInfo, name, options = {}) {
  const encodedPath = path.join(BASELINE_DIR, `${name}.png.b64`);
  const expectedPath = testInfo.snapshotPath(`${name}.png`);
  const screenshotOptions = { animations: "disabled", caret: "hide", ...options };

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
    fullPage: Boolean(options.fullPage),
    maxDiffPixelRatio: 0.001,
  });
  return true;
}

test("responsive visual state matrix", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "Visual baselines use one pinned Linux Chromium environment.");
  const missing = [];

  for (const [name, viewport] of [
    ["collection-phone", { width: 393, height: 851 }],
    ["collection-tablet", { width: 820, height: 1000 }],
    ["collection-desktop", { width: 1280, height: 800 }],
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await waitForCollection(page);
    await freezeVisualNoise(page);
    if (!await compareSnapshot(page, testInfo, name, { fullPage: false })) missing.push(name);
  }

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/?q=definitely-no-such-pokemon-987654");
  await expect(page.locator("#result-count")).toContainText("0 results", { timeout: 20_000 });
  await freezeVisualNoise(page);
  if (!await compareSnapshot(page, testInfo, "collection-empty", { fullPage: false })) missing.push("collection-empty");

  await page.goto("/insights.html");
  await expect(page.locator("#insights-status")).toHaveText("Collection insights loaded", { timeout: 20_000 });
  await freezeVisualNoise(page);
  if (!await compareSnapshot(page, testInfo, "insights-desktop", { fullPage: false })) missing.push("insights-desktop");

  await page.goto("/tools.html");
  await expect(page.locator("#planner-load-status")).toContainText("canonical owned records", { timeout: 20_000 });
  await page.locator("#local-data-preview").evaluate((element) => {
    element.textContent = "Restore preview: add goals; replace annotations; absent none; ignore none. No local data has changed yet.";
  });
  await freezeVisualNoise(page);
  if (!await compareSnapshot(page, testInfo, "tools-backup-preview", { fullPage: false })) missing.push("tools-backup-preview");

  expect(missing, "Visual baseline candidates were generated under test-results/visual-baseline-candidates; review and commit their .png.b64 files.").toEqual([]);
});
