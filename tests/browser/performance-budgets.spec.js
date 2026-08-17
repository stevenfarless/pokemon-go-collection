"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { expect, test } = require("@playwright/test");

const budgets = JSON.parse(fs.readFileSync(path.resolve("config/performance-budgets.json"), "utf8"));
const payload = JSON.parse(fs.readFileSync(path.resolve(process.env.COLLECTION_DIST || "dist", "data", "pokemon.json"), "utf8"));
const originalRecords = payload.records || [];

function expandedPayload(targetCount) {
  if (targetCount <= originalRecords.length) return payload;
  const records = [];
  for (let index = 0; index < targetCount; index += 1) {
    const source = originalRecords[index % originalRecords.length];
    const copy = JSON.parse(JSON.stringify(source));
    copy.source_index = index + 1;
    if (copy.identity?.record_id) copy.identity.record_id = `${copy.identity.record_id}-perf-${index}`;
    records.push(copy);
  }
  return { ...payload, records, manifest: { ...payload.manifest, pokemon_count: records.length } };
}

async function heapMb(page) {
  const session = await page.context().newCDPSession(page);
  await session.send("Performance.enable");
  const response = await session.send("Performance.getMetrics");
  const metric = response.metrics.find((item) => item.name === "JSHeapUsedSize");
  await session.detach();
  return metric ? metric.value / (1024 * 1024) : null;
}

async function measureScenario(page, targetCount) {
  const body = JSON.stringify(expandedPayload(targetCount));
  await page.route("**/data/pokemon.json*", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body });
  });
  const startupStarted = Date.now();
  await page.goto("/");
  await expect(page.locator("#result-count")).not.toContainText("Loading collection", { timeout: 30_000 });
  await expect.poll(() => page.locator("#pokemon-body tr").count(), { timeout: 30_000 }).toBeGreaterThan(0);
  const startupMs = Date.now() - startupStarted;

  const searchStarted = Date.now();
  await page.locator("#search").fill("mewtwo");
  await expect(page).toHaveURL(/q=mewtwo/, { timeout: 10_000 });
  await expect(page.locator("#result-count")).not.toContainText("Loading collection", { timeout: 10_000 });
  const searchMs = Date.now() - searchStarted;
  const memory = await heapMb(page);
  await page.unroute("**/data/pokemon.json*");
  return { startupMs, searchMs, heapMb: memory };
}

function assertBudget(measured, limit, label) {
  expect(measured.startupMs, `${label} startup`).toBeLessThanOrEqual(limit.startup_ms_max);
  expect(measured.searchMs, `${label} search`).toBeLessThanOrEqual(limit.search_ms_max);
  if (measured.heapMb !== null) expect(measured.heapMb, `${label} JS heap`).toBeLessThanOrEqual(limit.heap_mb_max);
}

test("current, 2x, and 10k collection sizes stay inside browser budgets", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "Performance budgets use one pinned Chromium runner.");
  const currentCount = originalRecords.length;
  expect(currentCount).toBeGreaterThan(0);

  const scenarios = [
    ["current", currentCount, budgets.browser.current_records],
    ["2x", currentCount * 2, budgets.browser.double_records],
    ["10k", Math.max(10000, currentCount), budgets.browser.stress_10000_records],
  ];
  const results = {};
  for (const [label, count, limit] of scenarios) {
    const measured = await measureScenario(page, count);
    results[label] = { count, ...measured };
    assertBudget(measured, limit, label);
  }
  await testInfo.attach("collection-performance.json", {
    body: Buffer.from(JSON.stringify(results, null, 2)),
    contentType: "application/json",
  });
});
