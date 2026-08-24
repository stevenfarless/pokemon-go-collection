"use strict";

(function exposeAdvancedLabs(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionAdvancedLabs = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const STORAGE = Object.freeze({
    mega_state: { key: "pokemon-go-collection:mega-state:v1", version: 1 },
    max_state: { key: "pokemon-go-collection:max-state:v1", version: 1 },
    hyper_training: { key: "pokemon-go-collection:hyper-training:v1", version: 1 },
    buddy_queue: { key: "pokemon-go-collection:buddy-queue:v1", version: 1 },
    raid_assumptions: { key: "pokemon-go-collection:raid-assumptions:v1", version: 1 },
  });
  const BRIDGE_MARK = Symbol("advanced-labs-backup-bridge");
  const TRI = new Set(["unknown", "yes", "no"]);
  const MEGA_LEVELS = new Set(["unknown", "base", "high", "max", "super-max"]);
  const TYPES = new Set([
    "normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground",
    "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy",
  ]);

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  function safeJson(raw, fallback) {
    try { return JSON.parse(raw); } catch { return fallback; }
  }

  function loadObject(storage, key, fallback) {
    return safeJson(storage?.getItem(key), fallback);
  }

  function saveObject(storage, key, value) {
    storage?.setItem(key, JSON.stringify(value));
    return value;
  }

  function numberOrNull(value, { min = null, max = null, integer = false } = {}) {
    if (value === null || value === undefined || value === "") return null;
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || (integer && !Number.isInteger(parsed))) return null;
    if (min !== null && parsed < min) return null;
    if (max !== null && parsed > max) return null;
    return parsed;
  }

  function validateMegaState(value) {
    if (!value || Number(value.version) !== 1 || typeof value.records !== "object" || Array.isArray(value.records) || typeof value.energy_by_species !== "object" || Array.isArray(value.energy_by_species)) throw new Error("Mega state requires schema version 1.");
    for (const entry of Object.values(value.records)) {
      if (!entry || !TRI.has(String(entry.first_mega_unlocked || "unknown")) || !MEGA_LEVELS.has(String(entry.mega_level || "unknown"))) throw new Error("Mega record state is invalid.");
      if (entry.super_max_unlocked !== undefined && !TRI.has(String(entry.super_max_unlocked || "unknown"))) throw new Error("Super Max state is invalid.");
      if (entry.mega_energy !== null && entry.mega_energy !== undefined && numberOrNull(entry.mega_energy, { min: 0, integer: true }) === null) throw new Error("Mega Energy must be a non-negative integer or null.");
    }
    for (const energy of Object.values(value.energy_by_species)) if (energy !== null && numberOrNull(energy, { min: 0, integer: true }) === null) throw new Error("Species Mega Energy must be non-negative or null.");
    return value;
  }

  function validateMaxState(value) {
    if (!value || Number(value.version) !== 1 || typeof value.records !== "object" || Array.isArray(value.records)) throw new Error("Max state requires schema version 1.");
    if (value.max_particles !== null && value.max_particles !== undefined && numberOrNull(value.max_particles, { min: 0, integer: true }) === null) throw new Error("Max Particles must be non-negative or null.");
    for (const entry of Object.values(value.records)) {
      if (!entry || !TRI.has(String(entry.dynamax || "unknown")) || !TRI.has(String(entry.gigantamax || "unknown"))) throw new Error("Max owned state is invalid.");
      for (const key of ["max_attack_level", "max_guard_level", "max_spirit_level"]) {
        if (entry[key] !== null && entry[key] !== undefined && numberOrNull(entry[key], { min: 0, max: 3, integer: true }) === null) throw new Error(`${key} must be 0-3 or null.`);
      }
      if (entry.fast_move_type && !TYPES.has(String(entry.fast_move_type))) throw new Error("Fast move type is invalid.");
    }
    return value;
  }

  function validateHyperState(value) {
    if (!value || Number(value.version) !== 1 || typeof value.records !== "object" || Array.isArray(value.records) || typeof value.bottle_caps !== "object") throw new Error("Hyper Training state requires schema version 1.");
    for (const key of ["silver", "gold"]) {
      const count = value.bottle_caps[key];
      if (count !== null && count !== undefined && numberOrNull(count, { min: 0, integer: true }) === null) throw new Error("Bottle Cap counts must be non-negative integers or null.");
    }
    for (const entry of Object.values(value.records)) {
      if (!entry || !TRI.has(String(entry.active || "unknown")) || !TRI.has(String(entry.good_buddy_or_higher || "unknown"))) throw new Error("Hyper Training owned state is invalid.");
      for (const group of ["targets", "completed_points"]) {
        if (!entry[group]) continue;
        for (const stat of ["attack", "defense", "stamina"]) {
          const statValue = entry[group][stat];
          if (statValue !== null && statValue !== undefined && numberOrNull(statValue, { min: 0, max: 15, integer: true }) === null) throw new Error("Hyper Training stat targets must be 0-15.");
        }
      }
    }
    return value;
  }

  function validateBuddyQueue(value) {
    if (!value || Number(value.version) !== 1 || typeof value.projects !== "object" || Array.isArray(value.projects)) throw new Error("Buddy Queue requires schema version 1.");
    for (const [id, project] of Object.entries(value.projects)) {
      if (!id || !project || !String(project.record_id || "")) throw new Error("Buddy project is incomplete.");
      const priority = Number(project.priority ?? 0);
      if (!Number.isFinite(priority) || priority < 0 || priority > 100) throw new Error("Buddy priority must be 0-100.");
    }
    return value;
  }

  function validateRaidAssumptions(value) {
    if (!value || Number(value.version) !== 1 || typeof value.by_boss !== "object" || Array.isArray(value.by_boss)) throw new Error("Raid assumptions require schema version 1.");
    for (const assumptions of Object.values(value.by_boss)) {
      if (!assumptions || typeof assumptions !== "object") throw new Error("Raid assumption entry is invalid.");
      for (const key of ["hp", "defense", "timer_seconds", "group_size", "weather_multiplier", "friendship_multiplier", "party_power_multiplier", "mega_multiplier", "survival_multiplier"]) {
        if (assumptions[key] === null || assumptions[key] === undefined || assumptions[key] === "") continue;
        if (!Number.isFinite(Number(assumptions[key])) || Number(assumptions[key]) <= 0) throw new Error(`Raid assumption ${key} must be positive.`);
      }
    }
    return value;
  }

  function validateNamespace(name, value) {
    if (name === "mega_state") return validateMegaState(value);
    if (name === "max_state") return validateMaxState(value);
    if (name === "hyper_training") return validateHyperState(value);
    if (name === "buddy_queue") return validateBuddyQueue(value);
    if (name === "raid_assumptions") return validateRaidAssumptions(value);
    throw new Error(`Unknown advanced-lab namespace ${name}.`);
  }

  function defaultState(name) {
    if (name === "mega_state") return { version: 1, records: {}, energy_by_species: {} };
    if (name === "max_state") return { version: 1, records: {}, max_particles: null };
    if (name === "hyper_training") return { version: 1, bottle_caps: { silver: null, gold: null, expires_at: "" }, records: {} };
    if (name === "buddy_queue") return { version: 1, projects: {} };
    if (name === "raid_assumptions") return { version: 1, by_boss: {} };
    throw new Error(`Unknown advanced-lab namespace ${name}.`);
  }

  function loadState(storage, name) {
    const spec = STORAGE[name];
    if (!spec) throw new Error(`Unknown namespace ${name}.`);
    const raw = loadObject(storage, spec.key, defaultState(name));
    try { return validateNamespace(name, raw); } catch { return defaultState(name); }
  }

  function saveState(storage, name, value) {
    return saveObject(storage, STORAGE[name].key, validateNamespace(name, value));
  }

  function extendUnifiedBackup(base, storage) {
    const output = JSON.parse(JSON.stringify(base || {}));
    output.namespaces = output.namespaces || {};
    for (const [name, spec] of Object.entries(STORAGE)) {
      const raw = storage?.getItem(spec.key);
      output.namespaces[name] = {
        storage_key: spec.key,
        schema_version: spec.version,
        present: raw !== null,
        data: raw === null ? null : validateNamespace(name, JSON.parse(raw)),
      };
    }
    output.extensions = { ...(output.extensions || {}), advanced_labs: { schema_version: 1, namespaces: Object.keys(STORAGE) } };
    return output;
  }

  function validateAdvancedBackup(raw, storage) {
    const namespaces = raw?.namespaces || {};
    const normalized = {}, preview = { added: [], replaced: [], absent: [] };
    for (const [name, spec] of Object.entries(STORAGE)) {
      const entry = namespaces[name];
      if (!entry) { preview.absent.push(name); continue; }
      if (entry.storage_key !== spec.key || Number(entry.schema_version) !== spec.version) throw new Error(`Advanced namespace ${name} has incompatible metadata.`);
      if (!entry.present) { preview.absent.push(name); continue; }
      normalized[name] = validateNamespace(name, entry.data);
      if (storage?.getItem(spec.key) == null) preview.added.push(name); else preview.replaced.push(name);
    }
    return { normalized, preview };
  }

  function allRestoreKeys(root) {
    const base = Object.values(root.CollectionLocalData?.STORAGE_KEYS || {});
    const player = Object.values(root.CollectionPlayerLabs?.STORAGE || {}).map((item) => item.key);
    return [...new Set([...base, ...player, ...Object.values(STORAGE).map((item) => item.key)])];
  }

  function atomicRestore(root, raw, records = []) {
    const Local = root.CollectionLocalData;
    if (!Local?.validateUnifiedBackup || !Local?.restoreUnifiedBackup) throw new Error("Base local-data restore tools are unavailable.");
    Local.validateUnifiedBackup(raw, root.localStorage, records);
    if (root.CollectionPlayerLabs?.validateLabBackup) root.CollectionPlayerLabs.validateLabBackup(raw, root.localStorage);
    const advanced = validateAdvancedBackup(raw, root.localStorage);
    const before = new Map(allRestoreKeys(root).map((key) => [key, root.localStorage.getItem(key)]));
    try {
      const baseResult = root.CollectionPlayerLabs?.atomicRestore
        ? root.CollectionPlayerLabs.atomicRestore(root, raw, records)
        : { base: Local.restoreUnifiedBackup(root.localStorage, raw, records), labs: { added: [], replaced: [] } };
      for (const [name, value] of Object.entries(advanced.normalized)) root.localStorage.setItem(STORAGE[name].key, JSON.stringify(value));
      return { base: baseResult, advanced: advanced.preview };
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
    const anchor = root.document.createElement("a");
    anchor.href = url; anchor.download = filename; anchor.click(); root.URL.revokeObjectURL(url);
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
      if (!event.target?.closest?.("#export-local-data")) return;
      event.preventDefault(); event.stopImmediatePropagation();
      const Local = root.CollectionLocalData;
      if (!Local?.buildUnifiedBackup) return;
      let payload = Local.buildUnifiedBackup(root.localStorage);
      if (root.CollectionPlayerLabs?.extendUnifiedBackup) payload = root.CollectionPlayerLabs.extendUnifiedBackup(payload, root.localStorage);
      payload = extendUnifiedBackup(payload, root.localStorage);
      downloadJson(root, "pokemon-go-collection-local-data.json", payload);
      root.CollectionStorageHealth?.markBackup?.(root.localStorage);
    }, true);

    documentObject.addEventListener("change", async (event) => {
      if (event.target !== restoreInput) return;
      event.preventDefault(); event.stopImmediatePropagation();
      try {
        const file = restoreInput.files?.[0]; if (!file) return;
        const raw = await readFile(root, file), Local = root.CollectionLocalData;
        const base = Local.validateUnifiedBackup(raw, root.localStorage, records).preview;
        const player = root.CollectionPlayerLabs?.validateLabBackup ? root.CollectionPlayerLabs.validateLabBackup(raw, root.localStorage).preview : { added: [], replaced: [] };
        const advanced = validateAdvancedBackup(raw, root.localStorage).preview;
        pending = raw; applyButton.disabled = false;
        if (previewTarget) previewTarget.textContent = `Restore preview: base add ${base.added.join(", ") || "none"}, player labs add ${player.added.join(", ") || "none"}, advanced labs add ${advanced.added.join(", ") || "none"}. No local data has changed yet.`;
      } catch (error) {
        pending = null; applyButton.disabled = true;
        if (previewTarget) previewTarget.textContent = `Restore validation failed: ${error.message || error}`;
      }
    }, true);

    documentObject.addEventListener("click", (event) => {
      if (!event.target?.closest?.("#apply-local-data-restore") || !pending) return;
      event.preventDefault(); event.stopImmediatePropagation();
      try {
        const result = atomicRestore(root, pending, records);
        pending = null; applyButton.disabled = true;
        const names = [...result.advanced.added, ...result.advanced.replaced];
        if (previewTarget) previewTarget.textContent = `Restore applied atomically. Advanced namespaces restored: ${names.join(", ") || "none"}. Reload pages to apply restored planning state.`;
      } catch (error) {
        if (previewTarget) previewTarget.textContent = `Restore failed without accepting partial advanced state: ${error.message || error}`;
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
    return `#${String(record?.pokemon_number ?? "?").padStart(4, "0")} ${record?.name || "Unknown"}${record?.form ? ` · ${record.form}` : ""} · CP ${record?.cp ?? "?"}`;
  }

  function optionHtml(record) {
    return `<option value="${escapeHtml(record.record_id)}">${escapeHtml(recordLabel(record))}</option>`;
  }

  function megaRecommendation(item, local, objective) {
    if (local.first_mega_unlocked === "unknown" || local.mega_level === "unknown") return { state: "blocked", text: "Enter this exact record's first-Mega history and Mega Level before recommending Energy/cooldown actions." };
    if (objective !== "progress" && item.current_objective_match?.freshness !== "fresh") return { state: "blocked", text: "No fresh event/raid snapshot supports a current type-matching recommendation." };
    if (objective !== "progress" && !(item.current_objective_match?.matched_types || []).length) return { state: "review", text: "This Mega/Primal target has no reviewed same-type overlap with the fresh featured set." };
    if (local.mega_level === "super-max") return { state: "available", text: "Super Max is already recorded locally. Prefer objective/type fit over further level progression." };
    if (objective === "progress") return { state: "review", text: "Progress is plausible, but any rush or Super Max spend must be compared against the local Energy balance and cooldown." };
    return { state: "available", text: `Fresh type overlap: ${(item.current_objective_match.matched_types || []).join(", ")}. Verify the exact active bonuses shown in Pokémon GO before spending Energy.` };
  }

  async function renderMega(root) {
    const mount = root.document.getElementById("mega-lab-root"); if (!mount) return false;
    const data = await fetchJson(root, "data/mega-lab.json"), state = loadState(root.localStorage, "mega_state");
    mount.innerHTML = `<section class="advanced-controls ds-card"><label>Exact owned record<select id="mega-record">${data.records.map(optionHtml).join("")}</select></label><label>Objective<select id="mega-objective"><option value="catch">Catch type bonus</option><option value="raid">Raid type support</option><option value="progress">Mega/Super Max progress</option></select></label></section><section id="mega-result" class="ds-card"></section>`;
    const select = root.document.getElementById("mega-record"), objective = root.document.getElementById("mega-objective"), result = root.document.getElementById("mega-result");
    function render() {
      const item = data.records.find((entry) => entry.record_id === select.value) || data.records[0]; if (!item) return;
      const local = state.records[item.record_id] || { first_mega_unlocked: "unknown", mega_level: "unknown", super_max_unlocked: "unknown", mega_energy: null, next_free_mega: "", priority: 50, favorite_project: false };
      const rec = megaRecommendation(item, local, objective.value);
      result.innerHTML = `<div class="advanced-grid"><article class="advanced-card"><h2>${escapeHtml(recordLabel(item))}</h2><p>Capability targets: ${(item.capability.targets || []).map((target) => `${escapeHtml(target.name)} (${escapeHtml(target.kind || "transform")}: ${(target.types || []).join("/")})`).join(" · ")}</p><p class="advanced-warning">Capability does not prove Mega history, Energy, level, or cooldown for this exact record.</p><p>Fresh featured types: ${escapeHtml((data.current_matching.types || []).join(", ") || "none")}. This record matches: ${escapeHtml((item.current_objective_match.matched_types || []).join(", ") || "none")}.</p><p>Reviewed Super Max contract: ${escapeHtml(data.super_max_contract)}</p></article><article class="advanced-card"><h3>Local exact-record state</h3><label>First Mega unlocked<select id="mega-first"><option>unknown</option><option>yes</option><option>no</option></select></label><label>Mega Level<select id="mega-level"><option value="unknown">Unknown</option><option value="base">Base</option><option value="high">High</option><option value="max">Max</option><option value="super-max">Super Max</option></select></label><label>Energy balance for this record<input id="mega-energy" type="number" min="0" step="1"></label><label>Next free Mega / cooldown note<input id="mega-cooldown" type="text" placeholder="User-entered time or note"></label><label>Priority 0-100<input id="mega-priority" type="number" min="0" max="100" step="1"></label><label><input id="mega-favorite" type="checkbox"> Favorite Mega project</label><button id="mega-save" type="button">Save local Mega state</button></article></div><article class="ds-card ${rec.state === "blocked" ? "advanced-danger" : rec.state === "available" ? "advanced-good" : "advanced-warning"}"><h3>Recommendation</h3><p>${escapeHtml(rec.text)}</p><p>${escapeHtml(item.opportunity_cost)}</p><p><a href="${escapeHtml(item.record_route)}">Open exact record</a> · <a href="${escapeHtml(item.action_pack)}">Locate in Pokémon GO</a></p></article>`;
      const first = root.document.getElementById("mega-first"), level = root.document.getElementById("mega-level"), energy = root.document.getElementById("mega-energy"), cooldown = root.document.getElementById("mega-cooldown"), priority = root.document.getElementById("mega-priority"), favorite = root.document.getElementById("mega-favorite");
      first.value = local.first_mega_unlocked || "unknown"; level.value = local.mega_level || "unknown"; energy.value = local.mega_energy ?? ""; cooldown.value = local.next_free_mega || ""; priority.value = local.priority ?? 50; favorite.checked = Boolean(local.favorite_project);
      root.document.getElementById("mega-save").addEventListener("click", () => {
        state.records[item.record_id] = { first_mega_unlocked: first.value, mega_level: level.value, super_max_unlocked: level.value === "super-max" ? "yes" : "unknown", mega_energy: numberOrNull(energy.value, { min: 0, integer: true }), next_free_mega: String(cooldown.value || "").trim(), priority: numberOrNull(priority.value, { min: 0, max: 100, integer: true }) ?? 50, favorite_project: favorite.checked };
        saveState(root.localStorage, "mega_state", state); render();
      });
    }
    select.addEventListener("change", render); objective.addEventListener("change", render); render(); return true;
  }

  function maxAttackType(local) {
    if (local.gigantamax === "yes" && local.gmax_attack_type) return { state: "gmax-explicit", type: local.gmax_attack_type };
    if (local.dynamax === "yes" && local.fast_move_type) return { state: "dynamax-fast-type", type: local.fast_move_type };
    return { state: "unknown", type: null };
  }

  async function renderMax(root) {
    const mount = root.document.getElementById("max-battle-lab-root"); if (!mount) return false;
    const data = await fetchJson(root, "data/max-battle-lab.json"), state = loadState(root.localStorage, "max_state");
    mount.innerHTML = `<section class="advanced-controls ds-card"><label>Exact owned record<select id="max-record">${data.records.map(optionHtml).join("")}</select></label><label>Local Max Particle balance<input id="max-particles" type="number" min="0" step="1" value="${state.max_particles ?? ""}"></label><button id="max-particles-save" type="button">Save balance</button></section><section id="max-result" class="ds-card"></section><section class="ds-card"><h2>My 3-Pokémon Max party</h2><div id="max-party"></div></section>`;
    const select = root.document.getElementById("max-record"), result = root.document.getElementById("max-result"), party = root.document.getElementById("max-party");
    function renderParty() {
      const known = data.records.map((item) => ({ item, local: state.records[item.record_id] || {} })).filter(({ local }) => local.dynamax === "yes" || local.gigantamax === "yes");
      known.sort((a, b) => (Number(b.local.max_build_priority || 0) - Number(a.local.max_build_priority || 0)) || (Number(b.item.cp || 0) - Number(a.item.cp || 0)));
      const selected = known.slice(0, 3);
      party.innerHTML = selected.length ? `<ol>${selected.map(({ item, local }) => `<li><strong>${escapeHtml(recordLabel(item))}</strong> · Attack ${local.max_attack_level ?? "?"}, Guard ${local.max_guard_level ?? "?"}, Spirit ${local.max_spirit_level ?? "?"} · Max Attack type ${escapeHtml(maxAttackType(local).type || "unknown")} · <a href="${escapeHtml(item.record_route)}">exact record</a></li>`).join("")}</ol><p>Party size contract: ${data.battle_contract.party_size}. Current boss data: <strong>${escapeHtml(data.current_bosses.state)}</strong>. Max boss matchup claims are blocked unless the snapshot is fresh.</p>` : `<p class="ds-empty">No exact record is locally confirmed Dynamax or Gigantamax. Species capability is not enough.</p>`;
    }
    function render() {
      const item = data.records.find((entry) => entry.record_id === select.value) || data.records[0]; if (!item) return;
      const local = state.records[item.record_id] || { dynamax: "unknown", gigantamax: "unknown", max_attack_level: null, max_guard_level: null, max_spirit_level: null, fast_move_type: "", gmax_attack_type: "", max_build_priority: 50, note: "" };
      const attack = maxAttackType(local);
      result.innerHTML = `<div class="advanced-grid"><article><h2>${escapeHtml(recordLabel(item))}</h2><p>Static species capability: Dynamax ${escapeHtml(String(item.species_capability.dynamax))}, Gigantamax ${escapeHtml(String(item.species_capability.gigantamax))}. This never proves owned Max state.</p><p>Known Fast Move: ${escapeHtml(item.max_attack.known_fast_move || "unknown")}. Dynamax Max Attack type follows the explicitly reviewed/confirmed Fast Attack type.</p><p class="advanced-warning">${escapeHtml(item.trade_transfer_warning)}</p></article><article><h3>Local exact-record Max state</h3><label>Dynamax<select id="max-dynamax"><option>unknown</option><option>yes</option><option>no</option></select></label><label>Gigantamax<select id="max-gigantamax"><option>unknown</option><option>yes</option><option>no</option></select></label><label>Fast Attack type<select id="max-fast-type"><option value="">Unknown</option>${[...TYPES].map((type) => `<option>${type}</option>`).join("")}</select></label><label>Explicit G-Max attack type<select id="max-gmax-type"><option value="">Unknown/not applicable</option>${[...TYPES].map((type) => `<option>${type}</option>`).join("")}</select></label><label>Max Attack level<input id="max-attack-level" type="number" min="0" max="3"></label><label>Max Guard level<input id="max-guard-level" type="number" min="0" max="3"></label><label>Max Spirit level<input id="max-spirit-level" type="number" min="0" max="3"></label><label>Priority 0-100<input id="max-priority" type="number" min="0" max="100"></label><button id="max-save" type="button">Save local Max state</button></article></div><p>Max Attack simulation: <strong>${escapeHtml(attack.state)}</strong>${attack.type ? ` · ${escapeHtml(attack.type)}` : ""}. A Fast TM type change changes this Dynamax attack type only when the new Fast Attack type is known.</p><p>Current Max bosses: ${(data.current_bosses.bosses || []).length}; planning allowed: ${data.current_bosses.planning_allowed ? "yes" : "no"}.</p><p><a href="${escapeHtml(item.action_pack)}">Exact Action Pack</a></p>`;
      const fields = {
        dynamax: root.document.getElementById("max-dynamax"), gigantamax: root.document.getElementById("max-gigantamax"), fast_move_type: root.document.getElementById("max-fast-type"), gmax_attack_type: root.document.getElementById("max-gmax-type"), max_attack_level: root.document.getElementById("max-attack-level"), max_guard_level: root.document.getElementById("max-guard-level"), max_spirit_level: root.document.getElementById("max-spirit-level"), max_build_priority: root.document.getElementById("max-priority"),
      };
      for (const [key, field] of Object.entries(fields)) field.value = local[key] ?? "";
      root.document.getElementById("max-save").addEventListener("click", () => {
        state.records[item.record_id] = { dynamax: fields.dynamax.value, gigantamax: fields.gigantamax.value, fast_move_type: fields.fast_move_type.value, gmax_attack_type: fields.gmax_attack_type.value, max_attack_level: numberOrNull(fields.max_attack_level.value, { min: 0, max: 3, integer: true }), max_guard_level: numberOrNull(fields.max_guard_level.value, { min: 0, max: 3, integer: true }), max_spirit_level: numberOrNull(fields.max_spirit_level.value, { min: 0, max: 3, integer: true }), max_build_priority: numberOrNull(fields.max_build_priority.value, { min: 0, max: 100, integer: true }) ?? 50 };
        saveState(root.localStorage, "max_state", state); render(); renderParty();
      });
    }
    root.document.getElementById("max-particles-save").addEventListener("click", () => { state.max_particles = numberOrNull(root.document.getElementById("max-particles").value, { min: 0, integer: true }); saveState(root.localStorage, "max_state", state); });
    select.addEventListener("change", render); render(); renderParty(); return true;
  }

  function cpCrossingText(projection) {
    if (!projection || projection.state !== "projected") return projection?.reason || "projection unavailable";
    return `CP ${projection.cp}${projection.league_cap_warnings?.length ? ` · ${projection.league_cap_warnings.join(" ")}` : " · no documented 500/1500/2500 cap crossing from this point"}`;
  }

  async function renderHyper(root) {
    const mount = root.document.getElementById("hyper-training-root"); if (!mount) return false;
    const data = await fetchJson(root, "data/hyper-training.json"), state = loadState(root.localStorage, "hyper_training");
    mount.innerHTML = `<section class="advanced-controls ds-card"><label>Exact owned record<select id="hyper-record">${data.records.map(optionHtml).join("")}</select></label><label>Silver Bottle Caps<input id="hyper-silver" type="number" min="0" step="1"></label><label>Gold Bottle Caps<input id="hyper-gold" type="number" min="0" step="1"></label><label>Bottle Cap expiration<input id="hyper-cap-expiry" type="datetime-local"></label><button id="hyper-inventory-save" type="button">Save local Bottle Cap info</button></section><section id="hyper-result" class="ds-card"></section>`;
    root.document.getElementById("hyper-silver").value = state.bottle_caps.silver ?? ""; root.document.getElementById("hyper-gold").value = state.bottle_caps.gold ?? ""; root.document.getElementById("hyper-cap-expiry").value = state.bottle_caps.expires_at || "";
    root.document.getElementById("hyper-inventory-save").addEventListener("click", () => { state.bottle_caps = { silver: numberOrNull(root.document.getElementById("hyper-silver").value, { min: 0, integer: true }), gold: numberOrNull(root.document.getElementById("hyper-gold").value, { min: 0, integer: true }), expires_at: root.document.getElementById("hyper-cap-expiry").value || "" }; saveState(root.localStorage, "hyper_training", state); });
    const select = root.document.getElementById("hyper-record"), result = root.document.getElementById("hyper-result");
    function render() {
      const item = data.records.find((entry) => entry.record_id === select.value) || data.records[0]; if (!item) return;
      const local = state.records[item.record_id] || { active: "unknown", good_buddy_or_higher: "unknown", targets: null, completed_points: null, training_deadline: "" };
      const allowed = item.eligibility === "requires-local-good-buddy-confirmation" && local.good_buddy_or_higher === "yes";
      result.innerHTML = `<h2>${escapeHtml(recordLabel(item))}</h2><p>Eligibility: <strong>${escapeHtml(item.eligibility)}</strong>${allowed ? " · local Good Buddy confirmation satisfies the remaining reviewed eligibility gate" : ""}.</p><p class="advanced-danger">${escapeHtml(item.irreversible_warning)}</p><div class="advanced-grid"><article><h3>Next irreversible stat points</h3><ul>${(item.next_stat_points || []).map((point) => `<li><strong>${escapeHtml(point.stat)}</strong> ${point.from}→${point.to}: ${escapeHtml(cpCrossingText(point.projection))}</li>`).join("") || "<li>No deterministic next-point projection is available.</li>"}</ul><p>Higher IV is not automatically better under a CP cap. Review each next point, not just the final target.</p></article><article><h3>Local Hyper Training state</h3><label>Good Buddy or higher<select id="hyper-buddy"><option>unknown</option><option>yes</option><option>no</option></select></label><label>Hyper Training active<select id="hyper-active"><option>unknown</option><option>yes</option><option>no</option></select></label><label>Training deadline<input id="hyper-deadline" type="datetime-local"></label><button id="hyper-save" type="button">Save local Hyper state</button></article></div><p>Better owned same-form alternatives: ${(item.owned_alternatives || []).map((alt) => `${alt.iv_percent}% CP ${alt.cp} (${alt.record_id})`).join(" · ") || "none identified by known IV percentage"}.</p><p>${escapeHtml(item.home_warning)}</p><p><a href="${escapeHtml(item.record_route)}">Open exact record</a> · <a href="${escapeHtml(item.action_pack)}">Exact checklist handoff</a></p>`;
      const buddy = root.document.getElementById("hyper-buddy"), active = root.document.getElementById("hyper-active"), deadline = root.document.getElementById("hyper-deadline"); buddy.value = local.good_buddy_or_higher || "unknown"; active.value = local.active || "unknown"; deadline.value = local.training_deadline || "";
      root.document.getElementById("hyper-save").addEventListener("click", () => { state.records[item.record_id] = { ...local, good_buddy_or_higher: buddy.value, active: active.value, training_deadline: deadline.value || "" }; saveState(root.localStorage, "hyper_training", state); render(); });
    }
    select.addEventListener("change", render); render(); return true;
  }

  function deadlineBonus(deadline, now = Date.now()) {
    if (!deadline) return 0;
    const when = new Date(deadline).getTime(); if (!Number.isFinite(when)) return 0;
    const hours = (when - now) / 3600000;
    if (hours <= 24) return 40;
    if (hours <= 168) return 20;
    return 0;
  }

  function rankBuddyProjects(candidates, localState, hyperState = {}, megaState = {}, now = Date.now()) {
    const projects = [];
    for (const candidate of candidates || []) {
      const saved = localState?.projects?.[candidate.record_id] || {};
      const hyper = hyperState?.records?.[candidate.record_id] || {};
      const mega = megaState?.records?.[candidate.record_id] || {};
      const defaultPriority = Math.max(...(candidate.objectives || []).map((item) => Number(item.default_priority || 0)), 0);
      const priority = Number(saved.priority ?? 50);
      const deadline = saved.deadline || hyper.training_deadline || "";
      const score = priority + defaultPriority + deadlineBonus(deadline, now) + (saved.pinned ? 100 : 0) + (hyper.active === "yes" ? 35 : 0) + (mega.favorite_project ? 15 : 0);
      if (saved.skipped || saved.completed) continue;
      projects.push({ candidate, saved, score, deadline, reasons: [`user priority ${priority}`, `objective base ${defaultPriority}`, ...(hyper.active === "yes" ? ["active Hyper Training +35"] : []), ...(mega.favorite_project ? ["favorite Mega project +15"] : []), ...(saved.pinned ? ["pinned +100"] : []), ...(deadlineBonus(deadline, now) ? [`deadline +${deadlineBonus(deadline, now)}`] : [])] });
    }
    return projects.sort((a, b) => b.score - a.score || String(a.candidate.record_id).localeCompare(String(b.candidate.record_id)));
  }

  async function renderBuddy(root) {
    const mount = root.document.getElementById("buddy-queue-root"); if (!mount) return false;
    const data = await fetchJson(root, "data/buddy-queue.json"), state = loadState(root.localStorage, "buddy_queue"), hyper = loadState(root.localStorage, "hyper_training"), mega = loadState(root.localStorage, "mega_state");
    mount.innerHTML = `<section class="ds-card"><h2>Transparent ranking</h2><p>${escapeHtml(data.ranking_contract.base)}. ${escapeHtml(data.ranking_contract.deadline)}. Pin: ${escapeHtml(data.ranking_contract.pin)}. Distance is never converted into guaranteed Candy/Mega Energy yield.</p></section><section id="buddy-results" class="advanced-list advanced-ranked"></section>`;
    const results = root.document.getElementById("buddy-results");
    function render() {
      const ranked = rankBuddyProjects(data.candidates, state, hyper, mega);
      results.innerHTML = ranked.slice(0, 30).map(({ candidate, saved, score, deadline, reasons }) => `<article class="ds-card advanced-card"><h3>${escapeHtml(recordLabel(candidate))}</h3><p>Score <strong>${score}</strong> · ${escapeHtml(reasons.join(" · "))}</p><p>Objectives: ${(candidate.objectives || []).map((objective) => escapeHtml(objective.kind)).join(", ")}. Known buddy distance: ${candidate.buddy_distance_km ?? "unknown"} km.</p><p>Deadline: ${escapeHtml(deadline || "none")}. ${escapeHtml(candidate.alternative_resource_paths)}</p><div class="advanced-inline"><label>Priority <input data-buddy-priority="${escapeHtml(candidate.record_id)}" type="number" min="0" max="100" value="${saved.priority ?? 50}"></label><button type="button" data-buddy-pin="${escapeHtml(candidate.record_id)}">${saved.pinned ? "Unpin" : "Pin"}</button><button type="button" data-buddy-skip="${escapeHtml(candidate.record_id)}">Skip</button><button type="button" data-buddy-complete="${escapeHtml(candidate.record_id)}">Complete</button></div><p><a href="${escapeHtml(candidate.record_route)}">Open exact record</a> · <a href="${escapeHtml(candidate.action_pack)}">Buddy checklist handoff</a></p></article>`).join("") || `<p class="ds-empty">No active buddy projects. Skipped/completed projects stay local and can be restored from backup.</p>`;
      results.querySelectorAll("[data-buddy-priority]").forEach((field) => field.addEventListener("change", () => { const id = field.dataset.buddyPriority; state.projects[id] = { ...(state.projects[id] || {}), record_id: id, priority: Math.max(0, Math.min(100, Number(field.value || 0))) }; saveState(root.localStorage, "buddy_queue", state); render(); }));
      results.querySelectorAll("[data-buddy-pin]").forEach((button) => button.addEventListener("click", () => { const id = button.dataset.buddyPin, current = state.projects[id] || { record_id: id, priority: 50 }; state.projects[id] = { ...current, pinned: !current.pinned }; saveState(root.localStorage, "buddy_queue", state); render(); }));
      results.querySelectorAll("[data-buddy-skip]").forEach((button) => button.addEventListener("click", () => { const id = button.dataset.buddySkip; state.projects[id] = { ...(state.projects[id] || { record_id: id, priority: 50 }), skipped: true }; saveState(root.localStorage, "buddy_queue", state); render(); }));
      results.querySelectorAll("[data-buddy-complete]").forEach((button) => button.addEventListener("click", () => { const id = button.dataset.buddyComplete; state.projects[id] = { ...(state.projects[id] || { record_id: id, priority: 50 }), completed: true }; saveState(root.localStorage, "buddy_queue", state); render(); }));
    }
    render(); return true;
  }

  function simulateRaidModel(data, assumptions) {
    if (String(data?.freshness || "") !== "fresh") return { state: "blocked", reason: "current boss data is not fresh" };
    for (const key of ["hp", "defense", "timer_seconds"]) if (!Number.isFinite(Number(assumptions[key])) || Number(assumptions[key]) <= 0) return { state: "blocked", reason: "boss HP, defense, and timer are required positive model inputs" };
    const groupSize = Math.max(1, Math.round(Number(assumptions.group_size || 1)));
    const multiplierKeys = ["weather_multiplier", "friendship_multiplier", "party_power_multiplier", "mega_multiplier", "survival_multiplier"];
    for (const key of multiplierKeys) if (!Number.isFinite(Number(assumptions[key] ?? 1)) || Number(assumptions[key] ?? 1) <= 0) return { state: "blocked", reason: `${key} must be positive` };
    const attackers = (data.owned_records || []).filter((item) => item.model_inputs?.state === "available").map((item) => {
      const inputs = item.model_inputs, moveFactor = 0.60 + 0.40 * Number(inputs.move_completeness || 0);
      const dps = Number(inputs.attack) / Number(assumptions.defense) * 28 * moveFactor * Number(assumptions.weather_multiplier || 1) * Number(assumptions.friendship_multiplier || 1) * Number(assumptions.party_power_multiplier || 1) * Number(assumptions.mega_multiplier || 1);
      const bulk = Number(inputs.defense) * Math.sqrt(Number(inputs.hp)) / 100;
      return { record_id: item.record_id, name: item.name, form: item.form, cp: item.cp, known_moves: item.moves, dps_style_proxy: dps, tdo_style_proxy: dps * bulk * Number(assumptions.survival_multiplier || 1), confidence: Number(inputs.confidence || 0), owned: true };
    }).sort((a, b) => b.dps_style_proxy - a.dps_style_proxy || b.tdo_style_proxy - a.tdo_style_proxy || String(a.record_id).localeCompare(String(b.record_id)));
    const team = attackers.slice(0, 6); if (!team.length) return { state: "blocked", reason: "no owned records have sufficient model inputs" };
    const meanDps = team.reduce((sum, item) => sum + item.dps_style_proxy, 0) / team.length, ttw = Number(assumptions.hp) / (meanDps * groupSize), totalTdo = team.reduce((sum, item) => sum + item.tdo_style_proxy, 0) * groupSize, pressure = Number(assumptions.hp) / Math.max(totalTdo, 1), estimatedFaints = Math.max(0, Math.ceil(pressure * team.length) - team.length), confidence = Math.min(...team.map((item) => item.confidence));
    return { state: "simulated", model_version: data.model_version, team, alternatives: attackers.slice(6, 12), estimated_ttw_seconds: Math.round(ttw * 10) / 10, estimated_ttw_range_seconds: [Math.round(ttw * 0.85 * 10) / 10, Math.round(ttw * 1.25 * 10) / 10], estimated_faints: estimatedFaints, relobby_risk: estimatedFaints >= 6 ? "high" : estimatedFaints >= 3 ? "moderate" : "low", practicality: ttw <= Number(assumptions.timer_seconds) * 0.9 ? "appears-practical-under-assumptions" : "appears-not-practical-under-assumptions", confidence: confidence >= 0.9 ? "high" : confidence >= 0.7 ? "medium" : "low", assumptions: { ...assumptions, group_size: groupSize } };
  }

  function bossKey(boss) {
    return [boss.dex, boss.name, boss.form, boss.tier].map((value) => String(value || "").toLowerCase()).join("|");
  }

  async function renderRaid(root) {
    const mount = root.document.getElementById("raid-readiness-root"); if (!mount) return false;
    const data = await fetchJson(root, "data/raid-readiness.json"), state = loadState(root.localStorage, "raid_assumptions"), bosses = data.current_bosses.bosses || [];
    if (data.current_bosses.freshness !== "fresh" || !bosses.length) { mount.innerHTML = `<section class="ds-card advanced-danger"><h2>Current raid simulation blocked</h2><p>Raid source freshness: <strong>${escapeHtml(data.current_bosses.freshness)}</strong>. Current-boss simulation refuses stale, expired, or unavailable rotation data.</p><p>The independent model remains documented, but no current boss is asserted.</p></section>`; return true; }
    mount.innerHTML = `<section class="advanced-controls ds-card"><label>Fresh current boss<select id="raid-boss">${bosses.map((boss, index) => `<option value="${index}">${escapeHtml(`#${boss.dex} ${boss.name}${boss.form ? ` · ${boss.form}` : ""} · ${boss.tier || "tier unknown"}`)}</option>`).join("")}</select></label><label>Group size<input id="raid-group" type="number" min="1" max="20" value="1"></label></section><section id="raid-model" class="ds-card"></section><section id="raid-output"></section>`;
    const bossSelect = root.document.getElementById("raid-boss"), model = root.document.getElementById("raid-model"), output = root.document.getElementById("raid-output");
    function renderInputs() {
      const boss = bosses[Number(bossSelect.value || 0)], key = bossKey(boss), saved = state.by_boss[key] || {};
      const baseDefense = boss.static_species?.base_stats?.defense ?? "";
      model.innerHTML = `<h2>${escapeHtml(boss.name)} readiness assumptions</h2><p>Boss identity/tier is fresh Official rotation data. HP/defense/timer are model inputs and are not invented from the announcement. Static species base defense ${baseDefense || "unknown"} may be used only as an explicitly accepted proxy.</p><div class="advanced-grid"><label>Boss HP<input id="raid-hp" type="number" min="1" value="${saved.hp ?? ""}"></label><label>Boss defense<input id="raid-defense" type="number" min="1" value="${saved.defense ?? baseDefense}"></label><label>Battle timer seconds<input id="raid-timer" type="number" min="1" value="${saved.timer_seconds ?? ""}"></label><label>Weather multiplier<input id="raid-weather" type="number" min="0.1" step="0.01" value="${saved.weather_multiplier ?? 1}"></label><label>Friendship multiplier<input id="raid-friendship" type="number" min="0.1" step="0.01" value="${saved.friendship_multiplier ?? 1}"></label><label>Party Power multiplier<input id="raid-party" type="number" min="0.1" step="0.01" value="${saved.party_power_multiplier ?? 1}"></label><label>Mega/Primal multiplier<input id="raid-mega" type="number" min="0.1" step="0.01" value="${saved.mega_multiplier ?? 1}"></label><label>Dodge/survival multiplier<input id="raid-survival" type="number" min="0.1" step="0.01" value="${saved.survival_multiplier ?? 1}"></label></div><div class="advanced-actions"><button id="raid-run" type="button">Run owned-roster estimate</button><button id="raid-save" type="button">Save assumptions locally</button></div><p class="advanced-assumptions">${escapeHtml(data.model.formula_summary)} ${escapeHtml(data.model.limits.join(" "))}</p>`;
      const assumptions = () => ({ hp: Number(root.document.getElementById("raid-hp").value), defense: Number(root.document.getElementById("raid-defense").value), timer_seconds: Number(root.document.getElementById("raid-timer").value), group_size: Number(root.document.getElementById("raid-group").value || 1), weather_multiplier: Number(root.document.getElementById("raid-weather").value || 1), friendship_multiplier: Number(root.document.getElementById("raid-friendship").value || 1), party_power_multiplier: Number(root.document.getElementById("raid-party").value || 1), mega_multiplier: Number(root.document.getElementById("raid-mega").value || 1), survival_multiplier: Number(root.document.getElementById("raid-survival").value || 1) });
      root.document.getElementById("raid-save").addEventListener("click", () => { state.by_boss[key] = assumptions(); saveState(root.localStorage, "raid_assumptions", state); });
      root.document.getElementById("raid-run").addEventListener("click", () => {
        const result = simulateRaidModel({ ...data, freshness: boss.freshness }, assumptions());
        if (result.state !== "simulated") { output.innerHTML = `<section class="ds-card advanced-danger"><h2>Simulation blocked</h2><p>${escapeHtml(result.reason)}</p></section>`; return; }
        output.innerHTML = `<section class="ds-card ${result.practicality.includes("not") ? "advanced-warning" : "advanced-good"}"><h2>${escapeHtml(result.practicality)}</h2><p>TTW estimate ${result.estimated_ttw_seconds}s, range ${result.estimated_ttw_range_seconds[0]}-${result.estimated_ttw_range_seconds[1]}s · estimated faints ${result.estimated_faints} · relobby risk ${escapeHtml(result.relobby_risk)} · confidence ${escapeHtml(result.confidence)} · model ${escapeHtml(result.model_version)}.</p><p>This is a Simulation/Inference result under your explicit assumptions, not an Official result or guarantee.</p><div class="advanced-table-wrap"><table class="advanced-table"><thead><tr><th>Owned team</th><th>DPS-style proxy</th><th>TDO-style proxy</th><th>Moves</th></tr></thead><tbody>${result.team.map((item) => `<tr><td>${escapeHtml(item.name)} · CP ${item.cp ?? "?"}</td><td>${item.dps_style_proxy.toFixed(2)}</td><td>${item.tdo_style_proxy.toFixed(2)}</td><td>${escapeHtml([item.known_moves.fast, item.known_moves.charged].filter(Boolean).join(" / ") || "incomplete")}</td></tr>`).join("")}</tbody></table></div><p>Raid Advice: review the weakest modeled slot against <a href="move-lab.html">Move Lab</a> and known investment inputs before spending. Missing exact PvE move power blocks stronger cost-effectiveness claims.</p></section>`;
      });
    }
    bossSelect.addEventListener("change", renderInputs); renderInputs(); return true;
  }

  function installTodayDeadlines(root) {
    if (!root.document.getElementById("today-root") && !root.document.querySelector("main")) return false;
    if (root.document.querySelector("[data-advanced-deadlines]")) return false;
    const hyper = loadState(root.localStorage, "hyper_training"), buddy = loadState(root.localStorage, "buddy_queue"), items = [];
    if (hyper.bottle_caps.expires_at) items.push({ label: "Bottle Cap expiration", deadline: hyper.bottle_caps.expires_at, route: "hyper-training.html" });
    for (const [recordId, entry] of Object.entries(hyper.records || {})) if (entry.active === "yes" && entry.training_deadline) items.push({ label: `Hyper Training ${recordId}`, deadline: entry.training_deadline, route: `hyper-training.html?record=${encodeURIComponent(recordId)}` });
    for (const [recordId, project] of Object.entries(buddy.projects || {})) if (!project.completed && !project.skipped && project.deadline) items.push({ label: `Buddy goal ${recordId}`, deadline: project.deadline, route: "buddy-queue.html" });
    if (!items.length) return false;
    items.sort((a, b) => new Date(a.deadline) - new Date(b.deadline));
    const section = root.document.createElement("section"); section.className = "ds-card advanced-deadlines"; section.dataset.advancedDeadlines = "true";
    section.innerHTML = `<h2>Local planning deadlines</h2><p>Browser-local user-entered dates. They are not inferred from game state.</p><ul>${items.slice(0, 10).map((item) => `<li><a href="${escapeHtml(item.route)}">${escapeHtml(item.label)}</a> · ${escapeHtml(item.deadline)}</li>`).join("")}</ul>`;
    (root.document.getElementById("today-root") || root.document.querySelector("main"))?.prepend(section); return true;
  }

  async function install(root) {
    installBackupBridge(root);
    installTodayDeadlines(root);
    try {
      if (await renderMega(root)) return;
      if (await renderMax(root)) return;
      if (await renderHyper(root)) return;
      if (await renderBuddy(root)) return;
      await renderRaid(root);
    } catch (error) {
      const mount = root.document.querySelector("#mega-lab-root,#max-battle-lab-root,#hyper-training-root,#buddy-queue-root,#raid-readiness-root");
      if (mount) mount.innerHTML = `<p class="ds-notice" data-kind="danger">Advanced lab unavailable: ${escapeHtml(error.message || error)}</p>`;
    }
  }

  return {
    STORAGE,
    validateMegaState,
    validateMaxState,
    validateHyperState,
    validateBuddyQueue,
    validateRaidAssumptions,
    validateNamespace,
    defaultState,
    loadState,
    saveState,
    extendUnifiedBackup,
    validateAdvancedBackup,
    atomicRestore,
    installBackupBridge,
    megaRecommendation,
    maxAttackType,
    rankBuddyProjects,
    simulateRaidModel,
    installTodayDeadlines,
    install,
  };
});
