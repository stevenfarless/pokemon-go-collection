"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { expect, test } = require("@playwright/test");

test.describe.configure({ retries: 0 });

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

async function installPerformanceObservers(page) {
  await page.addInitScript(() => {
    globalThis.__pgcPerf = { longTasks: [], interactionEvents: [] };
    if (typeof PerformanceObserver === "undefined") return;
    try {
      const longTaskObserver = new PerformanceObserver((list) => {
        globalThis.__pgcPerf.longTasks.push(...list.getEntries().map((entry) => entry.duration));
      });
      longTaskObserver.observe({ type: "longtask", buffered: true });
    } catch {}
    try {
      const eventObserver = new PerformanceObserver((list) => {
        globalThis.__pgcPerf.interactionEvents.push(...list.getEntries().map((entry) => entry.duration));
      });
      eventObserver.observe({ type: "event", buffered: true, durationThreshold: 16 });
    } catch {}
  });
}

async function heapMb(page) {
  const session = await page.context().newCDPSession(page);
  await session.send("Performance.enable");
  const response = await session.send("Performance.getMetrics");
  const metric = response.metrics.find((item) => item.name === "JSHeapUsedSize");
  await session.detach();
  return metric ? metric.value / (1024 * 1024) : null;
}

async function collectionTelemetry(page) {
  return page.evaluate(() => {
    const state = globalThis.__pgcPerf || { longTasks: [], interactionEvents: [] };
    const resources = performance.getEntriesByType("resource").map((entry) => ({
      path: new URL(entry.name).pathname,
      decodedBodySize: entry.decodedBodySize || 0,
      transferSize: entry.transferSize || 0,
    }));
    const eagerHeavySecondaryData = resources.filter((entry) =>
      entry.path.endsWith(".json") &&
      !/\/(pokemon|build-manifest|collection-summary)\.json$/.test(entry.path) &&
      entry.decodedBodySize > 250_000,
    );
    return {
      longTaskCount: state.longTasks.length,
      maxLongTaskMs: state.longTasks.length ? Math.max(...state.longTasks) : 0,
      interactionEventMs: state.interactionEvents.length ? Math.max(...state.interactionEvents) : 0,
      eagerHeavySecondaryData,
    };
  });
}

async function measureFilterAndSort(page) {
  await page.locator("#search").fill("");
  await expect.poll(() => new URL(page.url()).searchParams.has("q"), { timeout: 10_000 }).toBeFalsy();
  const started = Date.now();
  await page.locator("#advanced-filters > summary").click();
  await page.locator("#status-filter").selectOption("normal");
  await page.keyboard.press("Escape");
  await expect.poll(() => new URL(page.url()).searchParams.get("status"), { timeout: 10_000 }).toBe("normal");

  for (let attempt = 0; attempt < 2 && !new URL(page.url()).searchParams.has("sort"); attempt += 1) {
    await page.evaluate(() => document.querySelector('[data-sort-key="cp"]')?.click());
    await page.waitForTimeout(25);
  }
  await expect.poll(() => new URL(page.url()).searchParams.has("sort"), { timeout: 10_000 }).toBeTruthy();
  return Date.now() - started;
}

async function measureDetailOpen(page, mobile) {
  const button = page.locator(".pokemon-card").first().getByRole("button", { name: "Details" });
  const started = Date.now();
  if (mobile) await button.click();
  else await button.evaluate((element) => element.click());
  await expect(page.locator("#pokemon-detail-dialog")).toBeVisible({ timeout: 10_000 });
  const elapsed = Date.now() - started;
  await page.keyboard.press("Escape");
  return elapsed;
}

async function measureToolsAndMigration(page) {
  const toolsStarted = Date.now();
  await page.goto("/tools.html");
  await expect(page.locator("#planner-load-status")).toContainText("canonical owned records", { timeout: 30_000 });
  const toolsInitMs = Date.now() - toolsStarted;

  const localMigrationMs = await page.evaluate(async () => {
    const api = globalThis.CollectionLocalData;
    if (!api) throw new Error("CollectionLocalData API is unavailable on Tools");
    const collection = await fetch(`data/pokemon.json?migration=${Date.now()}`).then((response) => response.json());
    const records = (collection.records || []).slice(0, 5000);
    const raw = { version: 1, records: {}, unresolved: [] };
    for (const record of records) {
      const id = String(record?.identity?.record_id || record?.record_id || "");
      if (!id) continue;
      raw.records[id] = { shiny: "unknown", compatibility: api.compatibility(record) };
    }
    const started = performance.now();
    const migrated = api.migrateEnrichment(raw, collection.records || []);
    if (!migrated) throw new Error("Synthetic local-data migration unexpectedly failed");
    return performance.now() - started;
  });
  return { toolsInitMs, localMigrationMs };
}

