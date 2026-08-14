"use strict";

const { chromium } = require("@playwright/test");

async function main() {
  const baseUrl = String(process.env.PAGE_URL || "").replace(/\/+$/, "") + "/";
  const expectedBuildId = String(process.env.EXPECTED_BUILD_ID || "");
  if (!/^https?:\/\//.test(baseUrl) || !/^[0-9a-f]{12}$/.test(expectedBuildId)) {
    throw new Error("PAGE_URL and a 12-character EXPECTED_BUILD_ID are required");
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const fatal = [];
  page.on("pageerror", (error) => fatal.push(String(error.message || error)));
  page.on("console", (message) => {
    if (message.type() === "error") fatal.push(`console: ${message.text()}`);
  });

  try {
    await page.goto(`${baseUrl}?verify=${expectedBuildId}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.locator("#result-count").waitFor({ state: "visible", timeout: 20000 });
    await page.waitForFunction(() => !String(document.querySelector("#result-count")?.textContent || "").includes("Loading collection"), null, { timeout: 20000 });
    const manifestBuild = await page.evaluate(async () => (await (await fetch(`data/build-manifest.json?smoke=${Date.now()}`, { cache: "no-store" })).json()).build_id);
    if (manifestBuild !== expectedBuildId) throw new Error(`browser loaded build ${manifestBuild}, expected ${expectedBuildId}`);

    const firstName = await page.evaluate(async () => {
      const payload = await (await fetch(`data/pokemon.json?smoke=${Date.now()}`, { cache: "no-store" })).json();
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
    console.log(`Production browser smoke passed for ${expectedBuildId}: exact search, zero-result search, Tools resources, and navigation verified.`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
