"use strict";

const { expect, test } = require("@playwright/test");

async function loadCollection(page) {
  await page.goto("/", { waitUntil: "domcontentloaded", timeout: 30_000 });
  await expect(page.locator("#result-count")).not.toContainText("Loading collection", { timeout: 20_000 });
  await expect.poll(() => page.locator("#pokemon-body tr").count(), { timeout: 20_000 }).toBeGreaterThan(0);
  await expect.poll(() => page.locator("#mobile-results .pokemon-card").count(), { timeout: 20_000 }).toBeGreaterThan(0);
}

function requireMobile(testInfo) {
  test.skip(!testInfo.project.name.includes("mobile"), "Real-device regression contract applies to mobile projects.");
}

async function assertMobileGeometry(page) {
  const tableCard = page.locator(".table-card");
  const pagination = page.locator(".pagination");
  const cards = page.locator("#mobile-results");
  const firstCard = cards.locator(".pokemon-card").first();
  await expect(firstCard).toBeVisible();

  const [tableBox, cardBox] = await Promise.all([
    tableCard.boundingBox(),
    firstCard.boundingBox(),
  ]);
  expect(tableBox).not.toBeNull();
  expect(cardBox).not.toBeNull();
  expect(tableBox.height).toBeLessThan(40);
  expect(cardBox.y - (tableBox.y + tableBox.height)).toBeLessThan(32);

  const pagerFollowsCards = await cards.evaluate((element) => {
    const pager = document.querySelector(".pagination");
    return Boolean(pager && (element.compareDocumentPosition(pager) & Node.DOCUMENT_POSITION_FOLLOWING));
  });
  expect(pagerFollowsCards).toBeTruthy();
  await expect(pagination).toBeVisible();

  const summaryOverflow = await page.locator(".compact-stats").evaluate((element) => element.scrollWidth - element.clientWidth);
  expect(summaryOverflow).toBeLessThanOrEqual(2);
}

test("@compat mobile results stay compact at representative phone widths", async ({ page }, testInfo) => {
  requireMobile(testInfo);
  test.setTimeout(60_000);
  await loadCollection(page);

  for (const width of [320, 393, 430]) {
    await page.setViewportSize({ width, height: 851 });
    await assertMobileGeometry(page);
  }

  await page.setViewportSize({ width: 393, height: 851 });
  await testInfo.attach("collection-mobile-first-screen", {
    body: await page.screenshot({ fullPage: false }),
    contentType: "image/png",
  });
});

test("@compat secondary collection actions collapse into mobile More", async ({ page }, testInfo) => {
  requireMobile(testInfo);
  test.setTimeout(45_000);
  await loadCollection(page);

  const more = page.locator("#mobile-more");
  const panel = more.locator(".mobile-more-panel");
  await expect(more).toBeVisible();
  for (const selector of ["#saved-views", ".columns-menu", "#copy-link", "#go-search-builder"]) {
    await expect.poll(() => page.locator(selector).evaluate((element) => element.parentElement?.className || "")).toContain("mobile-more-panel");
  }
  await more.locator(":scope > summary").click();
  await expect(panel).toBeVisible();
  await expect(page.locator("#copy-link")).toBeVisible();
  await expect(page.locator("#go-search-builder")).toBeVisible();

  await page.setViewportSize({ width: 800, height: 851 });
  await expect(more).toBeHidden();
  await expect.poll(() => page.locator("#copy-link").evaluate((element) => element.parentElement?.className || "")).toContain("primary-toolbar");
});

test("@compat mobile primary actions retain 44px targets", async ({ page }, testInfo) => {
  requireMobile(testInfo);
  test.setTimeout(45_000);
  await loadCollection(page);

  for (const selector of [
    "#advanced-filters > summary",
    "#sort-controls > summary",
    "#mobile-more > summary",
  ]) {
    const box = await page.locator(selector).boundingBox();
    expect(box).not.toBeNull();
    expect(box.height).toBeGreaterThanOrEqual(44);
  }
});

