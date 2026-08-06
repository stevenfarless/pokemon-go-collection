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

test("qualified search combines fields, plain text, quotes, and exclusions", async ({ page }) => {
  await page.locator("#search").fill('name:pikachu cp:500+ -status:shadow');
  await expect(page).toHaveURL(/q=name%3Apikachu/);
  await expect(page.locator("#result-count")).not.toContainText("0 results");
  const rows = page.locator("#pokemon-body tr");
  const count = await rows.count();
  expect(count).toBeGreaterThan(0);
  for (let index = 0; index < Math.min(count, 10); index += 1) {
    await expect(rows.nth(index).locator("td").first()).toContainText(/Pikachu/i);
    await expect(rows.nth(index).locator("td").nth(5)).not.toContainText(/shadow/i);
  }

  await page.locator("#search").fill('move:"shadow ball" lucky');
  await expect(page.locator("#result-count")).not.toContainText("0 results");

  await page.getByRole("button", { name: "Search syntax help" }).click();
  await expect(page.locator(".search-help-card")).toContainText("name:pikachu");
  await expect(page.locator(".search-help-card")).toContainText("Unknown or malformed");
});

test("malformed qualified terms fail safely as ordinary text", async ({ page }) => {
  await page.locator("#search").fill("cp:abc");
  await expect(page.locator("#search-syntax-status")).toContainText("ordinary text");
  await expect(page.locator("#result-count")).toContainText("0 results");
  await expect(page.locator("#pokemon-body")).toBeEmpty();
});

test("desktop column preferences persist and Reset view restores defaults", async ({ page }) => {
  const movesHeader = page.locator('th[data-column="moves"]');
  const datesHeader = page.locator('th[data-column="dates"]');
  await expect(movesHeader).toBeHidden();
  await expect(datesHeader).toBeHidden();

  await page.locator(".columns-menu > summary").click();
  await page.locator('[data-column-toggle="moves"]').check();
  await expect(movesHeader).toBeVisible();
  await page.reload();
  await waitForCollection(page);
  await expect(movesHeader).toBeVisible();

  await page.locator(".data-menu > summary").click();
  await page.getByRole("button", { name: /Reset filters, sorting, pagination/ }).click();
  await page.waitForURL((url) => url.search === "");
  await waitForCollection(page);
  await expect(movesHeader).toBeHidden();
  await expect(page.locator('th[data-column="pokemon"]')).toBeVisible();
});

test("Data Health discloses source freshness and links to review searches", async ({ page }) => {
  await page.locator(".data-menu > summary").click();
  await page.getByRole("button", { name: "Data Health" }).click();
  const panel = page.locator("#data-health-panel");
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("Export timestamp");
  await expect(panel).toContainText("incomplete scans");
  await expect(panel.locator('a[href*="quality=missing-any"]')).toBeVisible();
});

test("Insights page loads accessible summaries and collection drill-down links", async ({ page }) => {
  await page.goto("/insights.html");
  await expect(page.getByRole("heading", { level: 1, name: "Collection Insights" })).toBeVisible();
  await expect(page.locator("#insights-status")).toHaveText("Collection insights loaded");
  await expect(page.locator("#insights-overview .insight-card").first()).toBeVisible();
  await expect(page.locator("#duplicate-rows tr").first()).toBeVisible();
  const drillDown = page.locator("#duplicate-rows a").first();
  await expect(drillDown).toHaveAttribute("href", /species=/);
  await drillDown.click();
  await waitForCollection(page);
  expect(new URL(page.url()).searchParams.has("species")).toBeTruthy();
});
