"use strict";

const assert = require("assert");
const Backup = require("../site/storage-search-backup.js");

function memoryStorage(initial = {}, failKey = null) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) {
      if (key === failKey) throw new Error("simulated storage failure");
      values.set(key, String(value));
    },
    removeItem(key) { values.delete(key); },
    snapshot() { return Object.fromEntries(values.entries()); },
  };
}

function localApi() {
  const BASE_KEY = "base:key";
  return {
    STORAGE_KEYS: { base: BASE_KEY },
    buildUnifiedBackup(storage) {
      const raw = storage.getItem(BASE_KEY);
      return {
        product: "pokemon-go-collection-local-data",
        backup_version: 1,
        namespaces: {
          base: { storage_key: BASE_KEY, schema_version: 1, present: raw != null, data: raw == null ? null : JSON.parse(raw) },
        },
      };
    },
    validateUnifiedBackup(raw, storage) {
      if (raw.product !== "pokemon-go-collection-local-data" || Number(raw.backup_version) !== 1) throw new Error("bad base backup");
      const envelope = { ...raw, namespaces: { ...(raw.namespaces || {}) } };
      const preview = { added: [], replaced: [], absent: [], ignored: [] };
      const entry = envelope.namespaces.base;
      if (entry?.present) (storage.getItem(BASE_KEY) == null ? preview.added : preview.replaced).push("base");
      return { envelope, preview };
    },
    restoreUnifiedBackup(storage, raw) {
      const validated = this.validateUnifiedBackup(raw, storage);
      const entry = validated.envelope.namespaces.base;
      if (entry?.present) storage.setItem(BASE_KEY, JSON.stringify(entry.data));
      return validated.preview;
    },
  };
}

{
  const storage = memoryStorage({
    "base:key": JSON.stringify({ ok: true }),
    [Backup.SEARCH_TEMPLATES_KEY]: JSON.stringify({ version: 1, templates: [{ name: "Cleanup", expression: "!favorite&!shiny", updated_at: "2026-08-28T00:00:00Z" }] }),
    [Backup.CLEANUP_KEY]: JSON.stringify({ version: 1, decisions: { abc: "approve" }, config: { slotsNeeded: 50 } }),
  });
  const backup = Backup.buildUnifiedBackupWithStorageSearch(localApi(), null, storage);
  assert.equal(backup.namespaces.search_templates.present, true);
  assert.equal(backup.namespaces.storage_cleanup.present, true);
  assert.equal(backup.namespaces.search_templates.data.templates[0].name, "Cleanup");
  const validated = Backup.validateUnifiedBackupWithStorageSearch(localApi(), null, backup, memoryStorage(), []);
  assert(validated.preview.added.includes("search_templates"));
  assert(validated.preview.added.includes("storage_cleanup"));
}

{
  assert.throws(() => Backup.validateSearchTemplates({ version: 1, templates: [
    { name: "Same", expression: "shiny" }, { name: "same", expression: "costume" },
  ] }), /duplicate/i);
  assert.throws(() => Backup.validateCleanupState({ version: 1, decisions: { x: "transfer" }, config: {} }), /invalid record decision/i);
}

{
  const source = memoryStorage({
    "base:key": JSON.stringify({ source: true }),
    [Backup.SEARCH_TEMPLATES_KEY]: JSON.stringify({ version: 1, templates: [{ name: "PvP", expression: "3*&!favorite", updated_at: "" }] }),
    [Backup.CLEANUP_KEY]: JSON.stringify({ version: 1, decisions: { x: "exclude" }, config: {} }),
  });
  const api = localApi();
  const backup = Backup.buildUnifiedBackupWithStorageSearch(api, null, source);
  const target = memoryStorage({ "base:key": JSON.stringify({ old: true }) });
  const preview = Backup.restoreUnifiedBackupWithStorageSearch(api, null, target, backup, []);
  assert(preview.replaced.includes("base"));
  assert.equal(JSON.parse(target.getItem(Backup.SEARCH_TEMPLATES_KEY)).templates[0].name, "PvP");
  assert.equal(JSON.parse(target.getItem(Backup.CLEANUP_KEY)).decisions.x, "exclude");
}

{
  const api = localApi();
  const source = memoryStorage({
    "base:key": JSON.stringify({ source: true }),
    [Backup.SEARCH_TEMPLATES_KEY]: JSON.stringify({ version: 1, templates: [{ name: "One", expression: "shiny", updated_at: "" }] }),
    [Backup.CLEANUP_KEY]: JSON.stringify({ version: 1, decisions: { a: "approve" }, config: {} }),
  });
  const backup = Backup.buildUnifiedBackupWithStorageSearch(api, null, source);
  const target = memoryStorage({
    "base:key": JSON.stringify({ before: true }),
    [Backup.SEARCH_TEMPLATES_KEY]: JSON.stringify({ version: 1, templates: [{ name: "Before", expression: "lucky", updated_at: "" }] }),
  }, Backup.CLEANUP_KEY);
  const beforeBase = target.getItem("base:key");
  const beforeTemplates = target.getItem(Backup.SEARCH_TEMPLATES_KEY);
  assert.throws(() => Backup.restoreUnifiedBackupWithStorageSearch(api, null, target, backup, []), /Restore failed/);
  assert.equal(target.getItem("base:key"), beforeBase);
  assert.equal(target.getItem(Backup.SEARCH_TEMPLATES_KEY), beforeTemplates);
}

console.log("storage/search unified backup tests passed");