test("@compat mobile cards separate IV, status, and Poke Genie ranking semantics", async ({ page }, testInfo) => {
  requireMobile(testInfo);
  test.setTimeout(45_000);
  await loadCollection(page);

  const card = page.locator("#mobile-results .pokemon-card").first();
  await expect(card.locator(".pokemon-card-status")).toBeVisible();
  await expect(card.locator(".pokemon-card-ranking")).toHaveText(
    /Great League(?:: no Poke Genie IV rank| IV rank: .+)/,
  );
  await expect(card.locator(".pokemon-card-meta")).not.toContainText(/weight|height/i);

  const ivStat = page.locator("#mobile-results .pokemon-card-stats > span:nth-child(2)").filter({ hasText: "%" }).first();
  await expect(ivStat).toBeVisible();
  await expect(ivStat.locator("strong")).toHaveText(/%$/);
  await expect(ivStat.locator(".pokemon-card-iv-detail")).toContainText(/\s\/\s/);
  await expect(ivStat).not.toContainText(/%\d/);

  await testInfo.attach("collection-mobile-card-semantics", {
    body: await card.screenshot(),
    contentType: "image/png",
  });
});

test("@compat controlled card variants keep status, ranking, and missing data explicit", async ({ page }, testInfo) => {
  requireMobile(testInfo);
  test.setTimeout(45_000);
  await loadCollection(page);

  const variants = await page.evaluate(() => {
    const sourceRow = document.querySelector("#pokemon-body tr");
    const sourceCard = document.querySelector("#mobile-results .pokemon-card");
    if (!sourceRow || !sourceCard || !globalThis.CollectionAccessibility) return [];

    const render = ({ ivPercent, ivDetail, status, rank }) => {
      const row = sourceRow.cloneNode(true);
      const card = sourceCard.cloneNode(true);
      row.cells[2].innerHTML = `<strong>${ivPercent}</strong><small>${ivDetail}</small>`;
      row.cells[5].innerHTML = status === "normal"
        ? '<span class="muted">normal</span>'
        : `<span class="badge">${status}</span>`;
      row.cells[6].innerHTML = rank ? `<strong>${rank}</strong>` : '<span class="muted">No ranking</span>';
      delete card.dataset.mobileSemanticSource;
      document.body.append(card);
      globalThis.CollectionAccessibility.enhanceMobileCard(card, row, document);
      const result = {
        iv: card.querySelector(".pokemon-card-stats > span:nth-child(2)")?.innerText || "",
        status: card.querySelector(".pokemon-card-status")?.textContent || "",
        ranking: card.querySelector(".pokemon-card-ranking")?.textContent || "",
        aria: card.querySelector(".pokemon-card-stats > span:nth-child(2)")?.getAttribute("aria-label") || "",
      };
      card.remove();
      return result;
    };

    return [
      render({ ivPercent: "100.00%", ivDetail: "15/15/15 · 45/45", status: "normal", rank: "99.98%" }),
      render({ ivPercent: "97.78%", ivDetail: "15/14/15 · 44/45", status: "shadow", rank: "" }),
      render({ ivPercent: "—", ivDetail: "", status: "purified", rank: "" }),
    ];
  });

  expect(variants).toHaveLength(3);
  expect(variants[0].iv).toContain("100.00%");
  expect(variants[0].iv).toContain("15 / 15 / 15 · 45 / 45");
  expect(variants[0].aria).toContain("exact 15 / 15 / 15 · 45 / 45");
  expect(variants[0].ranking).toContain("Great League IV rank: 99.98%");
  expect(variants[1].status).toBe("Shadow");
  expect(variants[1].ranking).toBe("Great League: no Poke Genie IV rank");
  expect(variants[2].status).toBe("Purified");
  expect(variants[2].iv).toContain("Exact IVs unavailable");
});

test("@compat mobile hierarchy survives 200% text scale, forced colors, and long labels", async ({ page }, testInfo) => {
  requireMobile(testInfo);
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 320, height: 851 });
  await page.emulateMedia({ colorScheme: "light", forcedColors: "active" });
  await loadCollection(page);
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "32px";
    const heading = document.querySelector("#mobile-results .pokemon-card h3");
    if (heading) heading.textContent = "Pokémon collection example with an intentionally long translated species and form label";
  });

  const card = page.locator("#mobile-results .pokemon-card").first();
  await expect(card).toBeVisible();
  const [cardBox, headingBox] = await Promise.all([
    card.boundingBox(),
    card.locator("h3").boundingBox(),
  ]);
  expect(cardBox).not.toBeNull();
  expect(headingBox).not.toBeNull();
  expect(headingBox.width).toBeLessThanOrEqual(cardBox.width + 1);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(2);

  await testInfo.attach("collection-mobile-200-percent-forced-colors", {
    body: await page.screenshot({ fullPage: false }),
    contentType: "image/png",
  });
});
