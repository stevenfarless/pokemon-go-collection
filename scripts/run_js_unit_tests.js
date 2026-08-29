"use strict";

const path = require("node:path");

const tests = [
  "test_advanced_search.js",
  "test_dashboard.js",
  "test_companion.js",
  "test_local_data.js",
  "test_js_fuzz.js",
  "test_storage_health.js",
  "test_storage_fault_resilience.js",
  "test_security_boundaries.js",
  "test_pwa_lifecycle.js",
  "test_offline_field_pack.js",
  "test_diagnostics.js",
  "test_design_system.js",
  "test_i18n.js",
  "test_product_experience.js",
  "test_action_workflows.js",
  "test_player_labs.js",
  "test_advanced_labs.js",
  "test_battle_labs.js",
  "test_opportunity_special_labs.js",
  "test_trade_resource_labs.js",
  "test_storage_search_labs.js",
  "test_storage_search_backup.js",
  "test_event_calendar.js",
  "test_evidence.js",
];

for (const testFile of tests) require(path.resolve(__dirname, "..", "tests", testFile));
