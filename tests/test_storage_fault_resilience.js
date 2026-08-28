"use strict";

const assert = require("node:assert/strict");
const StorageHealth = require("../site/storage-health.js");
const Diagnostics = require("../site/diagnostics.js");

class FaultStorage {
  constructor() {
    this.map = new Map();
    this.failReads = new Set();
    this.failWrites = false;
  }

  getItem(key) {
    if (this.failReads.has(key)) throw new Error("seeded read failure");
    return this.map.has(key) ? this.map.get(key) : null;
  }

  setItem(key, value) {
    if (this.failWrites) throw new Error("seeded quota failure");
    this.map.set(key, String(value));
  }

  removeItem(key) {
    if (this.failWrites) throw new Error("seeded quota failure");
    this.map.delete(key);
  }
}

function annotationsPayload(note = "preserve me") {
  return JSON.stringify({ version: 2, records: { abc: { note } }, unresolved: [] });
}

function diagnosticsBase(storageReport) {
  return {
    generated_at: "2026-08-28T09:30:00Z",
    summary: "",
    connectivity: { online: true, manifest_reachable: true, cached_manifest_available: true },
    build: { build_id: "abc", service_worker_build_id: "abc", consistent: true },
    service_worker: { supported: true, controlled: true, build_id: "abc", waiting: false, active: true },
    critical_resources: [],
    data_health: { available: true, blockers: [] },
    external_freshness: { available: true, categories: [] },
    storage: storageReport,
    capabilities: {},
  };
}

(async () => {
  {
    const storage = new FaultStorage();
    const original = annotationsPayload();
    storage.setItem(StorageHealth.CATALOG.annotations.key, original);
    const baseline = StorageHealth.scanNamespaces(storage);
    assert.equal(baseline.metadata_saved, true);

    storage.setItem(StorageHealth.CATALOG.annotations.key, "{broken");
    const broken = StorageHealth.scanNamespaces(storage, { updateSnapshots: false })
      .namespaces.find((item) => item.name === "annotations");
    assert.equal(broken.status, "corrupt");
    assert.equal(broken.recoverable, true);

    const recovered = StorageHealth.recoverNamespace(storage, "annotations");
    assert.equal(recovered.ok, true);
    assert.equal(storage.getItem(StorageHealth.CATALOG.annotations.key), original);
  }

  {
    const storage = new FaultStorage();
    storage.setItem(StorageHealth.CATALOG.annotations.key, annotationsPayload());
    StorageHealth.scanNamespaces(storage);
    storage.failReads.add(StorageHealth.CATALOG.annotations.key);

    const scan = StorageHealth.scanNamespaces(storage, { updateSnapshots: false });
    const unreadable = scan.namespaces.find((item) => item.name === "annotations");
    assert.equal(unreadable.status, "unreadable");
    assert.equal(unreadable.recoverable, true);
    assert.match(unreadable.detail, /seeded read failure/);

    const report = await StorageHealth.healthReport({ localStorage: storage, navigator: {} }, { updateSnapshots: false });
    assert.equal(report.state, "needs-attention");
    const evaluated = Diagnostics.assess(diagnosticsBase(report));
    assert.equal(evaluated.summary, "Needs attention");
    const issue = evaluated.issues.find((item) => item.code === "storage-needs-attention");
    assert.ok(issue);
    assert.match(issue.action, /backup/i);
    assert.match(issue.action, /Storage Health/i);
  }

  {
    const storage = new FaultStorage();
    storage.setItem(StorageHealth.CATALOG.annotations.key, annotationsPayload());
    StorageHealth.scanNamespaces(storage);
    storage.failWrites = true;

    const report = await StorageHealth.healthReport({ localStorage: storage, navigator: {} }, { updateSnapshots: false });
    assert.equal(report.write.ok, false);
    assert.equal(report.state, "needs-attention");
    assert.match(report.write.error, /quota failure/);

    const evaluated = Diagnostics.assess(diagnosticsBase(report));
    const issue = evaluated.issues.find((item) => item.code === "storage-write-failed");
    assert.ok(issue);
    assert.match(issue.action, /backup/i);
  }

  {
    const storage = new FaultStorage();
    storage.setItem(StorageHealth.CATALOG.annotations.key, annotationsPayload("last known good"));
    StorageHealth.scanNamespaces(storage);
    const corrupt = "{do not silently replace";
    storage.setItem(StorageHealth.CATALOG.annotations.key, corrupt);
    storage.failWrites = true;

    const recovered = StorageHealth.recoverNamespace(storage, "annotations");
    assert.equal(recovered.ok, false);
    assert.match(recovered.error, /quota failure/);
    storage.failWrites = false;
    assert.equal(storage.getItem(StorageHealth.CATALOG.annotations.key), corrupt);
  }

  console.log("storage fault resilience tests passed");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
