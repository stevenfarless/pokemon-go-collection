"use strict";

const AxeBuilder = require("@axe-core/playwright").default;
const { expect, test } = require("@playwright/test");

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection", { timeout: 20_000 });
  await expect.poll(() => page.locator("#pokemon-body tr").count(), { timeout: 20_000 }).toBeGreaterThan(0);
}

async function assertNoSeriousAxeViolations(page, options = {}) {
  let builder = new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]);
  if (options.representativeCollection) {
    builder = builder
      .exclude("#pokemon-body tr:nth-child(n+2)")
      .exclude("#pokemon-cards .pokemon-card:nth-child(n+2)");
  }
  if (options.include) builder = builder.include(options.include);
  const results = await builder.analyze();
  const violations = results.violations.filter((item) => ["serious", "critical"].includes(item.impact));
  expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
}

async function assertNoPageOverflow(page) {
  const overflow = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    body: document.body.scrollWidth - document.body.clientWidth,
  }));
  expect(overflow.document).toBeLessThanOrEqual(1);
  expect(overflow.body).toBeLessThanOrEqual(1);
}

test("WCAG 2.2 primary pages have no serious or critical automated violations", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "One pinned engine owns the full axe contract; compatibility is tested separately.");
  test.setTimeout(90_000);
  await page.goto("/");
  await waitForCollection(page);
  await assertNoSeriousAxeViolations(page, { representativeCollection: true });

  await page.goto("/insights.html");
  await expect(page.locator("#insights-status")).toHaveText("Collection insights loaded", { timeout: 20_000 });
  await assertNoSeriousAxeViolations(page);

  await page.goto("/tools.html");
  await expect(page.locator("#planner-load-status")).toContainText("canonical owned records", { timeout: 20_000 });
  await assertNoSeriousAxeViolations(page);
});

test("drawers and comparison dialog retain the WCAG 2.2 automated baseline", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium");
  test.setTimeout(60_000);
  await page.goto("/");
  await waitForCollection(page);

  await page.locator("#advanced-filters > summary").click();
  await assertNoSeriousAxeViolations(page, { representativeCollection: true });
  await page.keyboard.press("Escape");
  await expect(page.locator("#advanced-filters > summary")).toBeFocused();

  const firstCompare = page.locator("#pokemon-body tr").first().getByRole("button", { name: "Compare" });
  await firstCompare.click();
  await page.locator("#next-page").click();
  await page.locator("#pokemon-body tr").first().getByRole("button", { name: "Compare" }).click();
  await page.locator("[data-open-comparison]").click();
  await expect(page.locator("#pokemon-compare-dialog")).toBeVisible();
  await assertNoSeriousAxeViolations(page, { include: "#pokemon-compare-dialog" });
});

test("mobile record detail dialog retains the WCAG 2.2 automated baseline", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "Mobile Chromium provides the automated touch-layout dialog check; Safari remains in manual and compatibility coverage.");
  await page.goto("/");
  await waitForCollection(page);
  const card = page.locator(".pokemon-card").first();
  await card.getByRole("button", { name: "Details" }).click();
  await expect(page.locator("#pokemon-detail-dialog")).toBeVisible();
  await assertNoSeriousAxeViolations(page, { include: "#pokemon-detail-dialog" });
});

test("320 CSS pixel reflow keeps the primary workflow inside the viewport", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "A single pinned Chromium profile owns the reflow contract.");
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto("/");
  await waitForCollection(page);
  await assertNoPageOverflow(page);
  await expect(page.locator("#search")).toBeVisible();
  await expect(page.locator("#advanced-filters > summary")).toBeVisible();
  await expect(page.locator(".pokemon-card").first()).toBeVisible();
});

test("WCAG text spacing does not clip the primary mobile workflow", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium");
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto("/");
  await waitForCollection(page);
  await page.addStyleTag({ content: `
    * { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; }
    p { margin-bottom: 2em !important; }
  ` });
  await assertNoPageOverflow(page);
  await expect(page.locator("#search")).toBeVisible();
  await expect(page.locator(".pokemon-card").first()).toBeVisible();
});

