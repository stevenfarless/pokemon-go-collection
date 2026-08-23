"use strict";

(function exposeStorageHealth(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionStorageHealth = api;
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const META_KEY = "pokemon-go-collection:storage-health:v1";
  const META_VERSION = 1;
  const CATALOG = Object.freeze({
    saved_views: { key: "pokemon-go-collection:saved-views:v1", version: 1, expected: "small" },
    goals: { key: "pokemon-go-collection:goals:v1", version: 1, expected: "small" },
    goal_exclusions: { key: "pokemon-go-collection:goal-exclusions:v1", version: 1, expected: "small" },
    annotations: { key: "pokemon-go-collection:annotations:v2", version: 2, expected: "medium" },
    enrichment: { key: "pokemon-go-collection:enrichment:v1", version: 1, expected: "medium" },
    columns: { key: "pokemon-go-collection:columns:v1", version: 1, expected: "tiny" },
    planner_budget: { key: "pokemon-go-collection:planner-budget:v1", version: 1, expected: "tiny" },
  });

  function checksum(text) {
    let hash = 0x811c9dc5;
    for (const char of String(text || "")) {
      hash ^= char.charCodeAt(0);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return hash.toString(16).padStart(8, "0");
  }

  function emptyMeta() {
    return { version: META_VERSION, last_backup_at: "", namespaces: {} };
  }

  function loadMeta(storage) {
    try {
      const parsed = JSON.parse(storage?.getItem(META_KEY) || "null");
      if (!parsed || Number(parsed.version) !== META_VERSION || typeof parsed.namespaces !== "object") return emptyMeta();
      return { ...emptyMeta(), ...parsed, namespaces: { ...(parsed.namespaces || {}) } };
    } catch {
      return emptyMeta();
    }
  }

  function saveMeta(storage, meta) {
    try {
      storage?.setItem(META_KEY, JSON.stringify(meta));
      return true;
    } catch {
      return false;
    }
  }

  function isObject(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }

  function validateNamespace(name, value) {
    if (name === "saved_views") return isObject(value) && Number(value.version) === 1 && Array.isArray(value.views);
    if (name === "goals") return isObject(value) && Number(value.version) === 1 && Array.isArray(value.goals);
    if (name === "goal_exclusions") return isObject(value) && Number(value.version) === 1 && isObject(value.by_goal);
    if (name === "annotations") return isObject(value) && Number(value.version) === 2 && isObject(value.records) && Array.isArray(value.unresolved);
    if (name === "enrichment") return isObject(value) && Number(value.version) === 1 && isObject(value.records) && (!value.unresolved || Array.isArray(value.unresolved));
    if (name === "columns") return Array.isArray(value) && value.every((item) => typeof item === "string");
    if (name === "planner_budget") return isObject(value) && Object.values(value).every((item) => typeof item !== "number" || Number.isFinite(item));
    return false;
  }

  function parseRaw(name, raw) {
    try {
      const value = JSON.parse(raw);
      if (!validateNamespace(name, value)) return { ok: false, reason: "schema", value: null };
      return { ok: true, reason: "", value };
    } catch {
      return { ok: false, reason: "parse", value: null };
    }
  }

  function unresolvedCount(value) {
    return Array.isArray(value?.unresolved) ? value.unresolved.length : 0;
  }

  function scanNamespaces(storage, { updateSnapshots = true } = {}) {
    const meta = loadMeta(storage);
    const namespaces = [];
    let metaChanged = false;
    for (const [name, spec] of Object.entries(CATALOG)) {
      let raw = null;
      let readError = "";
      try { raw = storage?.getItem(spec.key); } catch (error) { readError = String(error?.message || error); }
      const saved = meta.namespaces[name] || {};
      if (readError) {
        namespaces.push({ name, storage_key: spec.key, schema_version: spec.version, status: "unreadable", recoverable: Boolean(saved.lkg), bytes: null, unresolved: null, detail: readError });
        continue;
      }
      if (raw == null || raw === "") {
        namespaces.push({ name, storage_key: spec.key, schema_version: spec.version, status: "empty", recoverable: Boolean(saved.lkg), bytes: 0, unresolved: 0, detail: "No local value stored." });
        continue;
      }
      const parsed = parseRaw(name, raw);
      if (!parsed.ok) {
        const lkg = saved.lkg ? parseRaw(name, saved.lkg) : { ok: false };
        namespaces.push({ name, storage_key: spec.key, schema_version: spec.version, status: "corrupt", recoverable: Boolean(lkg.ok), bytes: raw.length * 2, unresolved: null, detail: parsed.reason === "parse" ? "JSON cannot be parsed." : "Stored value does not match the supported schema." });
        continue;
      }
      const digest = checksum(raw);
      const integrityChanged = Boolean(saved.checksum && saved.checksum !== digest);
      if (updateSnapshots && (saved.checksum !== digest || saved.lkg !== raw)) {
        meta.namespaces[name] = { checksum: digest, schema_version: spec.version, lkg: raw, updated_at: new Date().toISOString() };
        metaChanged = true;
      }
      const unresolved = unresolvedCount(parsed.value);
      namespaces.push({
        name,
        storage_key: spec.key,
        schema_version: spec.version,
        status: unresolved ? "attention" : "healthy",
        recoverable: true,
        bytes: raw.length * 2,
        unresolved,
        integrity_changed: integrityChanged,
        detail: unresolved ? `${unresolved} unresolved or ambiguous mapping(s) retained for review.` : "Readable and schema-compatible.",
      });
    }
    if (metaChanged) saveMeta(storage, meta);
    return { namespaces, last_backup_at: meta.last_backup_at || "", metadata_saved: !metaChanged || saveMeta(storage, meta) };
  }

  function recoverNamespace(storage, name) {
    const spec = CATALOG[name];
    if (!spec) return { ok: false, error: "Unknown namespace." };
    const meta = loadMeta(storage);
    const saved = meta.namespaces[name];
    if (!saved?.lkg) return { ok: false, error: "No last-known-good snapshot is available." };
    const parsed = parseRaw(name, saved.lkg);
    if (!parsed.ok) return { ok: false, error: "The recovery snapshot is no longer valid." };
    let previous = null;
    try {
      previous = storage?.getItem(spec.key) ?? null;
      storage?.setItem(spec.key, saved.lkg);
      const roundTrip = storage?.getItem(spec.key);
      if (roundTrip !== saved.lkg) throw new Error("Storage read-back verification failed");
      return { ok: true };
    } catch (error) {
      try {
        if (previous === null) storage?.removeItem(spec.key);
        else storage?.setItem(spec.key, previous);
      } catch { /* best-effort rollback */ }
      return { ok: false, error: String(error?.message || error) };
    }
  }

  function probeWrite(storage) {
    const key = `${META_KEY}:probe`;
    try {
      storage?.setItem(key, "ok");
      if (storage?.getItem(key) !== "ok") throw new Error("Storage read-back failed");
      storage?.removeItem(key);
      return { ok: true, error: "" };
    } catch (error) {
      try { storage?.removeItem(key); } catch { /* no-op */ }
      return { ok: false, error: String(error?.message || error) };
    }
  }

  function markBackup(storage, timestamp = new Date().toISOString()) {
    const meta = loadMeta(storage);
    meta.last_backup_at = String(timestamp);
    return saveMeta(storage, meta);
  }

  async function storageManagerStatus(navigatorObject) {
    const storageManager = navigatorObject?.storage;
    const result = { supported: Boolean(storageManager), persisted: null, persistence_request_supported: false, usage: null, quota: null };
    if (!storageManager) return result;
    if (typeof storageManager.persisted === "function") {
      try { result.persisted = await storageManager.persisted(); } catch { result.persisted = null; }
    }
    result.persistence_request_supported = typeof storageManager.persist === "function";
    if (typeof storageManager.estimate === "function") {
      try {
        const estimate = await storageManager.estimate();
        result.usage = Number.isFinite(estimate?.usage) ? estimate.usage : null;
        result.quota = Number.isFinite(estimate?.quota) ? estimate.quota : null;
      } catch { /* uncertainty is represented as null */ }
    }
    return result;
  }

  async function requestPersistence(navigatorObject) {
    if (typeof navigatorObject?.storage?.persist !== "function") return { supported: false, granted: null };
    try { return { supported: true, granted: Boolean(await navigatorObject.storage.persist()) }; }
    catch (error) { return { supported: true, granted: null, error: String(error?.message || error) }; }
  }

  async function healthReport(root, { updateSnapshots = true } = {}) {
    const scan = scanNamespaces(root?.localStorage, { updateSnapshots });
    const manager = await storageManagerStatus(root?.navigator);
    const write = probeWrite(root?.localStorage);
    const corrupt = scan.namespaces.filter((item) => ["corrupt", "unreadable"].includes(item.status)).length;
    const attention = scan.namespaces.filter((item) => item.status === "attention").length;
    return {
      state: !write.ok || corrupt ? "needs-attention" : attention || manager.persisted === false ? "limited" : "healthy",
      write,
      storage_manager: manager,
      last_backup_at: scan.last_backup_at,
      namespaces: scan.namespaces,
      local_only: true,
    };
  }

  return {
    META_KEY, META_VERSION, CATALOG,
    checksum, validateNamespace, parseRaw, scanNamespaces, recoverNamespace,
    probeWrite, markBackup, storageManagerStatus, requestPersistence, healthReport,
  };
});
