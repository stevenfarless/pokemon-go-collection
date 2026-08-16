"use strict";

const { expect, test } = require("@playwright/test");

async function waitForCollection(page) {
  await expect(page.locator("#result-count")).not.toContainText("Loading collection");
  await expect.poll(() => page.locator("#pokemon-body tr").count()).toBeGreaterThan(0);
}

function isConnectivityProbeResponse(response) {
  try {
    const url = new URL(response.url());
    return url.pathname.endsWith("/data/build-manifest.json") && url.searchParams.has("connectivity");
  } catch {
    return false;
  }
}

async function loadCollection(page) {
  const connectivityProbe = page.waitForResponse(isConnectivityProbeResponse);
  await page.goto("/");
  await waitForCollection(page);
  const response = await connectivityProbe;
  expect(response.ok()).toBeTruthy();
}

test("clipboard denial falls back to selected text for manual copy", async ({ page }) => {
  await loadCollection(page);
  await page.locator("#advanced-filters > summary").click();
  await page.locator("#status-filter").selectOption("shadow");
  await page.locator("#go-search-builder").click();

  const dialog = page.locator("#go-search-dialog");
  await expect(dialog).toBeVisible();
  const output = dialog.locator("#go-search-output");
  await expect(output).not.toHaveValue("");

  await page.evaluate(() => {
    const rejectedClipboard = {
      writeText() {
        return Promise.reject(new Error("clipboard unavailable in compatibility test"));
      },
    };
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: rejectedClipboard,
    });
  });

  await dialog.locator("#copy-go-search").click();
  await expect(dialog.locator("#go-search-copy-status")).toHaveText(
    "Clipboard permission was unavailable. The text is selected for manual copy.",
  );

  const selection = await output.evaluate((element) => ({
    start: element.selectionStart,
    end: element.selectionEnd,
    length: element.value.length,
  }));
  expect(selection.start).toBe(0);
  expect(selection.end).toBe(selection.length);
});
