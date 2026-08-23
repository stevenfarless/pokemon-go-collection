"use strict";
const assert = require("node:assert/strict");
const Pwa = require("../site/pwa-lifecycle.js");

(async () => {
  let copied = "";
  const clipboardRoot = { navigator: { clipboard: { async writeText(value) { copied = value; } } } };
  const clipboardResult = await Pwa.share(clipboardRoot, { text: "safe share" });
  assert.equal(clipboardResult.ok, true);
  assert.equal(clipboardResult.method, "clipboard");
  assert.equal(copied, "safe share");

  let shared = null;
  const shareRoot = { navigator: { async share(payload) { shared = payload; } } };
  const shareResult = await Pwa.share(shareRoot, { title: "Collection", url: "https://example.test/" });
  assert.equal(shareResult.ok, true);
  assert.equal(shareResult.method, "share");
  assert.deepEqual(shared, { title: "Collection", url: "https://example.test/" });

  const unsupported = await Pwa.share({ navigator: {} }, { text: "x" });
  assert.equal(unsupported.ok, false);
  assert.equal(unsupported.method, "none");
  console.log("pwa lifecycle tests passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
