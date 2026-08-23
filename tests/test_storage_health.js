"use strict";
const assert = require("node:assert/strict");
const StorageHealth = require("../site/storage-health.js");

class MemoryStorage {
  constructor() { this.map = new Map(); this.failWrites = false; }
  getItem(key) { return this.map.has(key) ? this.map.get(key) : null; }
  setItem(key, value) { if (this.failWrites) throw new Error("quota"); this.map.set(key, String(value)); }
  removeItem(key) { this.map.delete(key); }
}

{
  const storage = new MemoryStorage();
  storage.setItem(StorageHealth.CATALOG.annotations.key, JSON.stringify({ version: 2, records: { abc: { note: "private" } }, unresolved: [] }));
  let report = StorageHealth.scanNamespaces(storage);
  assert.equal(report.namespaces.find((item) => item.name === "annotations").status, "healthy");
  storage.setItem(StorageHealth.CATALOG.annotations.key, "{broken");
  report = StorageHealth.scanNamespaces(storage, { updateSnapshots: false });
  const broken = report.namespaces.find((item) => item.name === "annotations");
  assert.equal(broken.status, "corrupt");
  assert.equal(broken.recoverable, true);
  assert.equal(StorageHealth.recoverNamespace(storage, "annotations").ok, true);
  assert.equal(JSON.parse(storage.getItem(StorageHealth.CATALOG.annotations.key)).records.abc.note, "private");
}

{
  const storage = new MemoryStorage();
  storage.failWrites = true;
  assert.equal(StorageHealth.probeWrite(storage).ok, false);
}

console.log("storage health tests passed");