async function measureScenario(page, targetCount, { mobile = false } = {}) {
  const body = JSON.stringify(expandedPayload(targetCount));
  await page.route("**/data/pokemon.json*", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body });
  });

  const startupStarted = Date.now();
  await page.goto("/");
  await expect(page.locator("#result-count")).not.toContainText("Loading collection", { timeout: 30_000 });
  await expect.poll(() => page.locator("#pokemon-body tr").count(), { timeout: 30_000 }).toBeGreaterThan(0);
  const startupMs = Date.now() - startupStarted;

  const initialResources = await page.evaluate(() => performance.getEntriesByType("resource").map((entry) => ({
    path: new URL(entry.name).pathname,
    decodedBodySize: entry.decodedBodySize || 0,
  })));
  const eagerHeavySecondaryData = initialResources.filter((entry) =>
    entry.path.endsWith(".json") &&
    !/\/(pokemon|build-manifest|collection-summary)\.json$/.test(entry.path) &&
    entry.decodedBodySize > 250_000,
  );

  const searchStarted = Date.now();
  await page.locator("#search").fill("mewtwo");
  await expect(page).toHaveURL(/q=mewtwo/, { timeout: 10_000 });
  await expect(page.locator("#result-count")).not.toContainText("Loading collection", { timeout: 10_000 });
  const searchMs = Date.now() - searchStarted;

  const filterSortMs = await measureFilterAndSort(page);
  const detailOpenMs = await measureDetailOpen(page, mobile);
  const memory = await heapMb(page);
  const telemetry = await collectionTelemetry(page);
  telemetry.eagerHeavySecondaryData = eagerHeavySecondaryData;
  const tools = await measureToolsAndMigration(page);

  await page.unroute("**/data/pokemon.json*");
  return { startupMs, searchMs, filterSortMs, detailOpenMs, heapMb: memory, ...telemetry, ...tools };
}

function assertBudget(measured, limit, label) {
  const checks = [
    ["startupMs", "startup_ms_max", "startup"],
    ["searchMs", "search_ms_max", "search"],
    ["filterSortMs", "filter_sort_ms_max", "filter/sort"],
    ["detailOpenMs", "detail_open_ms_max", "detail open"],
    ["toolsInitMs", "tools_init_ms_max", "Tools initialization"],
    ["localMigrationMs", "local_migration_ms_max", "local-state migration"],
    ["interactionEventMs", "interaction_event_ms_max", "Event Timing interaction"],
    ["longTaskCount", "long_task_count_max", "long-task count"],
    ["maxLongTaskMs", "max_long_task_ms_max", "longest task"],
  ];
  for (const [metric, budget, description] of checks) {
    expect(measured[metric], `${label} ${description}`).toBeLessThanOrEqual(limit[budget]);
  }
  if (measured.heapMb !== null) expect(measured.heapMb, `${label} JS heap`).toBeLessThanOrEqual(limit.heap_mb_max);
  expect(measured.eagerHeavySecondaryData, `${label} eagerly loaded heavy secondary JSON`).toEqual([]);
}

async function attachResults(testInfo, name, results) {
  await testInfo.attach(name, {
    body: Buffer.from(JSON.stringify(results, null, 2)),
    contentType: "application/json",
  });
}

test("current, 2x, and 10k collection sizes stay inside full browser budgets", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "The full scaling matrix uses one pinned Chromium runner.");
  test.setTimeout(180_000);
  await installPerformanceObservers(page);
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
  await attachResults(testInfo, "collection-performance.json", results);
});

test("10k collection remains usable in the mobile Chromium stress profile", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "The mobile stress gate runs once on the pinned mobile Chromium profile.");
  test.setTimeout(90_000);
  await installPerformanceObservers(page);
  const count = Math.max(10000, originalRecords.length);
  const measured = await measureScenario(page, count, { mobile: true });
  assertBudget(measured, budgets.browser.mobile_stress_10000_records, "mobile 10k");
  await attachResults(testInfo, "collection-performance-mobile-10k.json", { count, ...measured });
});
