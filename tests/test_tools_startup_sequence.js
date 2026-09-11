"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const planning = fs.readFileSync(path.join(root, "site", "planning.js"), "utf8");
assert.match(
  planning,
  /root\.__collectionPlanningReady = api\.install\(root\)/,
  "planning bootstrap must expose its initialization promise",
);

for (const filename of ["final-tools.js", "local-data.js"]) {
  const source = fs.readFileSync(path.join(root, "site", filename), "utf8");
  assert.match(
    source,
    /Promise\.resolve\(root\.__collectionPlanningReady\)\.then\(\(\) => api\.install\(root\)\)/,
    `${filename} must wait for planning initialization before starting heavy work`,
  );
}

const readyIndex = planning.indexOf("status.textContent = `Loaded");
const yieldIndex = planning.indexOf("await new Promise(r=>setTimeout(r));");
const teamIndex = planning.indexOf("installTeamUi(root, resources)", yieldIndex);
assert.ok(readyIndex >= 0 && yieldIndex > readyIndex && teamIndex > yieldIndex, "planning must yield after reporting readiness and before secondary UI setup");

const tools = fs.readFileSync(path.join(root, "site", "tools.html"), "utf8");
assert.match(tools, /const cache = new Map\(\)/, "Tools must share repeat heavy JSON fetches within the page load");
assert.match(tools, /pokemon\\\.json\|knowledge\\\/pokemon-go\\\.json\|external\\\/index\\\.json/, "Tools cache must cover the repeated canonical, knowledge, and external resources");
assert.match(tools, /response\.clone\(\)/, "each cached fetch consumer must receive an independent Response body");
assert.match(tools, /\?v=\[a-f0-9\]\+/, "build-versioned static resources must share the same page cache");
assert.doesNotMatch(tools, /migration.*sharedResource|connectivity.*sharedResource/, "one-off migration and connectivity probes must remain uncached");

console.log("Tools startup sequencing tests passed.");
