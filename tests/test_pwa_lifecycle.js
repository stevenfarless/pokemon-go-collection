"use strict";
const assert = require("node:assert/strict");
const Pwa = require("../site/pwa-lifecycle.js");

(async () => {
  let copied = "";
  const root = { navigator: { clipboard: { async writeText(value) { copied = value; } } } };
  const result = await Pwa.share(root, { text: "safe share" });
  assert.equal(result.ok, true);
  assert.equal(result.method, "clipboard");
  assert.equal(copied, "safe share");
  const unsupported = await Pwa.share({ navigator: {} }, { text: "x" });
  assert.equal(unsupported.ok, false);
  console.log("pwa lifecycle tests passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
