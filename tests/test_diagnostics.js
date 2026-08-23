"use strict";
const assert = require("node:assert/strict");
const Diagnostics = require("../site/diagnostics.js");

const report = {
  generated_at: "2026-08-23T00:00:00Z",
  summary: "Healthy",
  connectivity: { online: true, manifest_reachable: true, cached_manifest_available: true },
  build: { build_id: "abc", source_file: "export.csv", export_timestamp: "x", service_worker_build_id: "abc", consistent: true },
  service_worker: { controlled: true },
  data_health: { available: true },
  external_freshness: { available: true, categories: [] },
  storage: { state: "healthy", write: { ok: true }, storage_manager: {}, last_backup_at: "", namespaces: [{ name: "annotations", schema_version: 2, status: "healthy", bytes: 400, unresolved: 0, recoverable: true, secret_note: "do not export" }] },
  capabilities: { clipboard: true },
};
assert.equal(Diagnostics.classify(report), "Healthy");
const text = Diagnostics.diagnosticText(report);
assert.equal(text.includes("do not export"), false);
assert.equal(text.includes("annotations"), true);
const offline = structuredClone(report); offline.connectivity.online = false;
assert.equal(Diagnostics.classify(offline), "Offline");
console.log("diagnostics tests passed");
