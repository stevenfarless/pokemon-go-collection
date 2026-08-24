"use strict";

(function exposePlayerLabs(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionPlayerLabs = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const STORAGE = Object.freeze({
    naming_presets: { key: "pokemon-go-collection:naming-presets:v1", version: 1 },
    gap_goals: { key: "pokemon-go-collection:gap-goals:v1", version: 1 },
    roster_locks: { key: "pokemon-go-collection:roster-locks:v1", version: 1 },
    elite_tm_vault: { key: "pokemon-go-collection:elite-tm-vault:v1", version: 1 },
  });
  const ENRICHMENT_KEY = "pokemon-go-collection:enrichment:v1";
  const BRIDGE_MARK = Symbol("player-labs-backup-bridge");

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  function safeJson(raw, fallback) {
    try { return JSON.parse(raw); } catch { return fallback; }
  }

  function unicodeLength(value) {
    return Array.from(String(value ?? "")).length;
  }

  function fixedWidth(value, width, fallback = "?") {
    if (value === null || value === undefined || value === "" || !Number.isFinite(Number(value))) return fallback.repeat(width).slice(0, width);
    return String(Math.round(Number(value))).padStart(width, "0").slice(-width);
  }

  function abbreviateMove(value, width = 3) {
    const text = String(value || "").normalize("NFKD").replace(/[^A-Za-z0-9 ]/g, " ").trim();
    if (!text) return "";
    const words = text.split(/\s+/).filter(Boolean);
    const initials = words.map((word) => word[0]).join("").toUpperCase();
    if (initials.length >= 2) return initials.slice(0, width);
    return text.replace(/\s+/g, "").slice(0, width).toUpperCase();
  }

  function loadObject(storage, key, fallback) {
    return safeJson(storage?.getItem(key), fallback);
  }

  function saveObject(storage, key, value) {
    storage?.setItem(key, JSON.stringify(value));
    return value;
  }

  function validateNamingPresets(value) {
    if (!value || Number(value.version) !== 1 || !Array.isArray(value.presets) || !Array.isArray(value.verified_symbols || [])) throw new Error("Naming presets require schema version 1.");
    const ids = new Set();
    for (const preset of value.presets) {
      const id = String(preset?.id || "").trim();
      if (!id || ids.has(id)) throw new Error("Naming presets contain a blank or duplicate ID.");
      if (!String(preset?.name || "").trim() || typeof preset?.template !== "string") throw new Error(`Naming preset ${id} is incomplete.`);
      ids.add(id);
    }
    return value;
  }

  function validateGapGoals(value) {
    if (!value || Number(value.version) !== 1 || !Array.isArray(value.exclusions) || typeof value.goals !== "object" || Array.isArray(value.goals)) throw new Error("Gap goals require schema version 1.");
    value.exclusions = [...new Set(value.exclusions.map(Number).filter(Number.isFinite))];
    return value;
  }

  function validateRosterLocks(value) {
    if (!value || Number(value.version) !== 1 || typeof value.by_type !== "object" || Array.isArray(value.by_type)) throw new Error("Roster locks require schema version 1.");
    for (const [type, ids] of Object.entries(value.by_type)) {
      if (!Array.isArray(ids)) throw new Error(`Roster locks for ${type} must be an array.`);
      value.by_type[type] = [...new Set(ids.map(String).filter(Boolean))];
    }
    return value;
  }

  function validateEliteTmVault(value) {
    if (!value || Number(value.version) !== 1 || !Array.isArray(value.entries)) throw new Error("Elite TM Vault requires schema version 1.");
    const ids = new Set();
    for (const entry of value.entries) {
      const id = String(entry?.id || "");
      if (!id || ids.has(id) || !String(entry?.record_id || "") || !String(entry?.desired_move || "").trim()) throw new Error("Elite TM Vault contains an incomplete or duplicate entry.");
      ids.add(id);
    }
    return value;
  }

  function validateLabNamespace(name, value) {
    if (name === "naming_presets") return validateNamingPresets(value);
    if (name === "gap_goals") return validateGapGoals(value);
    if (name === "roster_locks") return validateRosterLocks(value);
    if (name === "elite_tm_vault") return validateEliteTmVault(value);
    throw new Error(`Unknown player-lab namespace ${name}.`);
  }

  function defaultLabState(name) {
    if (name === "naming_presets") return { version: 1, presets: [], verified_symbols: [] };
    if (name === "gap_goals") return { version: 1, exclusions: [], goals: {} };
    if (name === "roster_locks") return { version: 1, by_type: {} };
    if (name === "elite_tm_vault") return { version: 1, entries: [] };
    throw new Error(`Unknown namespace ${name}.`);
  }

  function loadLabState(storage, name) {
    const spec = STORAGE[name];
    if (!spec) throw new Error(`Unknown namespace ${name}.`);
    const raw = loadObject(storage, spec.key, defaultLabState(name));
    try { return validateLabNamespace(name, raw); } catch { return defaultLabState(name); }
  }

  function saveLabState(storage, name, value) {
    const normalized = validateLabNamespace(name, value);
    return saveObject(storage, STORAGE[name].key, normalized);
  }

  function loadEnrichment(storage) {
    const value = loadObject(storage, ENRICHMENT_KEY, { version: 1, records: {} });
    return value && typeof value.records === "object" ? value : { version: 1, records: {} };
  }

  function enrichmentFor(storage, recordId) {
    return loadEnrichment(storage).records?.[String(recordId)] || {};
  }

  function namingTokens(record, enrichment = {}) {
    const ivs = record?.ivs || {};
    const pvp = record?.pvp || {};
    const level = record?.level || {};
    const state = String(record?.status?.shadow_purified || "normal");
    const stateMarker = state === "shadow" ? "S" : state === "purified" ? "P" : "";
    const maxMarker = enrichment.gigantamax === "yes" ? "G" : enrichment.dynamax === "yes" ? "D" : "";
    const review = enrichment.reserved_trade === "yes" ? "T" : record?.status?.favorite ? "K" : "";
    const legacy = enrichment.legacy_move_review === "yes" ? "L" : "";
    const league = (name) => pvp?.[name] || {};
    const pct = (name) => league(name).rank_percent == null ? "" : fixedWidth(league(name).rank_percent, 3);
    const rank = (name) => league(name).rank_number == null ? "" : fixedWidth(league(name).rank_number, 4);
    let levelText = "";
    if (level.minimum != null && level.maximum != null) levelText = Number(level.minimum) === Number(level.maximum) ? String(level.minimum) : `${level.minimum}-${level.maximum}`;
    else if (level.minimum != null) levelText = String(level.minimum);
    else if (level.maximum != null) levelText = String(level.maximum);
    return {
      iv45: record?.naming?.iv45 || fixedWidth(ivs.total, 2),
      ivpct3: record?.naming?.ivpct3 || fixedWidth(ivs.average_percent, 3),
      iv1000: record?.naming?.iv1000 || (ivs.average_percent == null ? "????" : fixedWidth(Number(ivs.average_percent) * 10, 4)),
      atk: ivs.attack == null ? "?" : String(ivs.attack), def: ivs.defense == null ? "?" : String(ivs.defense), hp: ivs.stamina == null ? "?" : String(ivs.stamina),
      great: pct("great"), greatRank: rank("great"), ultra: pct("ultra"), ultraRank: rank("ultra"), little: pct("little"), littleRank: rank("little"),
      level: levelText, fast: abbreviateMove(record?.moves?.fast), charged: abbreviateMove(record?.moves?.charged), state: stateMarker, max: maxMarker, review, legacy,
    };
  }

  function renderTemplate(template, record, enrichment = {}, characterLimit = 12) {
    const tokens = namingTokens(record, enrichment);
    const unknown = [];
    const text = String(template || "").replace(/\{([A-Za-z0-9]+)\}/g, (match, key) => {
      if (!Object.prototype.hasOwnProperty.call(tokens, key)) { unknown.push(key); return match; }
      return tokens[key];
    });
    const length = unicodeLength(text);
    return { text, length, limit: Number(characterLimit || 12), overLimit: length > Number(characterLimit || 12), unknownTokens: [...new Set(unknown)], tokens };
  }

  function extendUnifiedBackup(base, storage) {
    const output = JSON.parse(JSON.stringify(base || {}));
    output.namespaces = output.namespaces || {};
    for (const [name, spec] of Object.entries(STORAGE)) {
      const raw = storage?.getItem(spec.key);
      output.namespaces[name] = {
        storage_key: spec.key, schema_version: spec.version, present: raw !== null,
        data: raw === null ? null : validateLabNamespace(name, JSON.parse(raw)),
      };
    }
    output.extensions = { ...(output.extensions || {}), player_labs: { schema_version: 1, namespaces: Object.keys(STORAGE) } };
    return output;
  }

  function validateLabBackup(raw, storage) {
    const namespaces = raw?.namespaces || {};
    const normalized = {}, preview = { added: [], replaced: [], absent: [] };
    for (const [name, spec] of Object.entries(STORAGE)) {
      const entry = namespaces[name];
      if (!entry) { preview.absent.push(name); continue; }
      if (entry.storage_key !== spec.key || Number(entry.schema_version) !== spec.version) throw new Error(`Lab namespace ${name} has incompatible metadata.`);
      if (!entry.present) { preview.absent.push(name); continue; }
      normalized[name] = validateLabNamespace(name, entry.data);
      if (storage?.getItem(spec.key) == null) preview.added.push(name); else preview.replaced.push(name);
    }
    return { normalized, preview };
  }

  function atomicRestore(root, raw, records = []) {
    const Local = root.CollectionLocalData;
    if (!Local?.validateUnifiedBackup || !Local?.restoreUnifiedBackup) throw new Error("Base local-data restore tools are unavailable.");
    Local.validateUnifiedBackup(raw, root.localStorage, records);
    const labs = validateLabBackup(raw, root.localStorage);
    const allKeys = [...Object.values(Local.STORAGE_KEYS || {}), ...Object.values(STORAGE).map((item) => item.key)];
    const before = new Map(allKeys.map((key) => [key, root.localStorage.getItem(key)]));
    try {
      const basePreview = Local.restoreUnifiedBackup(root.localStorage, raw, records);
      for (const [name, value] of Object.entries(labs.normalized)) root.localStorage.setItem(STORAGE[name].key, JSON.stringify(value));
      return { base: basePreview, labs: labs.preview };
    } catch (error) {
      for (const [key, value] of before.entries()) {
        try { if (value === null) root.localStorage.removeItem(key); else root.localStorage.setItem(key, value); } catch { /* best effort */ }
      }
      throw error;
    }
  }

  function downloadJson(root, filename, payload) {
    const blob = new root.Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
    const url = root.URL.createObjectURL(blob);
    const anchor = root.document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click(); root.URL.revokeObjectURL(url);
  }

  function readFile(root, file) {
    if (typeof file?.text === "function") return file.text().then((text) => JSON.parse(text));
    return new Promise((resolve, reject) => {
      const reader = new root.FileReader();
      reader.onload = () => { try { resolve(JSON.parse(String(reader.result || ""))); } catch (error) { reject(error); } };
      reader.onerror = () => reject(reader.error || new Error("File read failed"));
      reader.readAsText(file);
    });
  }

  function installBackupBridge(root) {
    const documentObject = root.document;
    const exportButton = documentObject.getElementById("export-local-data");
    const restoreInput = documentObject.getElementById("restore-local-data");
    const applyButton = documentObject.getElementById("apply-local-data-restore");
    if (!exportButton || !restoreInput || !applyButton || documentObject[BRIDGE_MARK]) return false;
    documentObject[BRIDGE_MARK] = true;
    let pending = null, records = [];
    const previewTarget = documentObject.getElementById("local-data-preview");
    root.fetch("data/pokemon.json").then((response) => response.ok ? response.json() : null).then((payload) => { records = payload?.records || []; }).catch(() => {});

    documentObject.addEventListener("click", (event) => {
      const button = event.target?.closest?.("#export-local-data");
      if (!button) return;
      event.preventDefault(); event.stopImmediatePropagation();
      const Local = root.CollectionLocalData;
      if (!Local?.buildUnifiedBackup) return;
      const payload = extendUnifiedBackup(Local.buildUnifiedBackup(root.localStorage), root.localStorage);
      downloadJson(root, "pokemon-go-collection-local-data.json", payload);
      root.CollectionStorageHealth?.markBackup?.(root.localStorage);
    }, true);

    documentObject.addEventListener("change", async (event) => {
      if (event.target !== restoreInput) return;
      event.preventDefault(); event.stopImmediatePropagation();
      try {
        const file = restoreInput.files?.[0]; if (!file) return;
        const raw = await readFile(root, file);
        const Local = root.CollectionLocalData;
        const base = Local.validateUnifiedBackup(raw, root.localStorage, records).preview;
        const labs = validateLabBackup(raw, root.localStorage).preview;
        pending = raw; applyButton.disabled = false;
        if (previewTarget) previewTarget.textContent = `Restore preview: base add ${base.added.join(", ") || "none"}, replace ${base.replaced.join(", ") || "none"}; labs add ${labs.added.join(", ") || "none"}, replace ${labs.replaced.join(", ") || "none"}. No local data has changed yet.`;
      } catch (error) {
        pending = null; applyButton.disabled = true;
        if (previewTarget) previewTarget.textContent = `Restore validation failed: ${error.message || error}`;
      }
    }, true);

    documentObject.addEventListener("click", (event) => {
      const button = event.target?.closest?.("#apply-local-data-restore");
      if (!button || !pending) return;
      event.preventDefault(); event.stopImmediatePropagation();
      try {
        const result = atomicRestore(root, pending, records);
        pending = null; applyButton.disabled = true;
        const labNames = [...result.labs.added, ...result.labs.replaced];
        if (previewTarget) previewTarget.textContent = `Restore applied atomically, including player-lab state: ${labNames.join(", ") || "no lab namespaces present"}. Reload this page to apply restored preferences.`;
      } catch (error) {
        if (previewTarget) previewTarget.textContent = `Restore failed without accepting partial local state: ${error.message || error}`;
      }
    }, true);
    return true;
  }

  async function fetchJson(root, path) {
    const response = await root.fetch(path);
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return response.json();
  }

  function recordLabel(record) {
    const iv = record?.ivs?.average_percent == null ? "? IV" : `${Number(record.ivs.average_percent).toFixed(1)}%`;
    return `#${record?.pokemon_number ?? "?"} ${record?.name || "Unknown"}${record?.form ? ` · ${record.form}` : ""} · CP ${record?.cp ?? "?"} · ${iv}`;
  }

  function optionHtml(record) {
    return `<option value="${escapeHtml(record.record_id)}">${escapeHtml(recordLabel(record))}</option>`;
  }

  function copy(root, text, status) {
    if (!root.navigator?.clipboard?.writeText) { if (status) status.textContent = "Clipboard API unavailable. Select and copy the preview manually."; return; }
    root.navigator.clipboard.writeText(text).then(() => { if (status) status.textContent = "Copied exact preview. Paste and verify it in Pokémon GO."; }).catch(() => { if (status) status.textContent = "Copy failed. Select the preview manually."; });
  }

  function seedNamingState(storage, defaults) {
    let state = loadLabState(storage, "naming_presets");
    if (!state.presets.length) {
      state = { ...state, presets: (defaults || []).map((item) => ({ id: item.id, name: item.name, template: item.template })) };
      saveLabState(storage, "naming_presets", state);
    }
    return state;
  }

  async function renderNaming(root) {
    const mount = root.document.getElementById("naming-studio-root"); if (!mount) return false;
    const data = await fetchJson(root, "data/naming-studio.json");
    let state = seedNamingState(root.localStorage, data.default_presets);
    mount.innerHTML = `<section class="lab-controls ds-card"><label>Exact owned record<select id="naming-record">${data.records.map(optionHtml).join("")}</select></label><label>Preset<select id="naming-preset"></select></label><label>Template<input id="naming-template" type="text" autocomplete="off"></label><div class="lab-actions"><button id="save-naming-preset" type="button">Save preset</button><button id="copy-nickname" type="button">Copy preview</button></div><p id="naming-status" class="lab-status"></p></section><section class="ds-card"><h2>Exact preview</h2><output id="nickname-preview" class="nickname-preview"></output><p id="nickname-count"></p><details><summary>Field and sorting contract</summary><pre class="lab-pre">${escapeHtml(JSON.stringify(data.fixed_width_contract, null, 2))}</pre></details></section><section class="ds-card"><h2>Paste-tested symbols</h2><p>The built-in palette is conservative ASCII. Add a symbol only after you paste-test it on your own device. Browser support is not proof that Pokémon GO accepts or renders it.</p><div class="lab-inline"><input id="symbol-test" maxlength="8" aria-label="Paste-tested symbol"><button id="add-symbol" type="button">Mark as tested</button></div><p id="symbol-palette"></p></section><section class="ds-card"><h2>Batch preview</h2><p>Preview only. This does not rename, control, or automate Pokémon GO.</p><button id="batch-preview" type="button">Preview first 25 records</button><div id="batch-results"></div></section>`;
    const recordSelect = root.document.getElementById("naming-record"), presetSelect = root.document.getElementById("naming-preset"), template = root.document.getElementById("naming-template");
    const preview = root.document.getElementById("nickname-preview"), count = root.document.getElementById("nickname-count"), status = root.document.getElementById("naming-status"), palette = root.document.getElementById("symbol-palette");
    const currentRecord = () => data.records.find((item) => item.record_id === recordSelect.value) || data.records[0];
    function refreshPresets(selected) {
      presetSelect.innerHTML = state.presets.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("");
      if (selected && state.presets.some((item) => item.id === selected)) presetSelect.value = selected;
      const preset = state.presets.find((item) => item.id === presetSelect.value) || state.presets[0];
      if (preset) template.value = preset.template;
    }
    function refreshPalette() { palette.textContent = [...data.verified_symbol_palette.symbols, ...state.verified_symbols].join("  ") || "No tested symbols."; }
    function refresh() {
      const result = renderTemplate(template.value, currentRecord(), enrichmentFor(root.localStorage, currentRecord()?.record_id), data.character_limit);
      preview.textContent = result.text || "(empty)";
      count.textContent = `${result.length}/${result.limit} Unicode code points${result.overLimit ? " · TOO LONG" : ""}${result.unknownTokens.length ? ` · unknown tokens: ${result.unknownTokens.join(", ")}` : ""}.`;
      count.dataset.state = result.overLimit ? "danger" : "success";
    }
    refreshPresets(); refreshPalette(); refresh();
    presetSelect.addEventListener("change", () => { const preset = state.presets.find((item) => item.id === presetSelect.value); if (preset) template.value = preset.template; refresh(); });
    recordSelect.addEventListener("change", refresh); template.addEventListener("input", refresh);
    root.document.getElementById("copy-nickname").addEventListener("click", () => copy(root, preview.textContent === "(empty)" ? "" : preview.textContent, status));
    root.document.getElementById("save-naming-preset").addEventListener("click", () => {
      const id = presetSelect.value || `custom-${Date.now()}`; const index = state.presets.findIndex((item) => item.id === id);
      const name = index >= 0 ? state.presets[index].name : "Custom"; const item = { id, name, template: template.value };
      if (index >= 0) state.presets[index] = item; else state.presets.push(item);
      saveLabState(root.localStorage, "naming_presets", state); refreshPresets(id); refresh(); status.textContent = "Preset saved locally and included in unified local-data backup.";
    });
    root.document.getElementById("add-symbol").addEventListener("click", () => {
      const field = root.document.getElementById("symbol-test"); const chars = Array.from(String(field.value || "").trim());
      for (const char of chars) if (!state.verified_symbols.includes(char) && !data.verified_symbol_palette.symbols.includes(char)) state.verified_symbols.push(char);
      saveLabState(root.localStorage, "naming_presets", state); field.value = ""; refreshPalette();
    });
    root.document.getElementById("batch-preview").addEventListener("click", () => {
      const results = root.document.getElementById("batch-results");
      results.innerHTML = `<ol>${data.records.slice(0, 25).map((record) => { const value = renderTemplate(template.value, record, enrichmentFor(root.localStorage, record.record_id), data.character_limit); return `<li><code>${escapeHtml(value.text)}</code> · ${value.length}/${value.limit} · ${escapeHtml(recordLabel(record))}</li>`; }).join("")}</ol>`;
    });
    return true;
  }

  async function renderGaps(root) {
    const mount = root.document.getElementById("gap-radar-root"); if (!mount) return false;
    const data = await fetchJson(root, "data/gap-radar.json");
    let state = loadLabState(root.localStorage, "gap_goals");
    mount.innerHTML = `<section class="lab-controls ds-card"><label>View<select id="gap-mode"><option value="list">List</option><option value="matrix">Matrix</option></select></label><label>Filter<select id="gap-filter"><option value="all">All</option><option value="missing">Missing</option><option value="actionable">Actionable now</option><option value="almost">Almost complete via owned family</option></select></label><p id="gap-summary"></p></section><section id="gap-results" class="lab-grid"></section><section class="ds-card"><h2>Collector-state support</h2><p>${escapeHtml(data.unknown_policy)}</p><pre class="lab-pre">${escapeHtml(JSON.stringify(data.attribute_support, null, 2))}</pre></section>`;
    const results = root.document.getElementById("gap-results"), summary = root.document.getElementById("gap-summary"), mode = root.document.getElementById("gap-mode"), filter = root.document.getElementById("gap-filter");
    function render() {
      const excluded = new Set(state.exclusions.map(Number));
      const eligible = data.species.filter((item) => !excluded.has(Number(item.dex)));
      let rows = eligible;
      if (filter.value === "missing") rows = rows.filter((item) => item.species_state === "missing");
      if (filter.value === "actionable") rows = rows.filter((item) => item.species_state === "missing" && item.actionable_now);
      if (filter.value === "almost") rows = rows.filter((item) => item.species_state === "missing" && (item.family_fill_record_ids || []).length);
      const owned = eligible.filter((item) => item.species_state === "yes").length;
      summary.textContent = `Effective Living Dex denominator: ${eligible.length} after ${excluded.size} local exclusion(s). Owned: ${owned}. Snapshot denominator before local exclusions: ${data.denominators.species}.`;
      results.className = mode.value === "matrix" ? "lab-grid gap-matrix" : "lab-list";
      results.innerHTML = rows.map((item) => `<article class="ds-card gap-card" data-state="${escapeHtml(item.species_state)}"><h3>#${String(item.dex).padStart(4, "0")} ${escapeHtml(item.name)}</h3><p><strong>${item.species_state === "yes" ? "Owned" : "Missing"}</strong>${item.actionable_now && item.species_state === "missing" ? " · Actionable evidence available" : ""}</p><p>Owned exact records: ${(item.owned_record_ids || []).length}. Family fill candidates: ${(item.family_fill_record_ids || []).length}. Fresh opportunity facts: ${(item.current_opportunities || []).length}.</p><p><a href="${escapeHtml(item.links.reference)}">Species reference</a> · <a href="${escapeHtml(item.links.evolution)}">Evolution Lab</a> · <a href="${escapeHtml(item.links.trade)}">Trade workflow</a></p><button type="button" data-gap-exclude="${item.dex}">${excluded.has(Number(item.dex)) ? "Include in denominator" : "Exclude from my goal"}</button></article>`).join("") || `<p class="ds-empty">No gaps match this filter.</p>`;
      results.querySelectorAll("[data-gap-exclude]").forEach((button) => button.addEventListener("click", () => {
        const dex = Number(button.dataset.gapExclude); const set = new Set(state.exclusions.map(Number)); if (set.has(dex)) set.delete(dex); else set.add(dex);
        state.exclusions = [...set].sort((a, b) => a - b); saveLabState(root.localStorage, "gap_goals", state); render();
      }));
    }
    mode.addEventListener("change", render); filter.addEventListener("change", render); render(); return true;
  }

  async function renderRoster(root) {
    const mount = root.document.getElementById("roster-readiness-root"); if (!mount) return false;
    const data = await fetchJson(root, "data/roster-readiness.json"); let locks = loadLabState(root.localStorage, "roster_locks");
    mount.innerHTML = `<section class="ds-card"><h2>Weakest links</h2><p>${data.weakest.map((item) => `${item.type}: ${item.best_score ?? "unavailable"} (${item.viable_count} usable)`).join(" · ")}</p><p>${escapeHtml(data.scoring.formula)} This score is not a raid simulation.</p><p>Current boss overlay: <strong>${escapeHtml(data.current_matchup_layer.state)}</strong>. ${escapeHtml(data.current_matchup_layer.reason)}</p></section><section id="roster-grid" class="lab-grid roster-grid"></section>`;
    const grid = root.document.getElementById("roster-grid");
    function render() {
      grid.innerHTML = data.types.map((item) => {
        const locked = new Set(locks.by_type[item.type] || []);
        return `<article class="ds-card roster-card"><h3>${escapeHtml(item.type.toUpperCase())}</h3><p>${escapeHtml(item.text_summary)}</p><details open><summary>Show my six</summary><ol>${(item.candidates || []).map((candidate) => `<li><strong>${escapeHtml(candidate.name)}</strong> · CP ${candidate.cp ?? "?"} · score ${candidate.score ?? "?"} · confidence ${escapeHtml(candidate.confidence_label)}${candidate.missing?.length ? ` · missing ${escapeHtml(candidate.missing.join(", "))}` : ""}${candidate.improvement_cost ? ` · known scoped cost ${candidate.improvement_cost.stardust} dust + ${candidate.improvement_cost.regular_candy} candy (${escapeHtml(candidate.improvement_cost.scope)})` : ""} <button type="button" data-lock-type="${escapeHtml(item.type)}" data-lock-id="${escapeHtml(candidate.record_id)}">${locked.has(candidate.record_id) ? "Unlock" : "Lock"}</button></li>`).join("") || "<li>No supported exact owned candidate.</li>"}</ol></details></article>`;
      }).join("");
      grid.querySelectorAll("[data-lock-id]").forEach((button) => button.addEventListener("click", () => {
        const type = button.dataset.lockType, id = button.dataset.lockId; const set = new Set(locks.by_type[type] || []); if (set.has(id)) set.delete(id); else set.add(id);
        locks.by_type[type] = [...set]; saveLabState(root.localStorage, "roster_locks", locks); render();
      }));
    }
    render(); return true;
  }

  function branchHtml(branch) {
    if (branch.state === "unknown-target") return `<li>Unknown target ${escapeHtml(branch.species_id)}. No projection.</li>`;
    const req = branch.requirements || {}, cp = branch.cp_projection || {};
    return `<li><strong>${escapeHtml(branch.name)}</strong> · requirements ${escapeHtml(req.state)}${req.candy != null ? ` · ${req.candy} candy` : ""}${req.special ? ` · special ${escapeHtml(JSON.stringify(req.special))}` : ""} · CP ${cp.state === "projected" ? cp.cp : `blocked (${escapeHtml(cp.reason || "unknown")})`}${cp.league_cap_warnings?.length ? ` · ${escapeHtml(cp.league_cap_warnings.join(" "))}` : ""} · <a href="${escapeHtml(branch.reference || "#")}">reference</a></li>`;
  }

  async function renderEvolution(root) {
    const mount = root.document.getElementById("evolution-lab-root"); if (!mount) return false;
    const data = await fetchJson(root, "data/evolution-lab.json");
    mount.innerHTML = `<section class="lab-controls ds-card"><label>Exact owned record<select id="evolution-record">${data.records.filter((item) => item.record_id).map(optionHtml).join("")}</select></label></section><section id="evolution-result" class="ds-card"></section>`;
    const select = root.document.getElementById("evolution-record"), result = root.document.getElementById("evolution-result");
    function render() {
      const item = data.records.find((record) => record.record_id === select.value) || data.records[0]; if (!item) return;
      const enrichment = enrichmentFor(root.localStorage, item.record_id);
      const gmaxKnown = enrichment.gigantamax === "yes";
      const officialBlock = Boolean(item.restriction_policy?.official_no_evolve_rule && gmaxKnown);
      result.innerHTML = `<h2>${escapeHtml(item.name || "Unknown")} evolution review</h2><p>Status: <strong>${escapeHtml(item.state)}</strong>. Decision: <strong>${escapeHtml(officialBlock ? "blocked by reviewed Max rule" : item.decision?.state || "unknown")}</strong>.</p>${gmaxKnown ? `<p class="ds-notice" data-kind="warning">Local enrichment says Gigantamax. ${officialBlock ? "A reviewed no-evolve rule applies." : "No no-evolve rule is inferred from this local state alone."}</p>` : ""}<ul>${(item.branches || []).map(branchHtml).join("") || "<li>No supported evolution branch in the pinned knowledge snapshot.</li>"}</ul><p>Current exclusive-move window: <strong>${escapeHtml(item.current_exclusive_move_window?.state)}</strong>. Fresh explicit evidence count: ${(item.current_exclusive_move_window?.evidence || []).length}.</p><p>${escapeHtml((item.decision?.reasons || []).join(" "))}</p><p><a href="${escapeHtml(item.links?.decision_card || "#")}">Decision card</a> · <a href="${escapeHtml(item.links?.gap_radar || "#")}">Gap Radar</a> · <a href="${escapeHtml(item.links?.action_pack || "#")}">Evolution Action Pack</a></p>`;
    }
    select.addEventListener("change", render); render(); return true;
  }

  async function renderMoves(root) {
    const mount = root.document.getElementById("move-lab-root"); if (!mount) return false;
    const data = await fetchJson(root, "data/move-lab.json"); let vault = loadLabState(root.localStorage, "elite_tm_vault");
    const available = data.records.filter((item) => item.record_id);
    mount.innerHTML = `<section class="lab-controls ds-card"><label>Exact owned record<select id="move-record">${available.map(optionHtml).join("")}</select></label></section><section id="move-result" class="ds-card"></section><section class="ds-card"><h2>Elite TM Vault</h2><p>Local planning queue only. It does not infer your Elite TM count or spend anything.</p><label>Desired move<input id="vault-move" type="text"></label><label>Why<textarea id="vault-why"></textarea></label><label>Wait/event alternative<textarea id="vault-wait"></textarea></label><button id="vault-add" type="button">Add exact record to vault</button><div id="vault-list"></div></section>`;
    const select = root.document.getElementById("move-record"), result = root.document.getElementById("move-result"), vaultList = root.document.getElementById("vault-list");
    function current() { return available.find((item) => item.record_id === select.value) || available[0]; }
    function renderRecord() {
      const item = current(); if (!item) return;
      result.innerHTML = `<h2>${escapeHtml(item.name)} move review</h2><p>Known moves: ${escapeHtml([item.known_moves.fast, item.known_moves.charged, item.known_moves.charged_second].filter(Boolean).join(" / ") || "unknown")}</p><p>Stable learnable pool is versioned reference only, not current TM/event availability. Current acquisition: <strong>${escapeHtml(item.current_acquisition.state)}</strong>, explicit fresh evidence ${(item.current_acquisition.evidence || []).length}.</p><details><summary>Stable move pool</summary><pre class="lab-pre">${escapeHtml(JSON.stringify(item.stable_move_pool, null, 2))}</pre></details><p>Frustration: <strong>${escapeHtml(item.frustration.state)}</strong>${item.frustration.current_removal_allowed ? " · fresh removal window verified" : ""}.</p><p>${escapeHtml(item.purification.permanent_tradeoff)}</p><p>Elite TM: <strong>${escapeHtml(item.elite_tm.spend_recommendation)}</strong>. ${escapeHtml(item.elite_tm.opportunity_cost)} Owned alternatives: ${(item.elite_tm.owned_alternative_record_ids || []).length}.</p><p><a href="${escapeHtml(item.action_pack)}">Open exact Move Action Pack</a></p>`;
    }
    function renderVault() {
      vaultList.innerHTML = vault.entries.length ? `<ol>${vault.entries.map((entry) => `<li><strong>${escapeHtml(entry.desired_move)}</strong> for <code>${escapeHtml(entry.record_id)}</code> · ${escapeHtml(entry.why || "No rationale entered")} · wait alternative: ${escapeHtml(entry.wait_alternative || "none entered")} · freshness at save: ${escapeHtml(entry.freshness || "unknown")} <button type="button" data-vault-remove="${escapeHtml(entry.id)}">Remove</button></li>`).join("")}</ol>` : `<p class="ds-empty">No local Elite TM plans.</p>`;
      vaultList.querySelectorAll("[data-vault-remove]").forEach((button) => button.addEventListener("click", () => { vault.entries = vault.entries.filter((item) => item.id !== button.dataset.vaultRemove); saveLabState(root.localStorage, "elite_tm_vault", vault); renderVault(); }));
    }
    root.document.getElementById("vault-add").addEventListener("click", () => {
      const item = current(), desired = String(root.document.getElementById("vault-move").value || "").trim(); if (!item || !desired) return;
      vault.entries.push({ id: `etm-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, record_id: item.record_id, desired_move: desired, why: String(root.document.getElementById("vault-why").value || "").trim(), wait_alternative: String(root.document.getElementById("vault-wait").value || "").trim(), freshness: item.current_acquisition.state, alternatives: item.elite_tm.owned_alternative_record_ids || [], action_pack: item.action_pack });
      saveLabState(root.localStorage, "elite_tm_vault", vault); renderVault();
    });
    select.addEventListener("change", renderRecord); renderRecord(); renderVault(); return true;
  }

  async function install(root) {
    installBackupBridge(root);
    try {
      if (await renderNaming(root)) return;
      if (await renderGaps(root)) return;
      if (await renderRoster(root)) return;
      if (await renderEvolution(root)) return;
      await renderMoves(root);
    } catch (error) {
      const mount = root.document.querySelector("#naming-studio-root,#gap-radar-root,#roster-readiness-root,#evolution-lab-root,#move-lab-root");
      if (mount) mount.innerHTML = `<p class="ds-notice" data-kind="danger">Player lab unavailable: ${escapeHtml(error.message || error)}</p>`;
    }
  }

  return {
    STORAGE, unicodeLength, fixedWidth, abbreviateMove, validateNamingPresets, validateGapGoals, validateRosterLocks, validateEliteTmVault,
    validateLabNamespace, defaultLabState, loadLabState, saveLabState, namingTokens, renderTemplate,
    extendUnifiedBackup, validateLabBackup, atomicRestore, installBackupBridge, install,
  };
});
