"use strict";

const { expect, test } = require("@playwright/test");

const ONBOARDING_KEY = "pokemon-go-collection:onboarding:v1";

test("first-run orientation appears once and persists dismissal", async ({ page }) => {
  await page.goto("/");
  await page.evaluate((key) => localStorage.removeItem(key), ONBOARDING_KEY);
  await page.reload();

  const onboarding = page.locator("#product-onboarding-dialog");
  await expect(onboarding).toBeVisible();
  await expect(onboarding).toContainText("Collection is the owned-record workspace");
  await onboarding.getByRole("button", { name: "Got it" }).click();
  await expect(onboarding).toBeHidden();
  await expect.poll(() => page.evaluate((key) => localStorage.getItem(key), ONBOARDING_KEY)).toBe("done");

  await page.reload();
  await expect(onboarding).toBeHidden();
});
