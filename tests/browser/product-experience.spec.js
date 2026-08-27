"use strict";

const { expect, test } = require("@playwright/test");

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection", { timeout: 20_000 });
  await expect.poll(() => page.locator("#pokemon-body tr").count(), { timeout: 20_000 }).toBeGreaterThan(0);
}

test("global utility bar and command shortcut remain keyboard reachable", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "Desktop Chromium owns the product-experience interaction contract.");
  await page.goto("/");
  await waitForCollection(page);

  const bar = page.locator("#product-utility-bar");
  await expect(bar).toBeVisible();
  await expect(bar.getByRole("link", { name: "Today" })).toHaveAttribute("href", "today.html");
  await expect(bar.getByRole("link", { name: "Reference" })).toHaveAttribute("href", "reference.html");
  await expect(bar.getByRole("button", { name: "Guidance" })).toBeVisible();
  await expect(bar.getByRole("button", { name: "Global search" })).toHaveAttribute("aria-keyshortcuts", /Control\+K/);

  await page.keyboard.press("Control+K");
  const dialog = page.locator("#product-global-search");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("searchbox", { name: "Global search" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test.describe("clean first-run profile", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("orientation stays discoverable and persists its completion locally", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "One pinned browser owns the first-run storage contract.");
    await page.goto("/");
    await waitForCollection(page);

    const onboarding = page.locator("#product-onboarding-dialog");
    const start = page.getByRole("button", { name: "Start here" });
    await expect(start).toBeVisible();
    await expect(onboarding).toBeHidden();

    await start.click();
    await expect(onboarding).toBeVisible();
    await expect(onboarding).toContainText("Collection is the owned-record workspace");
    await onboarding.getByRole("button", { name: "Got it" }).click();
    await expect(onboarding).toBeHidden();
    await expect(start).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => localStorage.getItem("pokemon-go-collection:onboarding:v1"))).toBe("done");

    await page.reload();
    await waitForCollection(page);
    await expect(page.locator("#product-onboarding-dialog")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Start here" })).toHaveCount(0);
  });
});
