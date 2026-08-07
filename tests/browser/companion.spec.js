"use strict";

const { expect, test } = require("@playwright/test");

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection");
  await expect.poll(() => page.locator("#pokemon-body tr").count()).toBeGreaterThan(0);
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await waitForCollection(page);
});

test("mobile cards expose core data and a full detail dialog", async ({ page }, testInfo) => {
  test.skip(!testInfo.project.name.includes("mobile"));
  await expect(page.locator(".table-card")).toBeHidden();
  const card = page.locator(".pokemon-card").first();
  await expect(card).toBeVisible();
  await expect(card).toContainText("CP");
  await expect(card).toContainText("IV");
  await card.getByRole("button", { name: "Details" }).click();
  const dialog = page.locator("#pokemon-detail-dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator(".record-fields")).toContainText("pokemon_number");
  await expect(dialog.locator(".detail-pvp")).toContainText("Great League");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("comparison survives pagination and supports reordering and clearing", async ({ page }, testInfo) => {
  const mobile = testInfo.project.name.includes("mobile");
  const firstCompare = mobile
    ? page.locator(".pokemon-card").first().getByRole("button", { name: "Compare" })
    : page.locator("#pokemon-body tr").first().getByRole("button", { name: "Compare" });
  await firstCompare.click();
  await expect(page.locator("#comparison-tray")).toBeVisible();
  await expect(page.locator("[data-compare-count]")).toHaveText("1");
  await page.locator("#next-page").click();
  await expect(page.locator("[data-compare-count]")).toHaveText("1");
  const secondCompare = mobile
    ? page.locator(".pokemon-card").first().getByRole("button", { name: "Compare" })
    : page.locator("#pokemon-body tr").first().getByRole("button", { name: "Compare" });
  await secondCompare.click();
  await expect(page.locator("[data-compare-count]")).toHaveText("2");
  await page.locator("[data-open-comparison]").click();
  await expect(page.locator("#pokemon-compare-dialog")).toBeVisible();
  await expect(page.locator("#pokemon-compare-dialog .comparison-grid article")).toHaveCount(2);
  await page.locator("#pokemon-compare-dialog [data-move-right]").first().click();
  await page.keyboard.press("Escape");
  await page.locator("[data-clear-comparison]").click();
  await expect(page.locator("#comparison-tray")).toBeHidden();
});

test("saved views persist, duplicate, rename, delete, export, and import", async ({ page }) => {
  await page.locator("#search").fill("pikachu");
  await expect(page).toHaveURL(/q=pikachu/);
  await page.locator("#saved-views > summary").click();
  await page.locator("#saved-view-name").fill("Pikachu review");
  await page.locator("#save-current-view").click();
  await expect(page.locator("#saved-view-list")).toContainText("Pikachu review");

  await page.locator("[data-duplicate-view='0']").click();
  await expect(page.locator("#saved-view-list .saved-view-row")).toHaveCount(2);
  page.once("dialog", async (dialog) => dialog.accept("Pikachu favorites"));
  await page.locator("[data-rename-view='1']").click();
  await expect(page.locator("#saved-view-list")).toContainText("Pikachu favorites");

  const downloadPromise = page.waitForEvent("download");
  await page.locator("#export-saved-views").click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("pokemon-go-collection-saved-views.json");

  page.once("dialog", async (dialog) => dialog.accept());
  await page.locator("[data-delete-view='1']").click();
  await expect(page.locator("#saved-view-list .saved-view-row")).toHaveCount(1);

  await page.locator("#import-saved-views").setInputFiles({
    name: "views.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ version: 1, views: [{ name: "Imported", query: "?status=shadow", columns: ["pokemon", "status"] }] })),
  });
  await expect(page.locator("#saved-view-list")).toContainText("Imported");
});

test("GO search generator explains exact, approximate, and omitted conditions", async ({ page }) => {
  await page.locator("#advanced-filters > summary").click();
  await page.locator("#status-filter").selectOption("shadow");
  const statsGroup = page.locator(".filter-group").filter({ hasText: "Stats and level" });
  await statsGroup.locator("summary").click();
  await page.locator("#cp-min").fill("1000");
  await page.locator("#cp-max").fill("1500");
  await page.keyboard.press("Escape");
  await page.locator("#go-search-builder").click();
  const dialog = page.locator("#go-search-dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator("#go-search-output")).toHaveValue(/cp1000-1500&shadow|shadow&cp1000-1500/);
  await expect(dialog).toContainText("Exact");
  await expect(dialog).toContainText("Not represented");
  await expect(dialog).toContainText("2026-08-07");
  await expect(dialog.getByRole("link", { name: /official Pokémon GO Help Center/i })).toHaveAttribute("href", /niantic\.helpshift\.com/);
});

test("PWA resources install and a loaded collection remains usable offline", async ({ page, context }) => {
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute("href", "manifest.webmanifest");
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
  await context.setOffline(true);
  try {
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator("#offline-status")).toBeVisible();
    await expect(page.locator("#offline-status")).toContainText("Offline");
    await expect(page.locator("#result-count")).not.toContainText("Loading collection");
  } finally {
    await context.setOffline(false);
  }
});
