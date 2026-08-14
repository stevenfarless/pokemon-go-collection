"use strict";

(function exposeLocalData(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionLocalData = api;
  if (root?.document) {
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", () => api.install(root), { once: true });
    else api.install(root);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const ENRICHMENT_KEY = "pokemon-go-collection:enrichment:v1";
  const ENRICHMENT_VERSION = 1;
  const ENRICHMENT_BACKUP_PRODUCT = "pokemon-go-collection-local-enrichment";
  const UNIFIED_BACKUP_PRODUCT = "pokemon-go-collection-local-data";
  const UNIFIED_BACKUP_VERSION = 1;
  const TRI_STATES = Object.freeze(["unknown", "yes", "no"]);
  const TRI_FIELDS = Object.freeze([
    "shiny", "costume", "background", "dynamax", "gigantamax",
    "reserved_trade", "already_traded", "legacy_move_review",
  ]);
  const TEXT_FIELDS = Object.freeze(["costume_label", "background_note", "trade_note", "origin_note"]);
  const STORAGE_KEYS = Object.freeze({
    saved_views: "pokemon-go-collection:saved-views:v1",
    goals: "pokemon-go-collection:goals:v1",
    goal_exclusions: "pokemon-go-collection:goal-exclusions:v1",
    annotations: "pokemon-go-collection:annotations:v2",
    enrichment: ENRICHMENT_KEY,
    columns: "pokemon-go-collection:columns:v1",
    planner_budget: "pokemon-go-collection:planner-budget:v1",
  });
  const ALLOWED_COLUMNS = new Set(["pokemon", "cp", "iv", "level", "moves", "status", "pvp", "dates"]);

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  const recordId = (record) => String(record?.identity?.record_id || record?.record_id || "");
  const normalizeText = (value, limit = 500) => String(value ?? "").trim().slice(0, limit);
  const tri = (value) => TRI_STATES.includes(String(value)) ? String(value) : "unknown";

  function compatibility(record) {
    return {
      pokemon_number: Number(record?.pokemon_number || 0),
      name: String(record?.name || ""),
      form: String(record?.form || ""),
      gender: String(record?.gender || ""),
      original_scan: String(record?.dates?.original_scan || ""),
      catch_date: String(record?.dates?.catch || ""),
    };
  }

  function compatibilityMatches(expected, record) {
    if (!expected || typeof expected !== "object") return false;
    const actual = compatibility(record);
    const keys = ["pokemon_number", "name", "form", "gender", "original_scan", "catch_date"];
    return keys.every((key) => String(expected[key] ?? "") === String(actual[key] ?? ""));
  }

  function blankEnrichmentEntry() {
    return {
      shiny: "unknown",
      costume: "unknown",
      costume_label: "",
      background: "unknown",
      background_note: "",
      dynamax: "unknown",
      gigantamax: "unknown",
      reserved_trade: "unknown",
      already_traded: "unknown",
      trade_note: "",
      origin_note: "",
      legacy_move_review: "unknown",
      compatibility: null,
      provenance: {},
      updated_at: "",
    };
  }

  function blankEnrichmentPayload() {
    return { version: ENRICHMENT_VERSION, records: {}, unresolved: [] };
  }

  function sanitizeEnrichment(raw) {
    const output = blankEnrichmentEntry();
    for (const field of TRI_FIELDS) output[field] = tri(raw?.[field]);
    output.costume_label = normalizeText(raw?.costume_label, 120);
    output.background_note = normalizeText(raw?.background_note, 300);
    output.trade_note = normalizeText(raw?.trade_note, 300);
    output.origin_note = normalizeText(raw?.origin_note, 300);
    output.compatibility = raw?.compatibility && typeof raw.compatibility === "object" ? { ...raw.compatibility } : null;
    output.updated_at = String(raw?.updated_at || "");
    const provenance = {};
    if (raw?.provenance && typeof raw.provenance === "object" && !Array.isArray(raw.provenance)) {
      for (const [field, value] of Object.entries(raw.provenance)) {
        if (![...TRI_FIELDS, ...TEXT_FIELDS].includes(field) || !value || typeof value !== "object") continue;
        provenance[field] = {
          source: String(value.source || "user-confirmed"),
          updated_at: String(value.updated_at || output.updated_at || ""),
        };
      }
    }
    output.provenance = provenance;
    return output;
  }

  function hasMeaningfulEnrichment(entry) {
    const value = sanitizeEnrichment(entry);
    return TRI_FIELDS.some((field) => value[field] !== "unknown") || TEXT_FIELDS.some((field) => Boolean(value[field]));
  }

  function migrateEnrichment(raw, records = []) {
    if (!raw || typeof raw !== "object") return null;
    const version = Number(raw.version ?? raw.schema_version ?? ENRICHMENT_VERSION);
    if (version !== ENRICHMENT_VERSION || !raw.records || typeof raw.records !== "object" || Array.isArray(raw.records)) return null;
    const output = blankEnrichmentPayload();
    const byId = new Map((records || []).map((record) => [recordId(record), record]).filter(([id]) => id));
    for (const [oldId, rawEntry] of Object.entries(raw.records)) {
      const entry = sanitizeEnrichment(rawEntry);
      if (byId.has(oldId)) {
        output.records[oldId] = entry;
        continue;
      }
      const matches = (records || []).filter((record) => compatibilityMatches(entry.compatibility, record));
      if (matches.length === 1) {
        output.records[recordId(matches[0])] = entry;
      } else {
        output.unresolved.push({
          old_record_id: String(oldId),
          reason: matches.length > 1 ? "ambiguous-compatibility-match" : "record-not-found",
          candidate_record_ids: matches.map(recordId),
          enrichment: entry,
        });
      }
    }
    for (const item of Array.isArray(raw.unresolved) ? raw.unresolved : []) output.unresolved.push({ ...item });
    return output;
  }

  function loadEnrichment(storage, records = []) {
    try {
      const raw = storage?.getItem(ENRICHMENT_KEY);
      if (!raw) return blankEnrichmentPayload();
      return migrateEnrichment(JSON.parse(raw), records) || blankEnrichmentPayload();
    } catch {
      return blankEnrichmentPayload();
    }
  }

  function saveEnrichment(storage, payload) {
    const migrated = migrateEnrichment(payload, []);
    if (!migrated) return false;
    try {
      storage?.setItem(ENRICHMENT_KEY, JSON.stringify(migrated));
      return true;
    } catch {
      return false;
    }
  }

  function setEnrichment(payload, record, rawEntry, updatedAt = new Date().toISOString()) {
    const next = migrateEnrichment(payload, [record]) || blankEnrichmentPayload();
    const id = recordId(record);
    if (!id) return next;
    const previous = sanitizeEnrichment(next.records[id]);
    const entry = sanitizeEnrichment(rawEntry);
    entry.compatibility = compatibility(record);
    entry.updated_at = String(updatedAt);
    for (const field of [...TRI_FIELDS, ...TEXT_FIELDS]) {
      if (entry[field] !== previous[field]) entry.provenance[field] = { source: "user-confirmed", updated_at: String(updatedAt) };
      else if (previous.provenance[field]) entry.provenance[field] = previous.provenance[field];
    }
    if (hasMeaningfulEnrichment(entry)) next.records[id] = entry;
    else delete next.records[id];
    return next;
  }

  function enrichmentForRecord(payload, record) {
    return sanitizeEnrichment(payload?.records?.[recordId(record)]);
  }

  function protectionReasons(entry) {
    const value = sanitizeEnrichment(entry);
    const reasons = [];
    if (value.shiny === "yes") reasons.push("user-confirmed shiny");
    if (value.costume === "yes") reasons.push("user-confirmed costume/event appearance");
    if (value.background === "yes") reasons.push("user-confirmed special/location/background");
    if (value.dynamax === "yes") reasons.push("user-confirmed Dynamax");
    if (value.gigantamax === "yes") reasons.push("user-confirmed Gigantamax");
    if (value.reserved_trade === "yes") reasons.push("reserved for trade");
    if (value.legacy_move_review === "yes") reasons.push("manual legacy/exclusive-move review flag");
    return reasons;
  }

  function augmentDuplicateGroups(groups, enrichment) {
    return (groups || []).map((group) => ({
      ...group,
      automatic_transfer_safe: false,
      records: (group.records || []).map((item) => {
        const id = String(item.record_id || recordId(item.record));
        const local = enrichment?.records?.[id];
        return { ...item, local_protection_reasons: protectionReasons(local) };
      }),
    }));
  }

  function filterRecordsByEnrichment(records, payload, field, state) {
    const wantedField = TRI_FIELDS.includes(field) ? field : "shiny";
    const wantedState = TRI_STATES.includes(state) ? state : "unknown";
    return (records || []).filter((record) => enrichmentForRecord(payload, record)[wantedField] === wantedState);
  }

  function enrichmentGoalCount(kind, records, payload) {
    const field = kind === "shiny" ? "shiny" : kind === "costume" ? "costume" : null;
    if (!field) return null;
    return (records || []).filter((record) => enrichmentForRecord(payload, record)[field] === "yes").length;
  }

  function enrichmentBackup(payload) {
    return {
      product: ENRICHMENT_BACKUP_PRODUCT,
      schema_version: ENRICHMENT_VERSION,
      exported_at: new Date().toISOString(),
      data: migrateEnrichment(payload, []) || blankEnrichmentPayload(),
    };
  }

  function enrichmentFromBackup(raw, records = []) {
    if (!raw || raw.product !== ENRICHMENT_BACKUP_PRODUCT || Number(raw.schema_version) !== ENRICHMENT_VERSION) return null;
    return migrateEnrichment(raw.data, records);
  }

  function parseStored(storage, key) {
    const text = storage?.getItem(key);
    if (text === null || text === undefined || text === "") return { present: false, data: null };
    return { present: true, data: JSON.parse(text) };
  }

  function validateSavedViews(data) {
    if (!data || Number(data.version) !== 1 || !Array.isArray(data.views)) throw new Error("Saved views must use schema version 1.");
    const names = new Set();
    for (const view of data.views) {
      const name = String(view?.name || "").trim();
      const query = String(view?.query || "");
      const key = name.toLocaleLowerCase();
      if (!name || names.has(key)) throw new Error("Saved views contain a blank or duplicate name.");
      if (query && !query.startsWith("?")) throw new Error(`Saved view ${name} has an invalid query state.`);
      if (view.columns !== undefined && !Array.isArray(view.columns)) throw new Error(`Saved view ${name} has invalid columns.`);
      names.add(key);
    }
    return data;
  }

  function validateGoals(data) {
    if (!data || Number(data.version) !== 1 || !Array.isArray(data.goals)) throw new Error("Goals must use schema version 1.");
    const ids = new Set();
    for (const goal of data.goals) {
      const id = String(goal?.id || "");
      if (!id || ids.has(id)) throw new Error("Goals contain a blank or duplicate ID.");
      if (!String(goal?.kind || "")) throw new Error(`Goal ${id} has no kind.`);
      ids.add(id);
    }
    return data;
  }

  function validateGoalExclusions(data) {
    if (!data || Number(data.version) !== 1 || !data.by_goal || typeof data.by_goal !== "object" || Array.isArray(data.by_goal)) throw new Error("Goal exclusions must use schema version 1.");
    for (const value of Object.values(data.by_goal)) if (!Array.isArray(value)) throw new Error("Goal exclusions must be arrays.");
    return data;
  }

  function validateAnnotations(data) {
    if (!data || Number(data.version) !== 2 || !data.records || typeof data.records !== "object" || Array.isArray(data.records)) throw new Error("Annotations must use schema version 2.");
    if (!Array.isArray(data.unresolved)) throw new Error("Annotations unresolved state must be an array.");
    return data;
  }

  function validateColumns(data) {
    if (!Array.isArray(data) || !data.every((value) => ALLOWED_COLUMNS.has(String(value)))) throw new Error("Column preferences contain an unsupported column.");
    if (new Set(data).size !== data.length) throw new Error("Column preferences contain duplicates.");
    return data;
  }

  function validateBudget(data) {
    if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("Planner budget must be an object.");
    for (const value of Object.values(data)) if (typeof value === "number" && !Number.isFinite(value)) throw new Error("Planner budget contains a non-finite number.");
    return data;
  }

  function namespaceValidator(name, data, records) {
    if (name === "saved_views") return validateSavedViews(data);
    if (name === "goals") return validateGoals(data);
    if (name === "goal_exclusions") return validateGoalExclusions(data);
    if (name === "annotations") return validateAnnotations(data);
    if (name === "enrichment") {
      const migrated = migrateEnrichment(data, records);
      if (!migrated) throw new Error("Enrichment must use schema version 1.");
      return migrated;
    }
    if (name === "columns") return validateColumns(data);
    if (name === "planner_budget") return validateBudget(data);
    throw new Error(`Unknown local-data namespace ${name}.`);
  }

  function namespaceSchemaVersion(name) {
    return name === "annotations" ? 2 : 1;
  }

  function buildUnifiedBackup(storage) {
    const namespaces = {};
    for (const [name, storageKey] of Object.entries(STORAGE_KEYS)) {
      const stored = parseStored(storage, storageKey);
      namespaces[name] = {
        storage_key: storageKey,
        schema_version: namespaceSchemaVersion(name),
        present: stored.present,
        data: stored.data,
      };
    }
    return {
      product: UNIFIED_BACKUP_PRODUCT,
      backup_version: UNIFIED_BACKUP_VERSION,
      exported_at: new Date().toISOString(),
      namespaces,
    };
  }

  function migrateBackupEnvelope(raw) {
    if (!raw || raw.product !== UNIFIED_BACKUP_PRODUCT) throw new Error("This file is not a Pokémon GO Collection local-data backup.");
    const version = Number(raw.backup_version);
    if (version > UNIFIED_BACKUP_VERSION) throw new Error(`Backup major version ${version} is newer than this site supports.`);
    if (version === UNIFIED_BACKUP_VERSION) return raw;
    if (version === 0 && raw.stores && typeof raw.stores === "object") {
      const namespaces = {};
      for (const [name, storageKey] of Object.entries(STORAGE_KEYS)) {
        const present = Object.prototype.hasOwnProperty.call(raw.stores, storageKey);
        namespaces[name] = { storage_key: storageKey, schema_version: namespaceSchemaVersion(name), present, data: present ? raw.stores[storageKey] : null };
      }
      return { product: UNIFIED_BACKUP_PRODUCT, backup_version: UNIFIED_BACKUP_VERSION, exported_at: raw.exported_at || "", namespaces };
    }
    throw new Error(`Unsupported backup version ${raw.backup_version}.`);
  }

  function validateUnifiedBackup(raw, storage, records = []) {
    const envelope = migrateBackupEnvelope(raw);
    if (!envelope.namespaces || typeof envelope.namespaces !== "object" || Array.isArray(envelope.namespaces)) throw new Error("Backup namespaces are missing or invalid.");
    const normalized = { ...envelope, namespaces: {} };
    const preview = { added: [], replaced: [], absent: [], ignored: [] };
    for (const [name, entry] of Object.entries(envelope.namespaces)) {
      if (!Object.prototype.hasOwnProperty.call(STORAGE_KEYS, name)) {
        preview.ignored.push(name);
        continue;
      }
      if (!entry || entry.storage_key !== STORAGE_KEYS[name] || Number(entry.schema_version) !== namespaceSchemaVersion(name)) throw new Error(`Namespace ${name} has incompatible metadata.`);
      if (!entry.present) {
        normalized.namespaces[name] = { ...entry, data: null };
        preview.absent.push(name);
        continue;
      }
      const data = namespaceValidator(name, entry.data, records);
      normalized.namespaces[name] = { ...entry, data };
      if (storage?.getItem(STORAGE_KEYS[name]) == null) preview.added.push(name);
      else preview.replaced.push(name);
    }
    return { envelope: normalized, preview };
  }

  function restoreUnifiedBackup(storage, raw, records = []) {
    const validated = validateUnifiedBackup(raw, storage, records);
    const before = new Map();
    const writes = [];
    for (const [name, entry] of Object.entries(validated.envelope.namespaces)) {
      if (!entry.present) continue;
      const key = STORAGE_KEYS[name];
      before.set(key, storage?.getItem(key) ?? null);
      writes.push([key, JSON.stringify(entry.data)]);
    }
    try {
      for (const [key, value] of writes) storage?.setItem(key, value);
    } catch (error) {
      for (const [key, previous] of before.entries()) {
        try {
          if (previous === null) storage?.removeItem(key);
          else storage?.setItem(key, previous);
        } catch { /* best-effort rollback of a failing storage implementation */ }
      }
      throw new Error(`Restore failed; previous local state was restored where storage allowed it: ${error.message || error}`);
    }
    return validated.preview;
  }

  async function fetchJson(root, path) {
    const response = await root.fetch(path);
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return response.json();
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

  function readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        try { resolve(JSON.parse(String(reader.result || ""))); } catch (error) { reject(error); }
      };
      reader.onerror = () => reject(reader.error || new Error("File read failed"));
      reader.readAsText(file);
    });
  }

  function optionLabel(record) {
    const iv = record?.ivs?.average_percent == null ? "? IV" : `${Number(record.ivs.average_percent).toFixed(1)}%`;
    return `#${record.pokemon_number} ${record.name}${record.form ? ` · ${record.form}` : ""} · CP ${record.cp ?? "?"} · ${iv} · ${recordId(record)}`;
  }

  function readEntryForm(documentObject) {
    const value = {};
    for (const field of TRI_FIELDS) value[field] = documentObject.getElementById(`enrichment-${field}`)?.value || "unknown";
    for (const field of TEXT_FIELDS) value[field] = documentObject.getElementById(`enrichment-${field.replaceAll("_", "-")}`)?.value || "";
    return value;
  }

  function fillEntryForm(documentObject, entry) {
    const value = sanitizeEnrichment(entry);
    for (const field of TRI_FIELDS) {
      const control = documentObject.getElementById(`enrichment-${field}`);
      if (control) control.value = value[field];
    }
    for (const field of TEXT_FIELDS) {
      const control = documentObject.getElementById(`enrichment-${field.replaceAll("_", "-")}`);
      if (control) control.value = value[field];
    }
  }

  function renderEnrichmentSummary(documentObject, records, payload, filterField, filterState) {
    const target = documentObject.getElementById("enrichment-results");
    if (!target) return;
    const filtered = filterRecordsByEnrichment(records, payload, filterField, filterState);
    const yesCounts = TRI_FIELDS.map((field) => `${field.replaceAll("_", " ")}: ${(records || []).filter((record) => enrichmentForRecord(payload, record)[field] === "yes").length}`);
    target.innerHTML = `<p><strong>${filtered.length.toLocaleString()}</strong> records are explicitly ${escapeHtml(filterState)} for <strong>${escapeHtml(filterField.replaceAll("_", " "))}</strong>.</p><p class="planner-note">${yesCounts.map(escapeHtml).join(" · ")}. Records with no local entry remain <strong>unknown</strong>, never false.</p><p class="planner-note">Unresolved migrations: ${(payload.unresolved || []).length}. Local enrichment can protect a record from review recommendations, but never makes another Pokémon automatically safe to transfer.</p>`;
  }

  function decorateProtectionSignals(documentObject, payload) {
    for (const containerId of ["duplicate-review-results", "trade-results"]) {
      const container = documentObject.getElementById(containerId);
      if (!container) continue;
      container.querySelectorAll("[data-local-enrichment-protection]").forEach((node) => node.remove());
      for (const [id, entry] of Object.entries(payload.records || {})) {
        const reasons = protectionReasons(entry);
        if (!reasons.length) continue;
        const candidates = [...container.querySelectorAll("small,code")].filter((node) => String(node.textContent || "").includes(id));
        for (const node of candidates) {
          const note = documentObject.createElement("span");
          note.dataset.localEnrichmentProtection = "true";
          note.className = "badge";
          note.textContent = `Local protection: ${reasons.join(", ")}`;
          node.parentElement?.append(note);
        }
      }
    }
  }

  function renderEnrichedGoals(root, records, payload) {
    const list = root.document.getElementById("goal-list");
    const Planning = root.CollectionPlanning;
    if (!list || !Planning?.loadGoals) return;
    list.querySelectorAll("[data-enrichment-goal-progress]").forEach((node) => node.remove());
    const goals = Planning.loadGoals(root.localStorage)?.goals || [];
    const cards = [...list.children];
    goals.forEach((goal, index) => {
      if (!["shiny", "costume"].includes(goal.kind) || !cards[index]) return;
      const count = enrichmentGoalCount(goal.kind, records, payload);
      const note = root.document.createElement("p");
      note.dataset.enrichmentGoalProgress = "true";
      note.className = "planner-note";
      note.textContent = `Browser-local enrichment progress: ${count}/${Number(goal.target || 1)} user-confirmed ${goal.kind} records. Unknown records are not counted.`;
      cards[index].append(note);
    });
  }

  async function install(root) {
    const documentObject = root.document;
    if (!documentObject?.getElementById("local-data-backup")) return;
    const status = documentObject.getElementById("local-data-status");
    try {
      const collection = await fetchJson(root, "data/pokemon.json");
      const records = collection.records || [];
      let payload = loadEnrichment(root.localStorage, records);
      saveEnrichment(root.localStorage, payload);
      const byId = new Map(records.map((record) => [recordId(record), record]));
      const select = documentObject.getElementById("enrichment-record");
      const filterField = documentObject.getElementById("enrichment-filter-field");
      const filterState = documentObject.getElementById("enrichment-filter-state");

      function refreshSelect() {
        const selected = select?.value;
        const list = filterRecordsByEnrichment(records, payload, filterField?.value || "shiny", filterState?.value || "unknown");
        if (select) {
          select.innerHTML = list.map((record) => `<option value="${escapeHtml(recordId(record))}">${escapeHtml(optionLabel(record))}</option>`).join("");
          if (selected && list.some((record) => recordId(record) === selected)) select.value = selected;
        }
        const record = byId.get(select?.value);
        fillEntryForm(documentObject, record ? enrichmentForRecord(payload, record) : blankEnrichmentEntry());
        renderEnrichmentSummary(documentObject, records, payload, filterField?.value || "shiny", filterState?.value || "unknown");
        decorateProtectionSignals(documentObject, payload);
        renderEnrichedGoals(root, records, payload);
      }

      select?.addEventListener("change", () => fillEntryForm(documentObject, enrichmentForRecord(payload, byId.get(select.value))));
      filterField?.addEventListener("change", refreshSelect);
      filterState?.addEventListener("change", refreshSelect);
      documentObject.getElementById("save-enrichment")?.addEventListener("click", () => {
        const record = byId.get(select?.value);
        if (!record) return;
        payload = setEnrichment(payload, record, readEntryForm(documentObject));
        saveEnrichment(root.localStorage, payload);
        refreshSelect();
      });
      documentObject.getElementById("clear-enrichment-record")?.addEventListener("click", () => {
        const id = select?.value;
        if (!id) return;
        delete payload.records[id];
        saveEnrichment(root.localStorage, payload);
        refreshSelect();
      });
      documentObject.getElementById("export-enrichment")?.addEventListener("click", () => downloadJson(root, "pokemon-go-local-enrichment.json", enrichmentBackup(payload)));
      documentObject.getElementById("import-enrichment")?.addEventListener("change", async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        const imported = enrichmentFromBackup(await readFile(file), records);
        if (!imported) throw new Error("Enrichment backup is invalid or unsupported.");
        payload = imported;
        saveEnrichment(root.localStorage, payload);
        event.target.value = "";
        refreshSelect();
      });
      documentObject.getElementById("clear-enrichment")?.addEventListener("click", () => {
        if (!root.confirm("Clear all browser-local enrichment on this browser? This does not change pokemon.json.")) return;
        payload = blankEnrichmentPayload();
        root.localStorage.removeItem(ENRICHMENT_KEY);
        refreshSelect();
      });

      const previewTarget = documentObject.getElementById("local-data-preview");
      let pendingBackup = null;
      documentObject.getElementById("export-local-data")?.addEventListener("click", () => downloadJson(root, "pokemon-go-collection-local-data.json", buildUnifiedBackup(root.localStorage)));
      documentObject.getElementById("restore-local-data")?.addEventListener("change", async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        pendingBackup = await readFile(file);
        const { preview } = validateUnifiedBackup(pendingBackup, root.localStorage, records);
        if (previewTarget) previewTarget.textContent = `Restore preview: add ${preview.added.join(", ") || "none"}; replace ${preview.replaced.join(", ") || "none"}; absent ${preview.absent.join(", ") || "none"}; ignore ${preview.ignored.join(", ") || "none"}. No local data has changed yet.`;
        const apply = documentObject.getElementById("apply-local-data-restore");
        if (apply) apply.disabled = false;
      });
      documentObject.getElementById("apply-local-data-restore")?.addEventListener("click", () => {
        if (!pendingBackup) return;
        const preview = restoreUnifiedBackup(root.localStorage, pendingBackup, records);
        payload = loadEnrichment(root.localStorage, records);
        pendingBackup = null;
        const apply = documentObject.getElementById("apply-local-data-restore");
        if (apply) apply.disabled = true;
        if (previewTarget) previewTarget.textContent = `Restore applied atomically. Added: ${preview.added.join(", ") || "none"}. Replaced: ${preview.replaced.join(", ") || "none"}. Reloading this page will apply restored view/goal preferences.`;
        refreshSelect();
      });

      const duplicate = documentObject.getElementById("duplicate-review-results");
      const trade = documentObject.getElementById("trade-results");
      const observer = new MutationObserver(() => decorateProtectionSignals(documentObject, payload));
      if (duplicate) observer.observe(duplicate, { childList: true, subtree: true });
      if (trade) observer.observe(trade, { childList: true, subtree: true });
      const goals = documentObject.getElementById("goal-list");
      if (goals) new MutationObserver(() => renderEnrichedGoals(root, records, payload)).observe(goals, { childList: true });

      refreshSelect();
      if (status) status.textContent = `Local enrichment and backup ready for ${records.length.toLocaleString()} canonical records.`;
    } catch (error) {
      if (status) status.textContent = `Local-data tools unavailable: ${error.message || error}`;
    }
  }

  return {
    ENRICHMENT_KEY, ENRICHMENT_VERSION, ENRICHMENT_BACKUP_PRODUCT,
    UNIFIED_BACKUP_PRODUCT, UNIFIED_BACKUP_VERSION, TRI_STATES, TRI_FIELDS, TEXT_FIELDS, STORAGE_KEYS,
    compatibility, compatibilityMatches, blankEnrichmentEntry, blankEnrichmentPayload,
    sanitizeEnrichment, migrateEnrichment, loadEnrichment, saveEnrichment, setEnrichment,
    enrichmentForRecord, protectionReasons, augmentDuplicateGroups, filterRecordsByEnrichment,
    enrichmentGoalCount, enrichmentBackup, enrichmentFromBackup,
    validateSavedViews, validateGoals, validateGoalExclusions, validateAnnotations, validateColumns,
    buildUnifiedBackup, migrateBackupEnvelope, validateUnifiedBackup, restoreUnifiedBackup, install,
  };
});
