"use strict";

const { chromium } = require("@playwright/test");

const DEFAULT_ATTEMPTS = 5;
const DEFAULT_DELAY_MS = 5000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
  throw new Error(`production browser smoke failed after ${attempts} attempts: ${message}`, { cause: lastError });
}

function describeConsoleMessage(message) {
  const location = message.location?.() || {};
  const suffix = location.url ? ` (${location.url}${location.lineNumber != null ? `:${location.lineNumber}` : ""})` : "";
  return `console: ${message.text()}${suffix}`;
}

function isIgnorableRequestFailure(request, baseUrl) {
  const errorText = String(request.failure?.()?.errorText || "");
  if (errorText !== "net::ERR_ABORTED") return false;

  try {
    const failedUrl = new URL(request.url());
    const collectionUrl = new URL(baseUrl);
    return failedUrl.origin === collectionUrl.origin && failedUrl.pathname === collectionUrl.pathname;
  } catch {
    return false;
  }
}

async function verifyBrowserOnce(browser, baseUrl, expectedBuildId) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const fatal = [];

  page.on("pageerror", (error) => fatal.push(`pageerror: ${String(error.message || error)}`));
  page.on("console", (message) => {
    if (message.type() === "error") fatal.push(describeConsoleMessage(message));
  });
  page.on("response", (response) => {
    if (response.status() >= 500) fatal.push(`HTTP ${response.status()}: ${response.url()}`);
  });
  page.on("requestfailed", (request) => {
    if (isIgnorableRequestFailure(request, baseUrl)) return;
    fatal.push(`request failed: ${request.url()} (${request.failure()?.errorText || "unknown network error"})`);
  });

  try {
    await page.goto(`${baseUrl}?verify=${expectedBuildId}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.locator("#result-count").waitFor({ state: "visible", timeout: 20000 });
    await page.waitForFunction(() => !String(document.querySelector("#result-count")?.textContent || "").includes("Loading collection"), null, { timeout: 20000 });

    const manifestBuild = await page.evaluate(async () => {
      const response = await fetch(`data/build-manifest.json?smoke=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`build-manifest HTTP ${response.status}`);
      return (await response.json()).build_id;
    });
    if (manifestBuild !== expectedBuildId) throw new Error(`browser loaded build ${manifestBuild}, expected ${expectedBuildId}`);

    const firstName = await page.evaluate(async () => {
      const response = await fetch(`data/pokemon.json?smoke=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`pokemon.json HTTP ${response.status}`);
      const payload = await response.json();
      return String(payload.records?.find((record) => record?.name)?.name || "");
    });
    if (!firstName) throw new Error("canonical collection had no searchable record name");

    const search = page.locator("#search");
    await search.fill(firstName);
    await search.press("Enter");
    await page.waitForFunction(() => {
      const text = String(document.querySelector("#result-count")?.textContent || "");
      return /^\s*[1-9][0-9,]*\s+results/i.test(text);
    }, null, { timeout: 10000 });

    await search.fill("definitely-no-such-pokemon-987654");
    await search.press("Enter");
    await page.waitForFunction(() => String(document.querySelector("#result-count")?.textContent || "").includes("0 results"), null, { timeout: 10000 });
    if (await page.locator("#pokemon-body tr").count()) throw new Error("impossible search returned collection rows");

    const toolsHref = await page.locator('a[href="tools.html"]').first().getAttribute("href");
    if (toolsHref !== "tools.html") throw new Error("root Tools navigation is missing");

    await page.goto(`${baseUrl}tools.html?verify=${expectedBuildId}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.locator("#planner-load-status").waitFor({ state: "visible", timeout: 20000 });
    await page.locator("#local-data-status").waitFor({ state: "visible", timeout: 20000 });
    await page.waitForFunction(() => /ready|records/i.test(String(document.querySelector("#local-data-status")?.textContent || "")), null, { timeout: 20000 });
    if (!(await page.locator("#enrichment").count()) || !(await page.locator("#local-data-backup").count())) throw new Error("Tools enrichment/backup controls are missing");
    if (!(await page.locator('a[href="index.html"]').count()) || !(await page.locator('a[href="insights.html"]').count())) throw new Error("Tools cross-page navigation is missing");

    if (fatal.length) throw new Error(`fatal browser errors: ${fatal.join(" | ")}`);
    return {
      buildId: expectedBuildId,
      exactSearch: firstName,
    };
  } finally {
    await context.close();
  }
}

async function main() {
  const baseUrl = String(process.env.PAGE_URL || "").replace(/\/+$/, "") + "/";
  const expectedBuildId = String(process.env.EXPECTED_BUILD_ID || "");
  if (!/^https?:\/\//.test(baseUrl) || !/^[0-9a-f]{12}$/.test(expectedBuildId)) {
    throw new Error("PAGE_URL and a 12-character EXPECTED_BUILD_ID are required");
  }

  const attempts = Math.max(1, Number(process.env.PRODUCTION_BROWSER_SMOKE_ATTEMPTS || DEFAULT_ATTEMPTS));
  const delayMs = Math.max(0, Number(process.env.PRODUCTION_BROWSER_SMOKE_DELAY_MS || DEFAULT_DELAY_MS));
  const browser = await chromium.launch({ headless: true });

  try {
    const result = await runWithRetry(
      () => verifyBrowserOnce(browser, baseUrl, expectedBuildId),
      {
        attempts,
        delayMs,
        onRetry(error, attempt, total) {
          console.warn(`Production browser smoke attempt ${attempt}/${total} failed: ${error.message || error}. Retrying after ${delayMs} ms.`);
        },
      },
    );
    console.log(`Production browser smoke passed for ${result.buildId}: exact search (${result.exactSearch}), zero-result search, Tools resources, navigation, and fatal browser errors verified.`);
  } finally {
    await browser.close();
  }
}

module.exports = {
  DEFAULT_ATTEMPTS,
  DEFAULT_DELAY_MS,
  runWithRetry,
  verifyBrowserOnce,
  describeConsoleMessage,
  isIgnorableRequestFailure,
};

if (require.main === module) {
  main().catch((error) => {
    console.error(error.stack || error);
    process.exitCode = 1;
  });
}
