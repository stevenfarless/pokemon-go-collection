"use strict";

const { expect, test } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection");
  await expect(page.locator("#pokemon-body tr").first()).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await waitForCollection(page);
});

test("filter badge is hidden at zero and counts active advanced filters", async ({ page }) => {
  const drawer = page.locator("#advanced-filters");
  const badge = page.locator("#advanced-count");
  await expect(badge).toBeHidden();
  await drawer.locator(":scope > summary").click();
  await page.locator("#hundo-filter").selectOption("yes");
  await expect(badge).toBeVisible();
  await expect(badge).toHaveText("1");
});

test("filter options load lazily on the first drawer opening", async ({ page }) => {
  await expect(page.locator("#species-options option")).toHaveCount(0);
  await page.locator("#advanced-filters > summary").click();
  await expect(page.locator("#advanced-filters")).toHaveAttribute("data-options-loaded", "true");
  expect(await page.locator("#species-options option").count()).toBeGreaterThan(100);
});

test("drawers trap focus, close with Escape, and return focus", async ({ page }) => {
  for (const id of ["advanced-filters", "sort-details"]) {
    const drawer = page.locator(`#${id}`);
    const summary = drawer.locator(":scope > summary");
    await summary.focus();
    await summary.press("Enter");
    await expect(drawer).toHaveAttribute("open", "");
    await expect(drawer.locator(".drawer-panel")).toHaveAttribute("aria-modal", "true");
    await expect(drawer.locator(".drawer-panel")).toContainText(id === "advanced-filters" ? "Filters" : "Sort");
    await page.keyboard.press("Escape");
    await expect(drawer).not.toHaveAttribute("open", "");
    await expect(summary).toBeFocused();
  }
});

test("presets, chips, reset, pagination, sorting, and shared URLs work", async ({ page }) => {
  await page.locator("#preset-select").selectOption("high-iv");
  await page.locator("#apply-preset").click();
  await expect(page.locator("#active-filters")).toContainText("IV %");
  await page.locator("#reset-filters").click();
  await expect(page.locator("#active-filters")).toContainText("No filters applied");

  await page.locator("#next-page").click();
  await expect(page).toHaveURL(/page=2/);
  await page.locator('[data-sort-key="cp"]').click();
  await expect(page).toHaveURL(/sort=cp%3Aasc|sort=cp:asc/);

  await page.goto("/?q=definitely-no-such-pokemon-987654");
  await expect(page.locator("#result-count")).toContainText("0 results");
  await expect(page.locator("#pokemon-body")).toBeEmpty();

  await page.goto("/?size=999&page=-3&sort=not-a-field:sideways&unknown=1");
  await waitForCollection(page);
  await expect(page.locator("#page-size")).toHaveValue("50");
  expect(new URL(page.url()).searchParams.has("unknown")).toBeFalsy();
});

test("data loading failure leaves a usable error state", async ({ page }) => {
  await page.route("**/data/pokemon.json*", (route) => route.abort());
  await page.reload();
  await expect(page.locator("#result-count")).toContainText("could not be loaded");
  await expect(page.locator("#pokemon-body")).toContainText("dashboard data failed to load");
  await expect(page.getByRole("link", { name: "CSV" })).toBeVisible();
});

test("primary search workflow has no critical accessibility violations", async ({ page }) => {
  const results = await new AxeBuilder({ page })
    .include("body")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const critical = results.violations.filter((violation) => violation.impact === "critical");
  expect(critical).toEqual([]);
});

test("startup benchmark stays within the documented long-task budget", async ({ page }) => {
  const measurement = await page.evaluate(() => {
    const init = performance.getEntriesByName("collection-initialize").at(-1);
    return { duration: init?.duration ?? null };
  });
  expect(measurement.duration).not.toBeNull();
  expect(measurement.duration).toBeLessThan(1500);
  console.log(`collection-initialize=${measurement.duration.toFixed(1)}ms`);
});
