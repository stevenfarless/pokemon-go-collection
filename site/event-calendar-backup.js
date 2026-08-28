"use strict";

(function exposeEventCalendarBackup(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionEventCalendarBackup = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const EVENT_KEY = "pokemon-go-collection:event-calendar:v1";
  const EVENT_NAMESPACE = "event_calendar";
  const EVENT_SCHEMA_VERSION = 1;
  const SCOPES = new Set(["now", "today", "next7", "later", "history"]);

  function validateEventCalendarState(data) {
    if (!data || Number(data.version) !== EVENT_SCHEMA_VERSION) throw new Error("Event Calendar state must use schema version 1.");
    const selectedScope = String(data.selected_scope || "now");
    if (!SCOPES.has(selectedScope)) throw new Error("Event Calendar contains an unsupported agenda scope.");
    if (!Array.isArray(data.reminders)) throw new Error("Event Calendar reminders must be an array.");
    const ids = new Set();
    const reminders = data.reminders.map((item) => {
      const id = String(item?.id || "").trim();
      const title = String(item?.title || "").trim();
      const at = String(item?.at || "").trim();
      if (!id || ids.has(id)) throw new Error("Event Calendar reminder IDs must be unique and non-empty.");
      if (!title || title.length > 120) throw new Error("Event Calendar reminder titles must be 1-120 characters.");
      if (!Number.isFinite(Date.parse(at))) throw new Error("Event Calendar reminder timestamps must be valid ISO-compatible dates.");
      if (typeof item.done !== "boolean") throw new Error("Event Calendar reminder completion state must be boolean.");
      ids.add(id);
      return { id, title, at: new Date(at).toISOString(), done: item.done };
    });
    reminders.sort((a, b) => Date.parse(a.at) - Date.parse(b.at) || a.id.localeCompare(b.id));
    return { version: EVENT_SCHEMA_VERSION, selected_scope: selectedScope, reminders };
  }

  function buildUnifiedBackupWithEvent(baseApi, localApi, tradeApi, storage) {
    if (!baseApi?.buildUnifiedBackupWithStorageSearch) throw new Error("Storage/Search unified backup extension is unavailable.");
    const backup = baseApi.buildUnifiedBackupWithStorageSearch(localApi, tradeApi, storage);
    const raw = storage?.getItem(EVENT_KEY);
    backup.namespaces = { ...(backup.namespaces || {}) };
    backup.namespaces[EVENT_NAMESPACE] = {
      storage_key: EVENT_KEY,
      schema_version: EVENT_SCHEMA_VERSION,
      present: raw !== null && raw !== undefined && raw !== "",
      data: raw !== null && raw !== undefined && raw !== "" ? validateEventCalendarState(JSON.parse(raw)) : null,
    };
    return backup;
  }

  function withoutEvent(raw) {
    const copy = { ...raw, namespaces: { ...(raw?.namespaces || {}) } };
    delete copy.namespaces[EVENT_NAMESPACE];
    return copy;
  }

  function validateUnifiedBackupWithEvent(baseApi, localApi, tradeApi, raw, storage, records = []) {
    if (!baseApi?.validateUnifiedBackupWithStorageSearch) throw new Error("Storage/Search unified backup validation extension is unavailable.");
    const base = baseApi.validateUnifiedBackupWithStorageSearch(localApi, tradeApi, withoutEvent(raw), storage, records);
    const envelope = { ...base.envelope, namespaces: { ...(base.envelope?.namespaces || {}) } };
    const preview = {
      added: [...(base.preview?.added || [])],
      replaced: [...(base.preview?.replaced || [])],
      absent: [...(base.preview?.absent || [])],
      ignored: [...(base.preview?.ignored || [])],
    };
    const entry = raw?.namespaces?.[EVENT_NAMESPACE];
    if (entry) {
      if (entry.storage_key !== EVENT_KEY || Number(entry.schema_version) !== EVENT_SCHEMA_VERSION) throw new Error("Namespace event_calendar has incompatible metadata.");
      if (!entry.present) {
        envelope.namespaces[EVENT_NAMESPACE] = { ...entry, data: null };
        preview.absent.push(EVENT_NAMESPACE);
      } else {
        const data = validateEventCalendarState(entry.data);
        envelope.namespaces[EVENT_NAMESPACE] = { ...entry, data };
        if (storage?.getItem(EVENT_KEY) == null) preview.added.push(EVENT_NAMESPACE);
        else preview.replaced.push(EVENT_NAMESPACE);
      }
    }
    return { envelope, preview };
  }

  function knownKeys(localApi, tradeApi, baseApi) {
    const keys = new Set(Object.values(localApi?.STORAGE_KEYS || {}));
    if (tradeApi?.RESOURCE_KEY) keys.add(tradeApi.RESOURCE_KEY);
    for (const metadata of Object.values(baseApi?.NAMESPACES || {})) if (metadata?.storage_key) keys.add(metadata.storage_key);
    keys.add(EVENT_KEY);
    return keys;
  }

  function snapshot(storage, keys) {
    const result = new Map();
    for (const key of keys) result.set(key, storage?.getItem(key) ?? null);
    return result;
  }

  function rollback(storage, before) {
    for (const [key, value] of before.entries()) {
      try {
        if (value === null) storage?.removeItem(key);
        else storage?.setItem(key, value);
      } catch { /* best-effort rollback */ }
    }
  }

  function restoreUnifiedBackupWithEvent(baseApi, localApi, tradeApi, storage, raw, records = []) {
    const validated = validateUnifiedBackupWithEvent(baseApi, localApi, tradeApi, raw, storage, records);
    const before = snapshot(storage, knownKeys(localApi, tradeApi, baseApi));
    try {
      baseApi.restoreUnifiedBackupWithStorageSearch(localApi, tradeApi, storage, withoutEvent(raw), records);
      const entry = validated.envelope.namespaces[EVENT_NAMESPACE];
      if (entry?.present) storage?.setItem(EVENT_KEY, JSON.stringify(entry.data));
      return validated.preview;
    } catch (error) {
      rollback(storage, before);
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
    if (!root.document?.getElementById("local-data-backup") || !root.CollectionLocalData || !root.CollectionStorageSearchBackup) return;
    const status = root.document.getElementById("local-data-preview");
    let pending = null;
    const recordsPromise = root.fetch("data/pokemon.json")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error(`data/pokemon.json returned HTTP ${response.status}`)))
      .then((payload) => payload.records || []).catch(() => []);

    root.document.addEventListener("click", async (event) => {
      const id = event.target?.id;
      if (id === "export-local-data") {
        event.preventDefault();
        event.stopImmediatePropagation();
        try {
          const backup = buildUnifiedBackupWithEvent(root.CollectionStorageSearchBackup, root.CollectionLocalData, root.CollectionTradeResourceLabs, root.localStorage);
          downloadJson(root, "pokemon-go-collection-local-data.json", backup);
          if (status) status.textContent = "Unified backup exported, including Event Calendar reminders when present.";
        } catch (error) {
          if (status) status.textContent = `Backup export failed: ${error.message || error}`;
        }
      } else if (id === "apply-local-data-restore") {
        if (!pending) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        try {
          const records = await recordsPromise;
          const preview = restoreUnifiedBackupWithEvent(root.CollectionStorageSearchBackup, root.CollectionLocalData, root.CollectionTradeResourceLabs, root.localStorage, pending, records);
          pending = null;
          event.target.disabled = true;
          if (status) status.textContent = `Restore applied atomically. Added: ${preview.added.join(", ") || "none"}. Replaced: ${preview.replaced.join(", ") || "none"}. Event Calendar reminders are included when present.`;
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
        const { preview } = validateUnifiedBackupWithEvent(root.CollectionStorageSearchBackup, root.CollectionLocalData, root.CollectionTradeResourceLabs, pending, root.localStorage, records);
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
    EVENT_KEY,
    EVENT_NAMESPACE,
    EVENT_SCHEMA_VERSION,
    validateEventCalendarState,
    buildUnifiedBackupWithEvent,
    validateUnifiedBackupWithEvent,
    restoreUnifiedBackupWithEvent,
    install,
  };
});
