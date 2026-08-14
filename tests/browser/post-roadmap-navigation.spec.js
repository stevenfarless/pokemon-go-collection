"use strict";

const { expect, test } = require("@playwright/test");

test("Collection exposes Tools and Tools links back to Collection and Insights", async ({ page }) => {
  await page.goto("/");
  await page.locator(".data-menu > summary").click();

  const toolsLink = page.getByRole("link", { name: "Tools" });
  await expect(toolsLink).toBeVisible();
  await expect(toolsLink).toHaveAttribute("href", "tools.html");
  await toolsLink.click();

  await expect(page.getByRole("heading", { level: 1, name: "Collection Tools" })).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Collection pages" });
  await expect(nav.getByRole("link", { name: "Collection" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Insights" })).toBeVisible();
});

test("Insights exposes accessible Tools navigation", async ({ page }) => {
  await page.goto("/insights.html");

  const nav = page.getByRole("navigation", { name: "Collection pages" });
  await expect(nav.getByRole("link", { name: "Collection" })).toBeVisible();

  const toolsLink = nav.getByRole("link", { name: "Tools" });
  await expect(toolsLink).toBeVisible();
  await expect(toolsLink).toHaveAttribute("href", "tools.html");
  await toolsLink.click();

  await expect(page.getByRole("heading", { level: 1, name: "Collection Tools" })).toBeVisible();
});
