"use strict";

const { expect, test } = require("@playwright/test");

test("secondary page headers reflow at 320px without collapsing branding", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "Pinned Chromium owns the narrow reflow contract.");
  await page.setViewportSize({ width: 320, height: 800 });

  for (const [path, heading] of [["/insights.html", "Collection Insights"], ["/tools.html", "Collection Tools"]]) {
    await page.goto(path);
    const title = page.getByRole("heading", { level: 1, name: heading });
    await expect(title).toBeVisible();

    const layout = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      brandWidth: document.querySelector(".site-header > .brand")?.getBoundingClientRect().width || 0,
    }));
    expect(layout.overflow).toBeLessThanOrEqual(1);
    expect(layout.brandWidth).toBeGreaterThan(120);
  }
});
