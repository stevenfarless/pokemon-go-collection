"use strict";

(function exposeItemBagPlanner(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionItemBagPlanner = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const ITEM_BAG_KEY = "pokemon-go-collection:item-bag:v1";
  const ITEM_BAG_VERSION = 1;
  const PROFILE_IDS = Object.freeze(["balanced", "catching", "raid", "pvp", "rocket", "max", "rural", "custom"]);
  const CATEGORIES = Object.freeze([
    { id: "poke_ball", label: "Poké Balls", group: "catching", baseline: [40, 120], cleanup: 10 },
    { id: "great_ball", label: "Great Balls", group: "catching", baseline: [40, 120], cleanup: 20 },
    { id: "ultra_ball", label: "Ultra Balls", group: "catching", baseline: [60, 180], cleanup: 80 },
    { id: "razz_berry", label: "Razz Berries", group: "berries", baseline: [15, 50], cleanup: 5 },
    { id: "nanab_berry", label: "Nanab Berries", group: "berries", baseline: [5, 25], cleanup: 1 },
    { id: "pinap_berry", label: "Pinap Berries", group: "berries", baseline: [25, 75], cleanup: 40 },
    { id: "golden_razz", label: "Golden Razz Berries", group: "premium", baseline: [20, 80], rare: true },
    { id: "silver_pinap", label: "Silver Pinap Berries", group: "premium", baseline: [10, 50], rare: true },
    { id: "potion", label: "Potions", group: "healing", baseline: [0, 20], cleanup: 1 },
    { id: "super_potion", label: "Super Potions", group: "healing", baseline: [0, 25], cleanup: 2 },
    { id: "hyper_potion", label: "Hyper Potions", group: "healing", baseline: [15, 60], cleanup: 30 },
    { id: "max_potion", label: "Max Potions", group: "healing", baseline: [15, 60], cleanup: 35 },
    { id: "revive", label: "Revives", group: "healing", baseline: [15, 50], cleanup: 20 },
    { id: "max_revive", label: "Max Revives", group: "healing", baseline: [20, 70], cleanup: 45 },
    { id: "fast_tm", label: "Fast TMs", group: "battle", baseline: [10, 40], cleanup: 25 },
    { id: "charged_tm", label: "Charged TMs", group: "battle", baseline: [20, 70], cleanup: 45 },
    { id: "elite_fast_tm", label: "Elite Fast TMs", group: "rare", baseline: [0, 9999], rare: true },
    { id: "elite_charged_tm", label: "Elite Charged TMs", group: "rare", baseline: [0, 9999], rare: true },
    { id: "evolution_item", label: "Evolution Items", group: "evolution", baseline: [3, 12], cleanup: 5 },
    { id: "raid_pass", label: "Raid Passes", group: "raid", baseline: [0, 9999], rare: true },
    { id: "premium_battle_pass", label: "Premium Battle Passes", group: "raid", baseline: [0, 9999], rare: true },
    { id: "remote_raid_pass", label: "Remote Raid Passes", group: "raid", baseline: [0, 9999], rare: true },
    { id: "incense", label: "Incense", group: "boost", baseline: [2, 20], cleanup: 8 },
    { id: "lure", label: "Lure Modules", group: "boost", baseline: [2, 15], cleanup: 6 },
    { id: "lucky_egg", label: "Lucky Eggs", group: "boost", baseline: [2, 15], cleanup: 5 },
    { id: "star_piece", label: "Star Pieces", group: "boost", baseline: [2, 15], cleanup: 8 },
    { id: "incubator", label: "Incubators", group: "rare", baseline: [0, 9999], rare: true },
    { id: "bottle_cap", label: "Bottle Caps / time-limited rare items", group: "rare", baseline: [0, 9999], rare: true, expiration: true },
  ]);
  const PROFILE_MULTIPLIERS = Object.freeze({
    balanced: {},
    catching: { catching: 1.6, berries: 1.3, healing: 0.7 },
    raid: { catching: 0.8, healing: 1.5, battle: 1.3, raid: 1.5 },
    pvp: { catching: 0.9, battle: 1.6, healing: 0.7 },
    rocket: { catching: 0.9, healing: 1.7, battle: 1.25 },
    max: { catching: 1.0, healing: 1.2, battle: 1.2 },
    rural: { catching: 1.7, berries: 1.25, healing: 1.2, boost: 1.25 },
    custom: {},
  });

  const num = (value) => {
    if (value === null || value === undefined || String(value).trim() === "") return null;
    const parsed = Number(String(value).replaceAll(",", ""));
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
  };
  const categoryMap = () => new Map(CATEGORIES.map((item) => [item.id, item]));
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  function blankBag() {
    return { version: ITEM_BAG_VERSION, capacity: null, profile: "balanced", counts: {}, reserves: {}, protected: {}, expirations: {}, custom_targets: {}, updated_at: "" };
  }

  function sanitizeBag(raw) {
    const out = blankBag();
    if (!raw || typeof raw !== "object" || Array.isArray(raw) || Number(raw.version) !== ITEM_BAG_VERSION) return out;
    out.capacity = num(raw.capacity);
    out.profile = PROFILE_IDS.includes(String(raw.profile)) ? String(raw.profile) : "balanced";
    const known = categoryMap();
    for (const [key, value] of Object.entries(raw.counts || {})) if (known.has(key)) out.counts[key] = num(value);
    for (const [key, value] of Object.entries(raw.reserves || {})) if (known.has(key)) out.reserves[key] = num(value) || 0;
    for (const [key, value] of Object.entries(raw.protected || {})) if (known.has(key)) out.protected[key] = value === true;
    for (const [key, value] of Object.entries(raw.expirations || {})) if (known.has(key)) out.expirations[key] = String(value || "").slice(0, 40);
    for (const [key, value] of Object.entries(raw.custom_targets || {})) {
      if (!known.has(key) || !value || typeof value !== "object") continue;
      const min = num(value.min), max = num(value.max);
      if (min !== null && max !== null && max >= min) out.custom_targets[key] = { min, max };
    }
    out.updated_at = String(raw.updated_at || "");
    return out;
  }

  function targetFor(category, profile, customTargets = {}) {
    if (profile === "custom" && customTargets[category.id]) return { ...customTargets[category.id], source: "custom" };
    const factor = Number(PROFILE_MULTIPLIERS[profile]?.[category.group] || 1);
    return { min: Math.round(category.baseline[0] * factor), max: Math.round(category.baseline[1] * factor), source: `profile:${profile}` };
  }

  function evaluateBag(raw, freeSlots = 50, now = new Date()) {
    const bag = sanitizeBag(raw);
    const rows = [], cleanupCandidates = [], expirations = [];
    let knownTotal = 0, unknownCount = 0;
    for (const category of CATEGORIES) {
      const count = Object.prototype.hasOwnProperty.call(bag.counts, category.id) ? bag.counts[category.id] : null;
      const reserve = bag.reserves[category.id] || 0;
      const protectedItem = bag.protected[category.id] === true || category.rare === true;
      const target = targetFor(category, bag.profile, bag.custom_targets);
      if (count === null) unknownCount += 1;
      else knownTotal += count;
      const floor = Math.max(target.min, reserve);
      const surplus = count === null || protectedItem ? 0 : Math.max(0, Math.floor(count - Math.max(floor, category.cleanup ?? floor)));
      const state = count === null ? "unknown" : count < floor ? "below-target" : count > target.max ? "above-target" : "within-target";
      rows.push({ id: category.id, label: category.label, count, reserve, protected: protectedItem, target, floor, surplus, state });
      if (surplus > 0) cleanupCandidates.push({ id: category.id, label: category.label, available: surplus, priority: category.cleanup ?? target.min });
      const expiresAt = bag.expirations[category.id];
      if (expiresAt) {
        const stamp = new Date(expiresAt);
        expirations.push({ id: category.id, label: category.label, expires_at: expiresAt, expired: Number.isFinite(stamp.getTime()) && stamp.getTime() <= now.getTime() });
      }
    }
    cleanupCandidates.sort((a, b) => a.priority - b.priority || a.label.localeCompare(b.label));
    let needed = Math.max(0, Math.floor(num(freeSlots) || 0));
    const cleanup = [];
    for (const candidate of cleanupCandidates) {
      if (needed <= 0) break;
      const amount = Math.min(candidate.available, needed);
      if (amount > 0) cleanup.push({ id: candidate.id, label: candidate.label, amount });
      needed -= amount;
    }
    return {
      bag, rows, cleanup, requested_slots: Math.max(0, Math.floor(num(freeSlots) || 0)),
      slots_identified: cleanup.reduce((sum, item) => sum + item.amount, 0),
      remaining_slots: needed, known_total: knownTotal, unknown_categories: unknownCount,
      estimated_free_space: bag.capacity === null || unknownCount > 0 ? null : Math.max(0, bag.capacity - knownTotal),
      expirations, missing_counts_are_unknown: true,
    };
  }

  function eventPreparation(calendar, now = new Date()) {
    const adjustments = [];
    for (const event of calendar?.events || []) {
      if (!event?.actionable_at_build || !event?.source || event.source?.freshness?.state !== "fresh") continue;
      const end = new Date(event.ends_at), start = new Date(event.starts_at);
      if (!Number.isFinite(end.getTime()) || !Number.isFinite(start.getTime()) || end < now) continue;
      const text = `${event.title || ""} ${(event.featured_species || []).join(" ")}`.toLocaleLowerCase();
      if (/community|spotlight|catch|wild/.test(text)) adjustments.push({ event_id: event.id, category: "catching", message: `Fresh event data supports raising catching-ball and berry reserves for ${event.title}.`, ends_at: event.ends_at });
      if (/raid|raid day/.test(text) || (event.raid_targets || []).length) adjustments.push({ event_id: event.id, category: "raid", message: `Fresh event data supports preserving raid and healing resources for ${event.title}.`, ends_at: event.ends_at });
    }
    return adjustments.slice(0, 8);
  }

  function loadBag(storage) {
    try {
      const raw = storage?.getItem(ITEM_BAG_KEY);
      return raw ? sanitizeBag(JSON.parse(raw)) : blankBag();
    } catch { return blankBag(); }
  }

  function saveBag(storage, raw, at = new Date().toISOString()) {
    const bag = sanitizeBag(raw);
    bag.updated_at = String(at);
    try { storage?.setItem(ITEM_BAG_KEY, JSON.stringify(bag)); return true; } catch { return false; }
  }

  function validateBagPayload(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw) || Number(raw.version) !== ITEM_BAG_VERSION) throw new Error("Item Bag Planner must use schema version 1.");
    return sanitizeBag(raw);
  }

  function wrapUnifiedLocalData(localApi) {
    if (!localApi || localApi.__itemBagWrapped) return localApi;
    const build = localApi.buildUnifiedBackup?.bind(localApi);
    const validate = localApi.validateUnifiedBackup?.bind(localApi);
    const restore = localApi.restoreUnifiedBackup?.bind(localApi);
    if (!build || !validate || !restore) return localApi;
    localApi.buildUnifiedBackup = (storage) => {
      const backup = build(storage), raw = storage?.getItem(ITEM_BAG_KEY);
      backup.namespaces = { ...(backup.namespaces || {}), item_bag: { storage_key: ITEM_BAG_KEY, schema_version: ITEM_BAG_VERSION, present: Boolean(raw), data: raw ? validateBagPayload(JSON.parse(raw)) : null } };
      return backup;
    };
    localApi.validateUnifiedBackup = (raw, storage, records = []) => {
      const base = validate(raw, storage, records), entry = raw?.namespaces?.item_bag;
      const preview = { added: [...(base.preview?.added || [])], replaced: [...(base.preview?.replaced || [])], absent: [...(base.preview?.absent || [])], ignored: [...(base.preview?.ignored || [])].filter((name) => name !== "item_bag") };
      if (!entry || !entry.present) preview.absent.push("item_bag");
      else {
        if (entry.storage_key !== ITEM_BAG_KEY || Number(entry.schema_version) !== ITEM_BAG_VERSION) throw new Error("Namespace item_bag has incompatible metadata.");
        validateBagPayload(entry.data);
        (storage?.getItem(ITEM_BAG_KEY) == null ? preview.added : preview.replaced).push("item_bag");
      }
      for (const key of Object.keys(preview)) preview[key] = [...new Set(preview[key])];
      return { ...base, preview };
    };
    localApi.restoreUnifiedBackup = (storage, raw, records = []) => {
      const entry = raw?.namespaces?.item_bag, before = storage?.getItem(ITEM_BAG_KEY) ?? null;
      const bag = entry?.present ? validateBagPayload(entry.data) : null;
      try {
        const result = restore(storage, raw, records);
        if (entry?.present) storage?.setItem(ITEM_BAG_KEY, JSON.stringify(bag));
        return result;
      } catch (error) {
        try {
          if (before === null) storage?.removeItem(ITEM_BAG_KEY);
          else storage?.setItem(ITEM_BAG_KEY, before);
        } catch { /* best effort */ }
        throw error;
      }
    };
    Object.defineProperty(localApi, "__itemBagWrapped", { value: true, enumerable: false });
    return localApi;
  }

  function readForm(root, bag) {
    const next = sanitizeBag(bag);
    next.capacity = num(root.document.getElementById("item-bag-capacity")?.value);
    next.profile = String(root.document.getElementById("item-bag-profile")?.value || "balanced");
    for (const category of CATEGORIES) {
      next.counts[category.id] = num(root.document.querySelector(`[data-bag-count="${category.id}"]`)?.value);
      next.reserves[category.id] = num(root.document.querySelector(`[data-bag-reserve="${category.id}"]`)?.value) || 0;
      next.protected[category.id] = Boolean(root.document.querySelector(`[data-bag-protected="${category.id}"]`)?.checked);
      if (category.expiration) next.expirations[category.id] = String(root.document.querySelector(`[data-bag-expiry="${category.id}"]`)?.value || "");
      if (next.profile === "custom") {
        const customMin = num(root.document.querySelector(`[data-bag-target-min="${category.id}"]`)?.value);
        const customMax = num(root.document.querySelector(`[data-bag-target-max="${category.id}"]`)?.value);
        if (customMin !== null && customMax !== null && customMax >= customMin) next.custom_targets[category.id] = { min: customMin, max: customMax };
      }
    }
    return next;
  }

  function render(root, bag, calendar = null) {
    const grid = root.document.getElementById("item-bag-grid"), result = root.document.getElementById("item-bag-root");
    if (!grid || !result) return;
    const capacity = root.document.getElementById("item-bag-capacity");
    const profile = root.document.getElementById("item-bag-profile");
    if (capacity) capacity.value = bag.capacity ?? "";
    if (profile) profile.value = bag.profile;
    const evaluated = evaluateBag(bag, root.document.getElementById("item-bag-free-slots")?.value || 50);
    grid.innerHTML = evaluated.rows.map((row) => {
      const category = categoryMap().get(row.id);
      const custom = bag.custom_targets[row.id] || { min: row.target.min, max: row.target.max };
      const customInputs = bag.profile === "custom" ? `<label>Target min <input inputmode="numeric" data-bag-target-min="${row.id}" value="${custom.min}"></label><label>Target max <input inputmode="numeric" data-bag-target-max="${row.id}" value="${custom.max}"></label>` : "";
      return `<fieldset class="trl-resource"><legend>${escapeHtml(row.label)}${category.rare ? " · protected rare" : ""}</legend><p class="trl-note">Target ${row.target.min}–${row.target.max}; reserve floor ${row.floor}.</p><label>Current <input inputmode="numeric" data-bag-count="${row.id}" value="${row.count ?? ""}" placeholder="unknown"></label><label>Reserve <input inputmode="numeric" data-bag-reserve="${row.id}" value="${row.reserve}"></label>${customInputs}<label><input type="checkbox" data-bag-protected="${row.id}"${bag.protected[row.id] || category.rare ? " checked" : ""}${category.rare ? " disabled" : ""}> Protect from cleanup</label>${category.expiration ? `<label>Expires <input type="datetime-local" data-bag-expiry="${row.id}" value="${escapeHtml(bag.expirations[row.id] || "")}"></label>` : ""}</fieldset>`;
    }).join("");
    const cleanup = evaluated.cleanup.map((item) => `<li>${escapeHtml(item.label)}: review discarding up to ${item.amount}</li>`).join("");
    const eventHtml = eventPreparation(calendar || {}).map((item) => `<li>${escapeHtml(item.message)}</li>`).join("");
    const expiryHtml = evaluated.expirations.map((item) => `<li>${escapeHtml(item.label)}: ${escapeHtml(item.expires_at)}${item.expired ? " · expired" : ""}</li>`).join("");
    result.innerHTML = `<section class="trl-card"><h2>Bag summary</h2><p>Known item total: ${evaluated.known_total}. Unknown categories: ${evaluated.unknown_categories}. ${evaluated.estimated_free_space === null ? "Free capacity remains unknown until all tracked counts are entered." : `Estimated free capacity: ${evaluated.estimated_free_space}.`}</p></section><section class="trl-card"><h2>Free-slot scenario</h2><p class="trl-note">Suggestions stop at profile targets and user reserves. Rare/protected categories are excluded.</p><ul>${cleanup || "<li>No supported cleanup surplus is available from entered counts.</li>"}</ul><p>Identified ${evaluated.slots_identified} of ${evaluated.requested_slots} requested slots.${evaluated.remaining_slots ? ` ${evaluated.remaining_slots} remain unresolved.` : ""}</p></section>${eventHtml ? `<section class="trl-card"><h2>Fresh event preparation</h2><ul>${eventHtml}</ul></section>` : ""}${expiryHtml ? `<section class="trl-card"><h2>Tracked expirations</h2><ul>${expiryHtml}</ul></section>` : ""}`;
  }

  async function install(root) {
    wrapUnifiedLocalData(root.CollectionLocalData);
    if (!root.document.getElementById("item-bag-grid")) return;
    const status = root.document.getElementById("item-bag-status");
    let bag = loadBag(root.localStorage), calendar = null;
    try {
      const response = await root.fetch("data/event-calendar.json");
      if (response.ok) calendar = await response.json();
    } catch { calendar = null; }
    render(root, bag, calendar);
    root.document.getElementById("item-bag-save")?.addEventListener("click", () => {
      bag = readForm(root, bag);
      const ok = saveBag(root.localStorage, bag);
      render(root, bag, calendar);
      if (status) status.textContent = ok ? "Item Bag plan saved locally and included in unified backup." : "Item Bag plan could not be saved in browser storage.";
    });
    for (const id of ["item-bag-profile", "item-bag-free-slots"]) {
      root.document.getElementById(id)?.addEventListener("change", () => {
        bag = readForm(root, bag);
        render(root, bag, calendar);
      });
    }
  }

  return {
    ITEM_BAG_KEY, ITEM_BAG_VERSION, PROFILE_IDS, CATEGORIES, PROFILE_MULTIPLIERS,
    blankBag, sanitizeBag, targetFor, evaluateBag, eventPreparation, loadBag, saveBag,
    validateBagPayload, wrapUnifiedLocalData, install,
  };
});
