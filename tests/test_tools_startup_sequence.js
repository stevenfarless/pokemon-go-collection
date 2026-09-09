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

console.log("Tools startup sequencing tests passed.");
