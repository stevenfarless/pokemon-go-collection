"use strict";
const assert = require("node:assert/strict");
const Diagnostics = require("../site/diagnostics.js");

function healthyReport() {
  return {
    generated_at: "2026-08-23T00:00:00Z",
    summary: "",
    connectivity: { online: true, manifest_reachable: true, cached_manifest_available: true },
    build: { build_id: "abc", source_file: "export.csv", export_timestamp: "x", service_worker_build_id: "abc", consistent: true },
    service_worker: { supported: true, controlled: true, build_id: "abc", waiting: false, active: true },
    critical_resources: [
      { path: "data/pokemon.json", reachable: true, status: 200, build_id: "abc", matches_active_build: true },
      { path: "data/collection-summary.json", reachable: true, status: 200, build_id: "abc", matches_active_build: true },
    ],
    data_health: { available: true, blockers: [] },
    external_freshness: { available: true, categories: [{ category: "events", freshness: "fresh", provider: "Official" }] },
    storage: {
      state: "healthy",
      write: { ok: true },
      storage_manager: {},
      last_backup_at: "",
      namespaces: [{ name: "annotations", schema_version: 2, status: "healthy", bytes: 400, unresolved: 0, recoverable: true, secret_note: "do not export" }],
    },
    capabilities: { clipboard: true },
  };
}

{
  const report = Diagnostics.assess(healthyReport());
  assert.equal(report.summary, "Healthy");
  assert.deepEqual(report.issues, []);
  const text = Diagnostics.diagnosticText(report);
  assert.equal(text.includes("do not export"), false);
  assert.equal(text.includes("annotations"), true);
}

{
  const report = healthyReport();
  report.connectivity.online = false;
  assert.equal(Diagnostics.assess(report).summary, "Offline");
}

{
  const report = healthyReport();
  report.external_freshness.categories[0].freshness = "stale";
  const evaluated = Diagnostics.assess(report);
  assert.equal(evaluated.summary, "Limited");
  const issue = evaluated.issues.find((item) => item.code === "external-data-stale");
  assert.ok(issue);
  assert.match(issue.action, /refresh succeeds/i);
}

{
  const report = healthyReport();
  report.build.service_worker_build_id = "old-build";
  report.build.consistent = false;
  report.service_worker.build_id = "old-build";
  const evaluated = Diagnostics.assess(report);
  assert.equal(evaluated.summary, "Needs attention");
  const issue = evaluated.issues.find((item) => item.code === "service-worker-build-mismatch");
  assert.ok(issue);
  assert.match(issue.action, /update\/reload flow/i);
}

{
  const report = healthyReport();
  report.storage.namespaces[0] = { name: "annotations", schema_version: 2, status: "corrupt", bytes: 400, unresolved: 0, recoverable: true };
  const evaluated = Diagnostics.assess(report);
  assert.equal(evaluated.summary, "Needs attention");
  const issue = evaluated.issues.find((item) => item.code === "local-namespace-corrupt");
  assert.ok(issue);
  assert.match(issue.action, /last-known-good snapshot/i);
}

{
  const report = healthyReport();
  report.storage.write.ok = false;
  const evaluated = Diagnostics.assess(report);
  assert.equal(evaluated.summary, "Needs attention");
  const issue = evaluated.issues.find((item) => item.code === "storage-write-failed");
  assert.ok(issue);
  assert.match(issue.action, /backup/i);
}

{
  const report = healthyReport();
  report.critical_resources[0] = { path: "data/pokemon.json", reachable: true, status: 200, build_id: "other", matches_active_build: false };
  const evaluated = Diagnostics.assess(report);
  assert.equal(evaluated.summary, "Needs attention");
  const issue = evaluated.issues.find((item) => item.code === "critical-resource-build-mismatch");
  assert.ok(issue);
  assert.match(issue.action, /one build/i);
}

{
  assert.equal(Diagnostics.buildIdOf({ build_id: "one" }), "one");
  assert.equal(Diagnostics.buildIdOf({ manifest: { build_id: "two" } }), "two");
  assert.equal(Diagnostics.buildIdOf({ metadata: { build_id: "three" } }), "three");
  assert.equal(Diagnostics.buildIdOf({}), null);
}

console.log("diagnostics tests passed");
