"use strict";

const { expect, test } = require("@playwright/test");

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection", { timeout: 20_000 });
  await expect.poll(() => page.locator("#pokemon-body tr").count(), { timeout: 20_000 }).toBeGreaterThan(0);
  await expect.poll(() => page.locator("#mobile-results .pokemon-card").count(), { timeout: 20_000 }).toBeGreaterThan(0);
}

function requireMobile(testInfo) {
  test.skip(!testInfo.project.name.includes("mobile"), "Real-device regression contract applies to mobile projects.");
}

test("@compat mobile results do not reserve a hidden desktop-table viewport", async ({ page }, testInfo) => {
  requireMobile(testInfo);
  await page.goto("/");
  await waitForCollection(page);

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
});

test("@compat mobile cards separate IV, status, and Poke Genie ranking semantics", async ({ page }, testInfo) => {
  requireMobile(testInfo);
  await page.goto("/");
  await waitForCollection(page);

  const card = page.locator("#mobile-results .pokemon-card").first();
  await expect(card.locator(".pokemon-card-status")).toBeVisible();
  await expect(card.locator(".pokemon-card-ranking")).toContainText("Poke Genie IV rank");
  await expect(card.locator(".pokemon-card-meta")).not.toContainText(/weight|height/i);

  const rankedIv = page.locator("#mobile-results .pokemon-card-stats > span:nth-child(2)").filter({ hasText: "%" }).first();
  await expect(rankedIv).toBeVisible();
  await expect(rankedIv.locator("strong")).toHaveText(/%$/);
  await expect(rankedIv.locator(".pokemon-card-iv-detail")).toContainText(/\s\/\s/);
  await expect(rankedIv).not.toContainText(/%\d/);
});
