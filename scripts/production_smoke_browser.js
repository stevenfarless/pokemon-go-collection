"use strict";

const { chromium } = require("@playwright/test");

const DEFAULT_ATTEMPTS = 5;
const DEFAULT_DELAY_MS = 5000;

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

async function runWithRetry(task, options = {}) {
  const attempts = Math.max(1, Number(options.attempts || DEFAULT_ATTEMPTS));
  const delayMs = Math.max(0, Number(options.delayMs ?? DEFAULT_DELAY_MS));
  const pause = options.sleep || sleep;
  const onRetry = options.onRetry || (() => {});
  let lastError = null;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await task(attempt);
    } catch (error) {
      lastError = error;
      if (attempt >= attempts) break;
      onRetry(error, attempt, attempts);
      await pause(delayMs);
    }
  }

  const message = lastError?.message || String(lastError || "unknown browser smoke failure");
  throw new Error(`browser smoke failed after ${attempts} attempts: ${message}`);
}

function isConnectivityProbeResponse(response) {
  try {
    const url = new URL(response.url());
    return url.pathname.endsWith("/data/build-manifest.json") && url.searchParams.has("connectivity");
  } catch {
    return false;
  }
}

async function smoke(url) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const fatal = [];

  page.on("pageerror", (error) => fatal.push(`page error: ${error.message}`));
  page.on("requestfailed", (request) => {
    fatal.push(`request failed: ${request.url()} (${request.failure()?.errorText || "unknown network error"})`);
  });

  const connectivityProbe = page.waitForResponse(isConnectivityProbeResponse, { timeout: 20000 });

  const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
  if (!response || !response.ok()) {
    throw new Error(`root navigation HTTP ${response ? response.status() : "no response"}`);
  }

  await page.waitForSelector("#pokemon-body tr", { timeout: 30000 });
  await page.waitForFunction(() => {
    const resultCount = document.querySelector("#result-count");
    return resultCount && !/Loading collection/i.test(resultCount.textContent || "");
  }, { timeout: 30000 });

  const probeResponse = await connectivityProbe;
  if (!probeResponse.ok()) throw new Error(`connectivity probe HTTP ${probeResponse.status()}`);
  if (await page.locator("#offline-status").isVisible()) {
    throw new Error("offline banner visible during healthy online load");
  }

  const toolsResponse = await page.goto(new URL("tools.html", url).href, { waitUntil: "domcontentloaded", timeout: 30000 });
  if (!toolsResponse || !toolsResponse.ok()) {
    throw new Error(`tools navigation HTTP ${toolsResponse ? toolsResponse.status() : "no response"}`);
  }
  await page.waitForSelector("#team-builder", { timeout: 30000 });
  await page.waitForFunction(() => {
    const status = document.querySelector("#planner-load-status");
    return status && !/Loading collection planning data/i.test(status.textContent || "");
  }, { timeout: 30000 });

  const collectionResponse = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
  if (!collectionResponse || !collectionResponse.ok()) {
    throw new Error(`collection return navigation HTTP ${collectionResponse ? collectionResponse.status() : "no response"}`);
  }
  await page.waitForSelector("#pokemon-body tr", { timeout: 30000 });
  await page.locator("#search").fill("name:pikachu");
  await page.waitForTimeout(150);
  const exactCount = await page.locator("#pokemon-body tr").count();
  if (exactCount < 1) throw new Error("exact collection search returned no rows");

  await page.locator("#search").fill("name:__production_smoke_impossible__");
  await page.waitForTimeout(150);
  const impossibleCount = await page.locator("#pokemon-body tr").count();
  if (impossibleCount !== 0) throw new Error("impossible collection search unexpectedly returned rows");

  await browser.close();

  if (fatal.length) throw new Error(fatal.join("\n"));
  console.log("Production browser smoke passed: collection, tools, search, and online connectivity are healthy.");
}

async function main() {
  const url = process.argv[2];
  if (!url) throw new Error("Usage: node scripts/production_smoke_browser.js <site-url>");
  await runWithRetry(() => smoke(url), {
    onRetry(error, attempt, attempts) {
      console.warn(`Browser smoke attempt ${attempt}/${attempts} failed: ${error.message}`);
    },
  });
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.stack || error.message || error);
    process.exit(1);
  });
}

module.exports = {
  DEFAULT_ATTEMPTS,
  DEFAULT_DELAY_MS,
  isConnectivityProbeResponse,
  runWithRetry,
  sleep,
  smoke,
};
