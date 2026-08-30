"use strict";

(function exposeStorageSearchBackup(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionStorageSearchBackup = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const SEARCH_TEMPLATES_KEY = "pokemon-go-collection:search-templates:v1";
  const CLEANUP_KEY = "pokemon-go-collection:storage-cleanup:v1";
  const FRIENDSHIP_TRADE_KEY = "pokemon-go-collection:friendship-trade-state:v1";
  const NAMESPACES = Object.freeze({
    search_templates: { storage_key: SEARCH_TEMPLATES_KEY, schema_version: 1 },
    storage_cleanup: { storage_key: CLEANUP_KEY, schema_version: 1 },
    friendship_trade_state: { storage_key: FRIENDSHIP_TRADE_KEY, schema_version: 1 },
  });

  function validateSearchTemplates(data) {
    if (!data || Number(data.version) !== 1 || !Array.isArray(data.templates)) throw new Error("Search templates must use schema version 1.");
    const names = new Set();
    const templates = [];
    for (const item of data.templates) {
      const name = String(item?.name || "").trim();
      const expression = String(item?.expression || "").trim();
      const key = name.toLocaleLowerCase();
      if (!name || !expression || names.has(key)) throw new Error("Search templates contain a blank field or duplicate name.");
      names.add(key);
      templates.push({ name, expression, updated_at: String(item?.updated_at || "") });
    }
    return { version: 1, templates };
  }

  function validateCleanupState(data) {
    if (!data || Number(data.version) !== 1 || !data.decisions || typeof data.decisions !== "object" || Array.isArray(data.decisions)) throw new Error("Storage Cleanup state must use schema version 1.");
    const decisions = {};
    for (const [id, value] of Object.entries(data.decisions)) {
      if (!String(id) || !["review", "approve", "exclude"].includes(String(value))) throw new Error("Storage Cleanup contains an invalid record decision.");
      decisions[String(id)] = String(value);
    }
    const config = data.config === undefined ? {} : data.config;
    if (!config || typeof config !== "object" || Array.isArray(config)) throw new Error("Storage Cleanup config must be an object.");
    return { version: 1, decisions, config: { ...config } };
  }

  function validateFriendshipTradeState(data) {
    if (!data || Number(data.version) !== 1 || !Array.isArray(data.friends)) throw new Error("Friendship/Trade state must use schema version 1.");
    if (data.friends.length > 500) throw new Error("Friendship/Trade state exceeds the supported friend limit.");
    const seen = new Set();
    for (const friend of data.friends) {
      if (!friend || typeof friend !== "object" || Array.isArray(friend)) throw new Error("Friendship/Trade state contains an invalid friend record.");
      const id = String(friend.id || "").trim();
      if (!id || seen.has(id)) throw new Error("Friendship/Trade state contains a blank or duplicate friend id.");
      seen.add(id);
      for (const field of ["wishes", "offers", "reservations"]) {
        if (friend[field] !== undefined && !Array.isArray(friend[field])) throw new Error(`Friendship/Trade ${field} must be a list.`);
      }
    }
    return { ...data, version: 1, friends: data.friends.map((friend) => ({ ...friend })) };
  }

  function validator(name, data) {
    if (name === "search_templates") return validateSearchTemplates(data);
    if (name === "storage_cleanup") return validateCleanupState(data);
    if (name === "friendship_trade_state") return validateFriendshipTradeState(data);
    throw new Error(`Unknown storage/search backup namespace ${name}.`);
  }

  function baseBuild(localApi, tradeApi, storage) {
    if (tradeApi?.buildUnifiedBackupWithVault) return tradeApi.buildUnifiedBackupWithVault(localApi, storage);
    if (localApi?.buildUnifiedBackup) return localApi.buildUnifiedBackup(storage);
    throw new Error("Unified local-data backup engine is unavailable.");
  }

  function buildUnifiedBackupWithStorageSearch(localApi, tradeApi, storage) {
    const backup = baseBuild(localApi, tradeApi, storage);
    backup.namespaces = { ...(backup.namespaces || {}) };
    for (const [name, metadata] of Object.entries(NAMESPACES)) {
      const raw = storage?.getItem(metadata.storage_key);
      backup.namespaces[name] = {
        storage_key: metadata.storage_key,
        schema_version: metadata.schema_version,
        present: raw !== null && raw !== undefined && raw !== "",
        data: raw !== null && raw !== undefined && raw !== "" ? JSON.parse(raw) : null,
      };
    }
    return backup;
  }

  function withoutStorageSearch(raw) {
    const copy = { ...raw, namespaces: { ...(raw?.namespaces || {}) } };
    for (const name of Object.keys(NAMESPACES)) delete copy.namespaces[name];
    return copy;
  }

  function baseValidate(localApi, tradeApi, raw, storage, records) {
    if (tradeApi?.validateUnifiedBackupWithVault) return tradeApi.validateUnifiedBackupWithVault(localApi, raw, storage, records);
    if (localApi?.validateUnifiedBackup) return localApi.validateUnifiedBackup(raw, storage, records);
    throw new Error("Unified local-data validation engine is unavailable.");
  }

  function validateUnifiedBackupWithStorageSearch(localApi, tradeApi, raw, storage, records = []) {
    const base = baseValidate(localApi, tradeApi, withoutStorageSearch(raw), storage, records);
    const envelope = { ...base.envelope, namespaces: { ...(base.envelope?.namespaces || {}) } };
    const preview = {
      added: [...(base.preview?.added || [])],
      replaced: [...(base.preview?.replaced || [])],
      absent: [...(base.preview?.absent || [])],
      ignored: [...(base.preview?.ignored || [])],
    };
    for (const [name, metadata] of Object.entries(NAMESPACES)) {
      const entry = raw?.namespaces?.[name];
      if (!entry) continue;
      if (entry.storage_key !== metadata.storage_key || Number(entry.schema_version) !== metadata.schema_version) throw new Error(`Namespace ${name} has incompatible metadata.`);
      if (!entry.present) {
        envelope.namespaces[name] = { ...entry, data: null };
        preview.absent.push(name);
        continue;
      }
      const data = validator(name, entry.data);
      envelope.namespaces[name] = { ...entry, data };
      if (storage?.getItem(metadata.storage_key) == null) preview.added.push(name);
      else preview.replaced.push(name);
    }
    return { envelope, preview };
  }

  function snapshotKnownStorage(localApi, tradeApi, storage) {
    const keys = new Set(Object.values(localApi?.STORAGE_KEYS || {}));
    if (tradeApi?.RESOURCE_KEY) keys.add(tradeApi.RESOURCE_KEY);
    for (const metadata of Object.values(NAMESPACES)) keys.add(metadata.storage_key);
    const snapshot = new Map();
    for (const key of keys) snapshot.set(key, storage?.getItem(key) ?? null);
    return snapshot;
  }

  function rollbackStorage(storage, snapshot) {
    for (const [key, value] of snapshot.entries()) {
      try {
        if (value === null) storage?.removeItem(key);
        else storage?.setItem(key, value);
      } catch { /* Best-effort rollback for a failing storage implementation. */ }
    }
  }

  function baseRestore(localApi, tradeApi, storage, raw, records) {
    if (tradeApi?.restoreUnifiedBackupWithVault) return tradeApi.restoreUnifiedBackupWithVault(localApi, storage, raw, records);
    if (localApi?.restoreUnifiedBackup) return localApi.restoreUnifiedBackup(storage, raw, records);
    throw new Error("Unified local-data restore engine is unavailable.");
  }

  function restoreUnifiedBackupWithStorageSearch(localApi, tradeApi, storage, raw, records = []) {
    const validated = validateUnifiedBackupWithStorageSearch(localApi, tradeApi, raw, storage, records);
    const before = snapshotKnownStorage(localApi, tradeApi, storage);
    try {
      baseRestore(localApi, tradeApi, storage, withoutStorageSearch(raw), records);
      for (const [name, metadata] of Object.entries(NAMESPACES)) {
        const entry = validated.envelope.namespaces[name];
        if (!entry?.present) continue;
        storage?.setItem(metadata.storage_key, JSON.stringify(entry.data));
      }
      return validated.preview;
    } catch (error) {
      rollbackStorage(storage, before);
      throw new Error(`Restore failed; previous local state was restored where storage allowed it: ${error.message || error}`);
    }
  }

  function downloadJson(root, filename, payload) {
    const blob = new root.Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
    const url = root.URL.createObjectURL(blob);
    const anchor = root.document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    root.URL.revokeObjectURL(url);
  }

  function install(root) {
    if (!root.document?.getElementById("local-data-backup") || !root.CollectionLocalData) return;
    const status = root.document.getElementById("local-data-preview");
    let pending = null;
    const recordsPromise = root.fetch("data/pokemon.json").then((response) => response.ok ? response.json() : Promise.reject(new Error(`data/pokemon.json returned HTTP ${response.status}`))).then((payload) => payload.records || []).catch(() => []);

    root.document.addEventListener("click", async (event) => {
      const id = event.target?.id;
      if (id === "export-local-data") {
        event.preventDefault();
        event.stopImmediatePropagation();
        try {
          const backup = buildUnifiedBackupWithStorageSearch(root.CollectionLocalData, root.CollectionTradeResourceLabs, root.localStorage);
          downloadJson(root, "pokemon-go-collection-local-data.json", backup);
          if (status) status.textContent = "Unified backup exported, including Resource Vault, Search Builder templates, Storage Cleanup review state, and Friendship/Trade planning state when present.";
        } catch (error) {
          if (status) status.textContent = `Backup export failed: ${error.message || error}`;
        }
      } else if (id === "apply-local-data-restore") {
        if (!pending) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        try {
          const records = await recordsPromise;
          const preview = restoreUnifiedBackupWithStorageSearch(root.CollectionLocalData, root.CollectionTradeResourceLabs, root.localStorage, pending, records);
          pending = null;
          event.target.disabled = true;
          if (status) status.textContent = `Restore applied atomically. Added: ${preview.added.join(", ") || "none"}. Replaced: ${preview.replaced.join(", ") || "none"}. Resource Vault, search templates, cleanup review state, and Friendship/Trade planning state are included when present.`;
        } catch (error) {
          if (status) status.textContent = `Restore failed without accepting partial local state: ${error.message || error}`;
        }
      }
    }, true);

    root.document.addEventListener("change", async (event) => {
      if (event.target?.id !== "restore-local-data") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      try {
        const file = event.target.files?.[0];
        if (!file) return;
        pending = JSON.parse(await file.text());
        const records = await recordsPromise;
        const { preview } = validateUnifiedBackupWithStorageSearch(root.CollectionLocalData, root.CollectionTradeResourceLabs, pending, root.localStorage, records);
        const apply = root.document.getElementById("apply-local-data-restore");
        if (apply) apply.disabled = false;
        if (status) status.textContent = `Restore preview: add ${preview.added.join(", ") || "none"}; replace ${preview.replaced.join(", ") || "none"}; absent ${preview.absent.join(", ") || "none"}; ignore ${preview.ignored.join(", ") || "none"}. No local data has changed yet.`;
      } catch (error) {
        pending = null;
        const apply = root.document.getElementById("apply-local-data-restore");
        if (apply) apply.disabled = true;
        if (status) status.textContent = `Restore validation failed: ${error.message || error}`;
      }
    }, true);
  }

  return {
    SEARCH_TEMPLATES_KEY, CLEANUP_KEY, FRIENDSHIP_TRADE_KEY, NAMESPACES,
    validateSearchTemplates, validateCleanupState, validateFriendshipTradeState,
    buildUnifiedBackupWithStorageSearch, validateUnifiedBackupWithStorageSearch, restoreUnifiedBackupWithStorageSearch,
    install,
  };
});
