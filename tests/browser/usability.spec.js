"use strict";

const { expect, test } = require("@playwright/test");

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection");
  await expect(page.locator("#pokemon-body tr").first()).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await waitForCollection(page);
});

test("shared URLs and presets restore state without opening a drawer", async ({ page }) => {
  const filters = page.locator("#advanced-filters");
  await page.goto("/?ivmin=96&sort=iv:desc,cp:desc");
  await waitForCollection(page);
  await expect(filters).not.toHaveAttribute("open", "");
  await expect(page.locator("#active-filters")).toContainText("IV %: ≥ 96");

  await page.goto("/");
  await waitForCollection(page);
  await page.locator("#preset-select").selectOption("high-iv");
  await page.locator("#apply-preset").click();
  await expect(filters).not.toHaveAttribute("open", "");
  await expect(page.locator("#active-filters")).toContainText("IV %: ≥ 96");
});

test("Clear filters preserves sorting and rows while Reset view restores defaults", async ({ page }) => {
  const filters = page.locator("#advanced-filters");
  await filters.locator(":scope > summary").click();
  await page.locator("#page-size").selectOption("100");
  await page.keyboard.press("Escape");
  await expect(filters).not.toHaveAttribute("open", "");

  await page.locator('[data-sort-key="cp"]').click();
  await expect(page).toHaveURL(/sort=cp%3Aasc|sort=cp:asc/);

  await page.locator("#search").fill("pikachu");
  await expect(page).toHaveURL(/q=pikachu/);
  await page.getByRole("button", { name: "Clear all search and filter criteria" }).click();

  await expect(page.locator("#search")).toHaveValue("");
  await expect(page.locator("#page-size")).toHaveValue("100");
  await expect(page).toHaveURL(/sort=cp%3Aasc|sort=cp:asc/);
  expect(new URL(page.url()).searchParams.has("q")).toBeFalsy();

  await page.locator(".data-menu > summary").click();
  await page.getByRole("button", { name: /Reset filters, sorting, pagination/ }).click();
  await page.waitForURL((url) => url.search === "");
  await waitForCollection(page);
  await expect(page.locator("#page-size")).toHaveValue("50");
  await expect(page.locator("#sort-status-chip")).toBeHidden();
});

test("free-text search is debounced and the final URL is canonical", async ({ page }) => {
  await page.locator("#search").pressSequentially("pikachu", { delay: 10 });
  await expect(page).toHaveURL(/q=pikachu/);
  const metrics = await page.evaluate(() => ({ ...window.CollectionUsability.metrics }));
  expect(metrics.searchEventsSuppressed).toBe(7);
  expect(metrics.searchDispatches).toBe(1);
  expect(metrics.searchCacheBuilds).toBeGreaterThan(1000);

  await page.locator("#search").fill("bulbasaur");
  await expect(page).toHaveURL(/q=bulbasaur/);
  const updated = await page.evaluate(() => ({ ...window.CollectionUsability.metrics }));
  expect(updated.searchDispatches).toBe(2);
  expect(updated.searchCacheHits).toBeGreaterThan(1000);
});

test("filter chips have explicit removal names and accessible touch targets", async ({ page }) => {
  await page.locator("#preset-select").selectOption("hundos");
  await page.locator("#apply-preset").click();
  const chip = page.locator("#active-filters .filter-chip").filter({ hasText: "Hundo: Yes" });
  await expect(chip).toHaveAttribute("aria-label", "Remove Hundo: Yes filter");
  const box = await chip.boundingBox();
  expect(box).not.toBeNull();
  expect(box.height).toBeGreaterThanOrEqual(44);
});

test("nondefault sort state is visible and opens the Sort drawer", async ({ page }) => {
  const chip = page.locator("#sort-status-chip");
  await expect(chip).toBeHidden();
  await page.locator('[data-sort-key="cp"]').click();
  await expect(chip).toBeVisible();
  await expect(chip).toContainText("Sort: 1. CP ↑");
  await expect(chip).toHaveAttribute("aria-label", /Edit sort order: 1\. CP ↑/);
  await chip.click();
  await expect(page.locator("#sort-details")).toHaveAttribute("open", "");
});
