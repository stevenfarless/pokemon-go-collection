"use strict";

const { expect, test } = require("@playwright/test");

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection");
  await expect.poll(() => page.locator("#pokemon-body tr").count()).toBeGreaterThan(0);
}

async function waitForPlanning(page) {
  await expect(page.locator("#planner-load-status")).toContainText("canonical owned records", { timeout: 20_000 });
  await expect(page.locator("#goal-exclusions")).toBeAttached({ timeout: 20_000 });
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

test("advanced search remains bounded at current collection size and a 2x fixture", async ({ page }) => {
  await page.goto("/");
  await waitForCollection(page);
  const benchmark = await page.evaluate(async () => {
    const response = await fetch("data/pokemon.json");
    const payload = await response.json();
    const records = payload.records;
    const Search = window.CollectionAdvancedSearch;
    const Engine = window.CollectionFilterEngine;
    const run = (items) => {
      const start = performance.now();
      let matches = 0;
      for (const record of items) if (Search.fuzzyPlainMatches(record, "pikchu", Engine)) matches += 1;
      return { ms: performance.now() - start, matches };
    };
    return {
      currentCount: records.length,
      current: run(records),
      doubled: run(records.concat(records)),
    };
  });
  expect(benchmark.currentCount).toBeGreaterThan(0);
  expect(benchmark.current.matches).toBeGreaterThan(0);
  expect(benchmark.doubled.matches).toBe(benchmark.current.matches * 2);
  expect(benchmark.current.ms).toBeLessThan(1500);
  expect(benchmark.doubled.ms).toBeLessThan(3000);
});

test("planning page builds an owned-only team with warnings, alternatives, and freshness boundary", async ({ page }) => {
  await page.goto("/tools.html");
  await waitForPlanning(page);
  await expect(page.locator("#team-locks option").first()).toBeAttached();
  await page.locator("#build-team").click();
  await expect(page.locator("#team-results .team-list li").first()).toBeVisible();
  await expect(page.locator("#team-results")).toContainText("Current-data freshness");
  await expect(page.locator("#team-results")).toContainText("Current meta/boss strength was not used");
  await expect(page.locator("#team-results [data-team-extras]")).toContainText("Build warnings");
  await expect(page.locator("#team-results [data-team-extras]")).toContainText("Legacy/exclusive/recommended move requirements");
  await expect(page.locator("#team-results [data-team-extras]")).toContainText("Alternatives");
});

test("resource optimizer explains exclusions and accumulates side-by-side what-if scenarios", async ({ page }) => {
  await page.goto("/tools.html");
  await waitForPlanning(page);

  await page.locator("#budget-dust").fill("250000");
  await page.locator("#budget-candy").fill("250");
  await page.locator("#run-optimizer").click();
  await expect(page.locator("#optimizer-results")).toContainText("projects fit the entered budget");
  await expect(page.locator("#optimizer-results")).toContainText("missing costs are not silently estimated");
  await expect(page.locator("#optimizer-results [data-optimizer-exclusions]")).toContainText("Why projects were excluded");

  await expect(page.locator("#scenario-record option").first()).toBeAttached();
  await page.locator("#scenario-type").selectOption("level40");
  await page.locator("#run-scenario").click();
  await expect(page.locator("#scenario-results")).toContainText("Power current species to level 40");
  await expect(page.locator("#scenario-results")).toContainText("Power-up model");
  await expect(page.locator("#scenario-comparisons .scenario-comparison-card")).toHaveCount(1);

  await page.locator("#scenario-type").selectOption("shadow-purified");
  await page.locator("#run-scenario").click();
  await expect(page.locator("#scenario-results")).toContainText("No purification recommendation is made");
  await expect(page.locator("#scenario-results")).toContainText("Purification is irreversible");
  await expect(page.locator("#scenario-comparisons .scenario-comparison-card")).toHaveCount(2);
});

test("goals are browser-local, support exclusions and drill-down, survive reload, and expose unsupported fields", async ({ page }) => {
  await page.goto("/tools.html");
  await waitForPlanning(page);

  await page.locator("#goal-kind").selectOption("hundo");
  await page.locator("#goal-target").fill("5");
  await page.locator("#goal-exclusions").fill("201");
  await page.locator("#add-goal").click();
  await expect(page.locator("#goal-list .goal-card")).toHaveCount(1);
  await expect(page.locator("#goal-list .goal-card [data-goal-detail]")).toContainText("1 exclusions");
  await expect(page.locator("#goal-list .goal-card [data-goal-detail]")).toContainText("Owned drill-down");
  await expect(page.locator("#goal-list .goal-card [data-goal-detail]")).toContainText("Missing drill-down");

  await page.reload();
  await waitForPlanning(page);
  await expect(page.locator("#goal-list .goal-card")).toHaveCount(1);
  await expect(page.locator("#goal-list .goal-card [data-goal-detail]")).toContainText("1 exclusions");

  await page.locator("#goal-kind").selectOption("shiny");
  await page.locator("#goal-target").fill("1");
  await page.locator("#add-goal").click();
  await expect(page.locator("#goal-list")).toContainText("cannot be measured");
  await expect(page.locator("#goal-list [data-goal-detail]").last()).toContainText("State: unsupported");
});

test("trade planner exposes canonical IDs and protection warnings instead of safe-transfer claims", async ({ page }) => {
  await page.goto("/tools.html#trade-planner");
  await waitForPlanning(page);
  await expect(page.locator("#trade-results")).toContainText("review-only");
  await expect(page.locator("#trade-results")).toContainText("Unsupported or unreliable trade-value facts");
  await expect(page.locator("#trade-results .trade-group").first()).toBeVisible();
  await page.locator("#trade-results .trade-group").first().locator("summary").click();
  await expect(page.locator("#trade-results .trade-group").first()).toContainText("Pokémon GO helper search");
  await expect(page.locator("#trade-results .trade-group").first().locator("small").first()).toContainText(/record|[0-9a-f]{8}/i);
});
