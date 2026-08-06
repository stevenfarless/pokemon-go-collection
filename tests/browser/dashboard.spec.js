"use strict";

const { expect, test } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection");
  await expect(page.locator("#pokemon-body tr").first()).toBeVisible();
}

async function closeOpenDrawer(page, drawer) {
  if (await drawer.getAttribute("open") !== null) {
    await page.keyboard.press("Escape");
    await expect(drawer).not.toHaveAttribute("open", "");
  }
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await waitForCollection(page);
});

test("personalized header displays and copies the public Friend Code", async ({ page, context }) => {
  const title = "Fuddledumpy’s Pokémon GO Collection";
  const displayCode = "2252 2231 2780";
  const origin = new URL(page.url()).origin;

  await expect(page).toHaveTitle(title);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
  await expect(page.locator(".trainer-contact")).toContainText(`Friend Code: ${displayCode}`);
  await expect(page.locator(".friend-code-value")).toHaveText(displayCode);
  await expect(page.locator('meta[name="description"]')).toHaveAttribute(
    "content",
    /Fuddledumpy.*2252 2231 2780/,
  );
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute("content", title);

  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin });
  await page.getByRole("button", { name: `Copy Friend Code ${displayCode}` }).click();
  await expect(page.locator("#friend-code-status")).toHaveText("Copied");
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe("225222312780");

  const viewport = page.viewportSize();
  const layout = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(layout.scrollWidth).toBeLessThanOrEqual(layout.clientWidth + 1);
  expect(viewport).not.toBeNull();
});

test("filter badge is hidden at zero and counts active advanced filters", async ({ page }) => {
  const drawer = page.locator("#advanced-filters");
  const badge = page.locator("#advanced-count");
  await expect(badge).toBeHidden();
  await drawer.locator(":scope > summary").click();
  const statusGroup = drawer.locator(".filter-group").filter({ hasText: "Status and scan quality" });
  await statusGroup.locator("summary").first().click();
  await page.locator("#hundo-filter").selectOption("yes");
  await expect(badge).toHaveText("1");
  await closeOpenDrawer(page, drawer);
  await expect(badge).toBeVisible();
  await expect(badge).toHaveText("1");
});

test("filter options load lazily on the first drawer opening", async ({ page }) => {
  await expect(page.locator("#species-options option")).toHaveCount(0);
  await page.locator("#advanced-filters > summary").click();
  await expect(page.locator("#advanced-filters")).toHaveAttribute("data-options-loaded", "true");
  expect(await page.locator("#species-options option").count()).toBeGreaterThan(100);
});

test("summary statistics act as compact collection shortcuts", async ({ page }) => {
  const count = async (id) => Number((await page.locator(id).textContent()).replace(/[^0-9]/g, ""));
  const total = await count("#total-count");
  const hundos = await count("#hundo-count");
  const shadows = await count("#shadow-count");
  const lucky = await count("#lucky-count");
  const maximumCp = await count("#highest-cp");

  await page.locator('[data-summary-preset="hundos"]').click();
  await expect(page.locator("#result-count")).toContainText(`${hundos.toLocaleString()} results`);
  await expect(page).toHaveURL(/hundo=yes/);

  await page.locator('[data-summary-preset="shadows"]').click();
  await expect(page.locator("#result-count")).toContainText(`${shadows.toLocaleString()} results`);
  await expect(page).toHaveURL(/status=shadow/);

  await page.locator('[data-summary-preset="lucky"]').click();
  await expect(page.locator("#result-count")).toContainText(`${lucky.toLocaleString()} results`);
  await expect(page).toHaveURL(/lucky=yes/);

  await page.locator('[data-summary-preset="max-cp"]').click();
  await expect(page).toHaveURL(new RegExp(`cpmin=${maximumCp}.*cpmax=${maximumCp}`));
  await expect(page.locator("#pokemon-body tr").first().locator("td").nth(1)).toContainText(maximumCp.toLocaleString());

  await page.locator('[data-summary-preset="species"]').click();
  await expect(page.locator("#result-count")).toContainText(`${total.toLocaleString()} results`);
  await expect(page).toHaveURL(/sort=name%3Aasc%2Ccp%3Adesc|sort=name:asc%2Ccp:desc/);

  await page.locator('[data-summary-preset="all"]').click();
  await expect(page.locator("#result-count")).toContainText(`${total.toLocaleString()} results`);
  expect(new URL(page.url()).search).toBe("");
});

test("drawers trap focus, close with Escape, and return focus", async ({ page }) => {
  for (const id of ["advanced-filters", "sort-details"]) {
    const drawer = page.locator(`#${id}`);
    const summary = drawer.locator(":scope > summary");
    await summary.focus();
    await summary.press("Enter");
    await expect(drawer).toHaveAttribute("open", "");
    await expect(drawer.locator(".drawer-panel")).toHaveAttribute("aria-modal", "true");
    await expect(drawer.locator(".drawer-panel")).toContainText(id === "advanced-filters" ? "Filters" : "Sort");
    await page.keyboard.press("Escape");
    await expect(drawer).not.toHaveAttribute("open", "");
    await expect(summary).toBeFocused();
  }
});

test("presets, chips, reset, pagination, sorting, and shared URLs work", async ({ page }) => {
  const filterDrawer = page.locator("#advanced-filters");
  await page.locator("#preset-select").selectOption("high-iv");
  await page.locator("#apply-preset").click();
  await expect(page.locator("#active-filters")).toContainText("IV %");
  await closeOpenDrawer(page, filterDrawer);
  await page.locator("#reset-filters").click();
  await expect(page.locator("#active-filters")).toContainText("No filters applied");

  await page.locator("#next-page").click();
  await expect(page).toHaveURL(/page=2/);
  await page.locator('[data-sort-key="cp"]').click();
  await expect(page).toHaveURL(/sort=cp%3Aasc|sort=cp:asc/);

  await page.goto("/?q=definitely-no-such-pokemon-987654");
  await expect(page.locator("#result-count")).toContainText("0 results");
  await expect(page.locator("#pokemon-body")).toBeEmpty();

  await page.goto("/?size=999&page=-3&sort=not-a-field:sideways&unknown=1");
  await waitForCollection(page);
  await expect(page.locator("#page-size")).toHaveValue("50");
  expect(new URL(page.url()).searchParams.has("unknown")).toBeFalsy();
});

test("data loading failure leaves a usable error state", async ({ page }) => {
  await page.route("**/data/pokemon.json*", (route) => route.abort());
  await page.reload();
  await expect(page.locator("#result-count")).toHaveText(/failed to fetch|could not be loaded/i);
  await expect(page.locator("#pokemon-body")).toContainText("dashboard data failed to load");
  await page.locator(".data-menu > summary").click();
  await expect(page.getByRole("link", { name: "CSV", exact: true })).toBeVisible();
});

test("primary search workflow has no critical accessibility violations", async ({ page }) => {
  const results = await new AxeBuilder({ page })
    .include("body")
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const critical = results.violations.filter((violation) => violation.impact === "critical");
  expect(critical).toEqual([]);
});

test("startup benchmark stays within the documented long-task budget", async ({ page }) => {
  const measurement = await page.evaluate(() => {
    const init = performance.getEntriesByName("collection-initialize").at(-1);
    return { duration: init?.duration ?? null };
  });
  expect(measurement.duration).not.toBeNull();
  expect(measurement.duration).toBeLessThan(1500);
  console.log(`collection-initialize=${measurement.duration.toFixed(1)}ms`);
});
