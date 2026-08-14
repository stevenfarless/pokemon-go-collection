"use strict";

const { expect, test } = require("@playwright/test");

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection");
  await expect.poll(() => page.locator("#pokemon-body tr").count()).toBeGreaterThan(0);
}

test("advanced search tolerates common species typos and exposes natural-language interpretation", async ({ page }) => {
  await page.goto("/");
  await waitForCollection(page);

  await page.locator("#search").fill("pikchu");
  await expect(page.locator("#result-count")).not.toContainText("0 results");
  await expect(page.locator("#pokemon-body tr").first()).toContainText(/Pikachu/i);

  await page.locator("#search").fill("shadow dragons under 1500 cp");
  const interpretation = page.locator("#search-interpretation");
  await expect(interpretation).toBeVisible();
  await expect(interpretation).toContainText("status:shadow");
  await expect(interpretation).toContainText("type:dragon");
  await expect(interpretation).toContainText("cp:0-1499");
  await expect(interpretation.getByRole("button", { name: "Use structured query" })).toBeVisible();
});

test("planning page builds an owned-only team and exposes freshness boundary", async ({ page }) => {
  await page.goto("/tools.html");
  await expect(page.locator("#planner-load-status")).toContainText("canonical owned records");
  await expect(page.locator("#team-locks option").first()).toBeAttached();
  await page.locator("#build-team").click();
  await expect(page.locator("#team-results .team-list li").first()).toBeVisible();
  await expect(page.locator("#team-results")).toContainText("Current-data freshness");
  await expect(page.locator("#team-results")).toContainText("Current meta/boss strength was not used");
});

test("resource optimizer and what-if simulator produce explicit local calculations", async ({ page }) => {
  await page.goto("/tools.html");
  await expect(page.locator("#planner-load-status")).toContainText("canonical owned records");

  await page.locator("#budget-dust").fill("250000");
  await page.locator("#budget-candy").fill("250");
  await page.locator("#run-optimizer").click();
  await expect(page.locator("#optimizer-results")).toContainText("projects fit the entered budget");
  await expect(page.locator("#optimizer-results")).toContainText("missing costs are not silently estimated");

  await expect(page.locator("#scenario-record option").first()).toBeAttached();
  await page.locator("#scenario-type").selectOption("level40");
  await page.locator("#run-scenario").click();
  await expect(page.locator("#scenario-results")).toContainText("Power current species to level 40");
  await expect(page.locator("#scenario-results")).toContainText("Power-up model");
});

test("goals are browser-local, survive reload, and unsupported source fields are explicit", async ({ page }) => {
  await page.goto("/tools.html");
  await expect(page.locator("#planner-load-status")).toContainText("canonical owned records");

  await page.locator("#goal-kind").selectOption("hundo");
  await page.locator("#goal-target").fill("5");
  await page.locator("#add-goal").click();
  await expect(page.locator("#goal-list .goal-card")).toHaveCount(1);
  await page.reload();
  await expect(page.locator("#planner-load-status")).toContainText("canonical owned records");
  await expect(page.locator("#goal-list .goal-card")).toHaveCount(1);

  await page.locator("#goal-kind").selectOption("shiny");
  await page.locator("#goal-target").fill("1");
  await page.locator("#add-goal").click();
  await expect(page.locator("#goal-list")).toContainText("cannot be measured");
});

test("trade planner exposes canonical IDs and protection warnings instead of safe-transfer claims", async ({ page }) => {
  await page.goto("/tools.html#trade-planner");
  await expect(page.locator("#planner-load-status")).toContainText("canonical owned records");
  await expect(page.locator("#trade-results")).toContainText("review-only");
  await expect(page.locator("#trade-results .trade-group").first()).toBeVisible();
  await page.locator("#trade-results .trade-group").first().locator("summary").click();
  await expect(page.locator("#trade-results .trade-group").first()).toContainText("Pokémon GO helper search");
  await expect(page.locator("#trade-results .trade-group").first().locator("small").first()).toContainText(/record|[0-9a-f]{8}/i);
});
