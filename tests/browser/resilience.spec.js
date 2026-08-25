"use strict";

const { expect, test } = require("@playwright/test");

test.use({ serviceWorkers: "block" });

const FAILURE_MESSAGE = "The dashboard data failed to load. Use the CSV or JSON download links above.";

async function expectFailClosed(page) {
  const body = page.locator("#pokemon-body");
  await expect(body).toContainText(FAILURE_MESSAGE, { timeout: 20_000 });
  await expect(body.locator("tr")).toHaveCount(1);

  const dataMenu = page.locator("details.data-menu");
  await dataMenu.locator(":scope > summary").click();
  await expect(dataMenu.locator('a[href="data/latest-export.csv"]')).toBeVisible();
  await expect(dataMenu.locator('a[href="data/pokemon.json"]')).toBeVisible();
}

function chromiumOnly(testInfo) {
  test.skip(
    testInfo.project.name !== "desktop-chromium",
    "The fast resilience gate runs once in pinned Chromium; cross-engine healthy-path coverage is owned by @compat.",
  );
}

test("@resilience critical collection HTTP failure fails closed with recovery links", async ({ page }, testInfo) => {
  chromiumOnly(testInfo);
  await page.route("**/data/pokemon.json*", (route) => route.fulfill({
    status: 503,
    contentType: "application/json",
    body: JSON.stringify({ error: "seeded resilience failure" }),
  }));

  await page.goto("/");

  await expect(page.locator("#result-count")).toHaveText("Collection data could not be loaded");
  await expectFailClosed(page);
});

test("@resilience malformed critical JSON cannot produce a partial collection", async ({ page }, testInfo) => {
  chromiumOnly(testInfo);
  await page.route("**/data/pokemon.json*", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: "{ this is deliberately malformed JSON",
  }));

  await page.goto("/");

  await expectFailClosed(page);
});

test("@resilience network loss during companion data fetch cannot produce a mixed healthy view", async ({ page }, testInfo) => {
  chromiumOnly(testInfo);
  await page.route("**/data/collection-summary.json*", (route) => route.abort("internetdisconnected"));

  await page.goto("/");

  await expectFailClosed(page);
});