test("portrait and landscape layouts preserve primary controls", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium");
  for (const viewport of [{ width: 390, height: 844 }, { width: 844, height: 390 }]) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await waitForCollection(page);
    await expect(page.locator("#search")).toBeVisible();
    await expect(page.locator("#advanced-filters > summary")).toBeVisible();
    await assertNoPageOverflow(page);
  }
});

test("keyboard focus is visible and not obscured on high-frequency controls", async ({ page }) => {
  await page.goto("/");
  await waitForCollection(page);
  const targets = ["#search", "#apply-preset", "#advanced-filters > summary", ".data-menu > summary"];
  for (const selector of targets) {
    const locator = page.locator(selector);
    await locator.focus();
    const state = await locator.evaluate((element) => {
      element.scrollIntoView({ block: "center", inline: "nearest" });
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right,
        viewportWidth: innerWidth, viewportHeight: innerHeight,
        outlineWidth: parseFloat(style.outlineWidth) || 0, boxShadow: style.boxShadow,
      };
    });
    expect(state.top).toBeGreaterThanOrEqual(-1);
    expect(state.left).toBeGreaterThanOrEqual(-1);
    expect(state.bottom).toBeLessThanOrEqual(state.viewportHeight + 1);
    expect(state.right).toBeLessThanOrEqual(state.viewportWidth + 1);
    expect(state.outlineWidth > 0 || state.boxShadow !== "none").toBeTruthy();
  }
});

test("high-frequency controls meet WCAG 2.2 minimum target size", async ({ page }) => {
  await page.goto("/");
  await waitForCollection(page);
  const selectors = [
    "#copy-friend-code", "#apply-preset", "#advanced-filters > summary",
    ".data-menu > summary", ".summary-preset", "#next-page", "#previous-page",
  ];
  const undersized = await page.evaluate((wanted) => {
    const failures = [];
    for (const selector of wanted) for (const element of document.querySelectorAll(selector)) {
      if (!element.getClientRects().length) continue;
      const rect = element.getBoundingClientRect();
      if (rect.width < 24 || rect.height < 24) failures.push({ selector, width: rect.width, height: rect.height });
    }
    return failures;
  }, selectors);
  expect(undersized).toEqual([]);
});

test("frequent touch controls prefer 44 CSS pixel targets on coarse pointers", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.includes("mobile"));
  await page.goto("/");
  await waitForCollection(page);
  const selectors = ["#copy-friend-code", "#apply-preset", "#advanced-filters > summary", ".data-menu > summary", ".summary-preset", "#next-page"];
  const undersized = await page.evaluate((wanted) => wanted.flatMap((selector) => [...document.querySelectorAll(selector)]
    .filter((element) => element.getClientRects().length)
    .map((element) => ({ selector, ...element.getBoundingClientRect().toJSON() }))
    .filter((rect) => rect.height < 44)), selectors);
  expect(undersized).toEqual([]);
});

test("reduced motion disables nonessential animation and transition", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await waitForCollection(page);
  const animated = await page.evaluate(() => [...document.querySelectorAll("button, summary, .drawer-panel, .filter-chip")]
    .filter((element) => element.getClientRects().length)
    .map((element) => {
      const style = getComputedStyle(element);
      return { animation: style.animationDuration, transition: style.transitionDuration };
    })
    .filter((item) => item.animation !== "0s" || item.transition !== "0s"));
  expect(animated).toEqual([]);
});

test("forced colors keeps controls and focus distinguishable", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "forced-colors emulation is pinned to Chromium.");
  await page.emulateMedia({ forcedColors: "active" });
  await page.goto("/");
  await waitForCollection(page);
  const control = page.locator("#apply-preset");
  await control.focus();
  const style = await control.evaluate((element) => {
    const computed = getComputedStyle(element);
    return { border: computed.borderStyle, borderWidth: parseFloat(computed.borderWidth) || 0, outlineWidth: parseFloat(computed.outlineWidth) || 0 };
  });
  expect(style.border !== "none" || style.borderWidth > 0).toBeTruthy();
  expect(style.outlineWidth).toBeGreaterThan(0);
});
