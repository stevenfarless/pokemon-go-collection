"use strict";

const path = require("node:path");

const tests = [
  "test_advanced_search.js",
  "test_dashboard.js",
  "test_companion.js",
  "test_local_data.js",
  "test_js_fuzz.js",
  "test_storage_health.js",
  "test_security_boundaries.js",
  "test_pwa_lifecycle.js",
  "test_diagnostics.js",
  "test_design_system.js",
  "test_i18n.js",
  "test_product_experience.js",
  "test_action_workflows.js",
  "test_player_labs.js",
  "test_advanced_labs.js",
];

for (const testFile of tests) require(path.resolve(__dirname, "..", "tests", testFile));
