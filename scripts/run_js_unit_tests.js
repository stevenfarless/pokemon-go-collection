"use strict";

const path = require("node:path");

const tests = [
  "test_advanced_search.js",
  "test_dashboard.js",
  "test_companion.js",
  "test_local_data.js",
  "test_js_fuzz.js",
];

for (const testFile of tests) require(path.resolve(__dirname, "..", "tests", testFile));
