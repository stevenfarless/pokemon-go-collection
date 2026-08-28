"use strict";

(function exposeTradeResourceLabs(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionTradeResourceLabs = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const RESOURCE_KEY = "pokemon-go-collection:resource-vault:v1";
  const RESOURCE_VERSION = 1;
  const HISTORY_LIMIT = 12;
  const ENRICHMENT_KEY = "pokemon-go-collection:enrichment:v1";
  const LEGACY_BUDGET_KEY = "pokemon-go-collection:planner-budget:v1";
  const GUEST_UNKNOWNS = Object.freeze(["shiny", "costume", "background", "dynamax", "gigantamax", "favorite", "trade_history"]);
  const SCARCE = new Set(["rare_candy_xl", "elite_fast_tm", "elite_charged_tm", "silver_bottle_cap", "gold_bottle_cap"]);
  const DEFAULT_RESOURCES = Object.freeze([
    ["stardust", "Stardust"], ["rare_candy", "Rare Candy"], ["rare_candy_xl", "Rare Candy XL"],
    ["fast_tm", "Fast TM"], ["charged_tm", "Charged TM"], ["elite_fast_tm", "Elite Fast TM"],
    ["elite_charged_tm", "Elite Charged TM"], ["max_particles", "Max Particles"],
    ["silver_bottle_cap", "Silver Bottle Cap"], ["gold_bottle_cap", "Gold Bottle Cap"],
    ["raid_pass", "Raid Pass"], ["premium_battle_pass", "Premium Battle Pass"], ["remote_raid_pass", "Remote Raid Pass"],
  ]);

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  const normalize = (value) => String(value ?? "").trim().toLocaleLowerCase();
  const formKey = (value) => {
    const text = normalize(value);
    if (!text || ["normal", "none", "ordinary"].includes(text)) return "normal";
    const aliases = { alolan: "alola", galarian: "galar", hisuian: "hisui", paldean: "paldea" };
    const mapped = aliases[text] || text;
    return mapped.replace(/\bforme?\b/g, " ").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "normal";
  };
  const recordId = (record) => String(record?.identity?.record_id || record?.record_id || "");
  const speciesKey = (record) => `${Number(record?.pokemon_number ?? record?.dex ?? 0)}:${formKey(record?.form)}`;
  const numberOrNull = (value) => {
    if (value === null || value === undefined || String(value).trim() === "") return null;
    const number = Number(String(value).replaceAll(",", "").replace(/%$/, ""));
    return Number.isFinite(number) ? number : null;
  };
  const nonnegativeOrNull = (value) => {
    const number = numberOrNull(value);
    return number !== null && number >= 0 ? number : null;
  };

  function buildKnowledgeIndex(payload) {
    const byKey = new Map();
    const byDex = new Map();
    for (const item of payload?.entries || []) {
      const dex = Number(item.dex || item.pokemon_number || 0);
      const key = `${dex}:${formKey(item.form_key || item.form_label || item.form)}`;
      if (!byKey.has(key)) byKey.set(key, item);
      if (!byDex.has(dex)) byDex.set(dex, []);
      byDex.get(dex).push(item);
    }
    return { byKey, byDex };
  }

  function knowledgeFor(record, knowledge) {
    const exact = knowledge?.byKey?.get(speciesKey(record));
    if (exact) return exact;
    const values = knowledge?.byDex?.get(Number(record?.pokemon_number ?? record?.dex ?? 0)) || [];
    const ordinary = values.filter((item) => formKey(item.form_key || item.form_label) === "normal");
    return ordinary.length === 1 ? ordinary[0] : values.length === 1 ? values[0] : null;
  }

  function possibleSpecialTrade(entry) {
    if (!entry) return { state: "unknown", reason: "No exact species/form knowledge match." };
    const evidence = [entry.rarity, entry.category, entry.classification, ...(entry.tags || [])].filter(Boolean).map(normalize).join(" ");
    if (/legendary|mythical|ultra[ -]?beast/.test(evidence)) {
      return { state: "possible", reason: "Static species/category evidence can make this a Special Trade category, but exact eligibility and cost still require in-game confirmation." };
    }
    return { state: "unknown", reason: "No supported local fact proves whether this exact trade is Special; shiny/registration/history can change classification." };
  }

  function explicitTradeEvolution(entry) {
    if (!entry) return false;
    const walk = (value, key = "") => {
      if (value === null || value === undefined) return false;
      if (typeof value === "string") return /trade/i.test(key) && /trade/i.test(value);
      if (typeof value === "boolean") return /trade/i.test(key) && value === true;
      if (Array.isArray(value)) return value.some((child) => walk(child, key));
      if (typeof value === "object") return Object.entries(value).some(([childKey, child]) => walk(child, childKey));
      return false;
    };
    return walk(entry);
  }

  function guestRecordsFromParsed(parsed) {
    return (parsed?.rows || []).map((entry, index) => {
      const row = entry.values || {};
      return {
        guest_id: `guest-row-${index + 1}`,
        row_number: entry.rowNumber || index + 2,
        name: String(row.Name || "").trim(),
        pokemon_number: Number(numberOrNull(row["Pokemon Number"]) || 0),
        form: String(row.Form || "").trim(),
        cp: numberOrNull(row.CP),
        ivs: {
          attack: numberOrNull(row["Atk IV"]), defense: numberOrNull(row["Def IV"]), stamina: numberOrNull(row["Sta IV"]),
          average_percent: numberOrNull(row["IV Avg"]),
        },
        status: {
          lucky: ["1", "true", "yes", "y"].includes(normalize(row.Lucky)),
          shadow_purified: String(row["Shadow/Purified"] || "").trim(),
        },
        collector_unknown: [...GUEST_UNKNOWNS],
        source: "ephemeral-guest-csv",
      };
    }).filter((item) => item.name && item.pokemon_number > 0);
  }

  function canonicalProtectionReasons(record, enrichment = {}) {
    const reasons = [];
    const status = record?.status || {};
    const ivs = record?.ivs || {};
    if (status.favorite) reasons.push("favorite");
    if (status.lucky) reasons.push("lucky");
    if (["shadow", "purified"].includes(normalize(status.shadow_purified))) reasons.push(normalize(status.shadow_purified));
    if (ivs.is_hundo) reasons.push("hundo");
    if (ivs.is_nundo) reasons.push("nundo");
    const local = enrichment?.records?.[recordId(record)] || {};
    for (const [field, label] of [
      ["shiny", "user-confirmed shiny"], ["costume", "user-confirmed costume"], ["background", "user-confirmed background"],
      ["dynamax", "user-confirmed Dynamax"], ["gigantamax", "user-confirmed Gigantamax"], ["reserved_trade", "reserved for trade"],
      ["legacy_move_review", "legacy/exclusive move review"],
    ]) if (local[field] === "yes") reasons.push(label);
    return [...new Set(reasons)];
  }

  function groupBySpecies(records) {
    const map = new Map();
    for (const record of records || []) {
      const key = speciesKey(record);
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(record);
    }
    return map;
  }

  function compareCanonicalReviewValue(a, b) {
    const protectedA = canonicalProtectionReasons(a).length;
    const protectedB = canonicalProtectionReasons(b).length;
    if (protectedA !== protectedB) return protectedB - protectedA;
    const pvp = (record) => Math.max(0, ...Object.values(record?.pvp || {}).map((item) => Number(item?.rank_percent || 0)));
    if (pvp(a) !== pvp(b)) return pvp(b) - pvp(a);
    if (Number(a?.ivs?.average_percent || 0) !== Number(b?.ivs?.average_percent || 0)) return Number(b?.ivs?.average_percent || 0) - Number(a?.ivs?.average_percent || 0);
    if (Number(a?.cp || 0) !== Number(b?.cp || 0)) return Number(b?.cp || 0) - Number(a?.cp || 0);
    return recordId(a).localeCompare(recordId(b));
  }

  function buildTradeMatcher(playerA, playerB, knowledgePayload = {}, enrichment = {}) {
    const knowledge = buildKnowledgeIndex(knowledgePayload);
    const groupsA = groupBySpecies(playerA);
    const groupsB = groupBySpecies(playerB);
    const allKeys = [...new Set([...groupsA.keys(), ...groupsB.keys()])].sort();
    const aOffers = [], bOffers = [];
    for (const key of allKeys) {
      const a = groupsA.get(key) || [], b = groupsB.get(key) || [];
      if (a.length >= 2 && b.length === 0) {
        const ordered = [...a].sort(compareCanonicalReviewValue);
        const keeper = ordered[0];
        const candidates = ordered.slice(1).map((record) => ({
          record_id: recordId(record), name: record.name, pokemon_number: record.pokemon_number, form: record.form, cp: record.cp,
          review_only: true, safe_to_trade: false, protection_reasons: canonicalProtectionReasons(record, enrichment),
        }));
        const entry = knowledgeFor(keeper, knowledge);
        aOffers.push({ key, name: keeper.name, pokemon_number: keeper.pokemon_number, form: keeper.form, owned_count: a.length, other_player_count: 0, keeper_record_id: recordId(keeper), candidates, possible_special_trade: possibleSpecialTrade(entry), trade_evolution_supported: explicitTradeEvolution(entry) });
      }
      if (b.length >= 2 && a.length === 0) {
        const sample = b[0], entry = knowledgeFor(sample, knowledge);
        bOffers.push({ key, name: sample.name, pokemon_number: sample.pokemon_number, form: sample.form, owned_count: b.length, other_player_count: 0,
          candidates: b.map((record) => ({ guest_id: record.guest_id, row_number: record.row_number, cp: record.cp, review_only: true, safe_to_trade: false, collector_unknown: [...GUEST_UNKNOWNS] })),
          possible_special_trade: possibleSpecialTrade(entry), trade_evolution_supported: explicitTradeEvolution(entry),
        });
      }
    }
    const pairCount = Math.min(aOffers.length, bOffers.length, 50);
    const mutualWins = [];
    for (let index = 0; index < pairCount; index += 1) {
      mutualWins.push({ id: `mutual-${index + 1}`, a_gives: aOffers[index], b_gives: bOffers[index], state: "review", exact_post_trade_stats_guaranteed: false, lucky_guaranteed: false, exact_stardust_cost: null });
    }
    return {
      possible_mutual_wins: mutualWins,
      player_a_offers: aOffers,
      player_b_offers: bOffers,
      privacy: { guest_persisted: false, guest_uploaded: false, guest_identity: "ephemeral" },
      warnings: [
        "Duplicate count creates a review candidate, never proof that a Pokémon is expendable.",
        "Player B collector attributes such as shiny, costume, background, Max state, favorite, and trade history remain unknown unless separately confirmed.",
        "Trade eligibility, Special Trade classification, Stardust cost, Lucky outcome, and post-trade IV/CP must be confirmed in Pokémon GO when required inputs are unknown.",
      ],
    };
  }

  function tradeSearch(record, workflows) {
    if (workflows?.narrowRecordSearch && recordId(record)) return workflows.narrowRecordSearch(record);
    const dex = Number(record?.pokemon_number || 0);
    return { search: dex > 0 ? String(dex) : String(record?.name || ""), exact: false, gaps: ["Exact record identity and unsupported collector attributes require manual verification."] };
  }

  function blankVault() {
    return { version: RESOURCE_VERSION, balances: {}, commitments: [], plans: [], history: [], updated_at: "" };
  }

  function sanitizeBalance(raw) {
    return { amount: nonnegativeOrNull(raw?.amount), reserve: nonnegativeOrNull(raw?.reserve) || 0, expires_at: String(raw?.expires_at || ""), note: String(raw?.note || "").slice(0, 300) };
  }

  function sanitizeCosts(raw) {
    const output = {};
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return output;
    for (const [key, value] of Object.entries(raw)) {
      const amount = nonnegativeOrNull(value);
      if (String(key) && amount !== null && amount > 0) output[String(key)] = amount;
    }
    return output;
  }

  function sanitizeVault(raw) {
    const output = blankVault();
    if (!raw || typeof raw !== "object" || Number(raw.version) !== RESOURCE_VERSION) return output;
    for (const [key, value] of Object.entries(raw.balances || {})) if (key) output.balances[String(key)] = sanitizeBalance(value);
    output.commitments = (Array.isArray(raw.commitments) ? raw.commitments : []).slice(0, 100).map((item, index) => ({
      id: String(item?.id || `commitment-${index + 1}`), name: String(item?.name || "Commitment").slice(0, 120), resource: String(item?.resource || ""), amount: nonnegativeOrNull(item?.amount) || 0, active: item?.active !== false,
    })).filter((item) => item.resource && item.amount > 0);
    output.plans = (Array.isArray(raw.plans) ? raw.plans : []).slice(0, 100).map((item, index) => ({
      id: String(item?.id || `plan-${index + 1}`), name: String(item?.name || "Plan").slice(0, 120), priority: Number.isFinite(Number(item?.priority)) ? Number(item.priority) : 0,
      selected: item?.selected !== false, objective: String(item?.objective || "").slice(0, 120), costs: sanitizeCosts(item?.costs),
    }));
    output.history = (Array.isArray(raw.history) ? raw.history : []).slice(-HISTORY_LIMIT).map((item) => ({ at: String(item?.at || ""), balances: item?.balances && typeof item.balances === "object" ? item.balances : {} }));
    output.updated_at = String(raw.updated_at || "");
    return output;
  }

  function migrateLegacyBudget(vault, legacy) {
    const next = sanitizeVault(vault);
    if (next.balances.stardust?.amount !== null && next.balances.stardust?.amount !== undefined) return next;
    const dust = nonnegativeOrNull(legacy?.dust ?? legacy?.stardust);
    if (dust !== null) next.balances.stardust = { amount: dust, reserve: 0, expires_at: "", note: "Migrated from legacy planner budget" };
    return next;
  }

  function evaluateVault(raw) {
    const vault = sanitizeVault(raw);
    const remaining = {}, commitmentsByResource = {}, conflicts = [], expirations = [];
    for (const [key, balance] of Object.entries(vault.balances)) {
      if (balance.expires_at) expirations.push({ resource: key, expires_at: balance.expires_at });
      remaining[key] = balance.amount === null ? null : balance.amount - balance.reserve;
      if (remaining[key] !== null && remaining[key] < 0) conflicts.push({ kind: "reserve-exceeds-balance", resource: key, shortage: Math.abs(remaining[key]) });
    }
    for (const commitment of vault.commitments.filter((item) => item.active)) commitmentsByResource[commitment.resource] = (commitmentsByResource[commitment.resource] || 0) + commitment.amount;
    for (const [resource, amount] of Object.entries(commitmentsByResource)) {
      if (!Object.prototype.hasOwnProperty.call(remaining, resource)) remaining[resource] = null;
      if (remaining[resource] !== null) {
        remaining[resource] -= amount;
        if (remaining[resource] < 0) conflicts.push({ kind: "commitments-overdraw", resource, shortage: Math.abs(remaining[resource]) });
      }
    }

    const planResults = [];
    const ordered = vault.plans.map((plan, index) => ({ plan, index })).filter(({ plan }) => plan.selected)
      .sort((a, b) => b.plan.priority - a.plan.priority || a.index - b.index || a.plan.id.localeCompare(b.plan.id));
    for (const { plan } of ordered) {
      let blocked = false, unknown = false;
      const shortages = [], before = {}, after = {}, scarce = [];
      for (const [resource, cost] of Object.entries(plan.costs)) {
        if (!Object.prototype.hasOwnProperty.call(remaining, resource)) remaining[resource] = null;
        before[resource] = remaining[resource];
        if (remaining[resource] === null) unknown = true;
        else if (remaining[resource] < cost) { blocked = true; shortages.push({ resource, needed: cost, available: remaining[resource], shortage: cost - remaining[resource] }); }
        if (SCARCE.has(resource)) scarce.push(resource);
      }
      const state = blocked ? "blocked" : unknown ? "unknown" : "feasible";
      if (!blocked) {
        for (const [resource, cost] of Object.entries(plan.costs)) {
          if (remaining[resource] !== null) remaining[resource] -= cost;
          after[resource] = remaining[resource];
        }
      } else {
        for (const resource of Object.keys(plan.costs)) after[resource] = remaining[resource];
        conflicts.push({ kind: "plan-overdraw", plan_id: plan.id, shortages });
      }
      planResults.push({ id: plan.id, name: plan.name, priority: plan.priority, state, costs: plan.costs, before, after, shortages, scarce_resource_warnings: scarce });
    }
    return { balances: vault.balances, commitments: vault.commitments, plan_results: planResults, remaining, conflicts, expirations, unknown_is_zero: false };
  }

  function snapshotVault(raw, at = new Date().toISOString()) {
    const vault = sanitizeVault(raw);
    const balances = {};
    for (const [key, value] of Object.entries(vault.balances)) balances[key] = { amount: value.amount, reserve: value.reserve, expires_at: value.expires_at };
    vault.history = [...vault.history, { at: String(at), balances }].slice(-HISTORY_LIMIT);
    vault.updated_at = String(at);
    return vault;
  }

  function loadVault(storage) {
    try {
      const raw = storage?.getItem(RESOURCE_KEY);
      let vault = raw ? sanitizeVault(JSON.parse(raw)) : blankVault();
      if (!raw) {
        const legacy = storage?.getItem(LEGACY_BUDGET_KEY);
        if (legacy) vault = migrateLegacyBudget(vault, JSON.parse(legacy));
      }
      return vault;
    } catch { return blankVault(); }
  }

  function saveVault(storage, raw, at = new Date().toISOString()) {
    const vault = sanitizeVault(raw); vault.updated_at = String(at);
    try { storage?.setItem(RESOURCE_KEY, JSON.stringify(vault)); return true; } catch { return false; }
  }

  function validateVaultPayload(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw) || Number(raw.version) !== RESOURCE_VERSION) throw new Error("Resource Vault must use schema version 1.");
    if (!raw.balances || typeof raw.balances !== "object" || Array.isArray(raw.balances)) throw new Error("Resource Vault balances are missing or invalid.");
    if (!Array.isArray(raw.commitments) || !Array.isArray(raw.plans) || !Array.isArray(raw.history)) throw new Error("Resource Vault commitments, plans, and history must be arrays.");
    return sanitizeVault(raw);
  }

  function buildUnifiedBackupWithVault(localApi, storage) {
    if (!localApi?.buildUnifiedBackup) throw new Error("Unified local-data backup engine is unavailable.");
    const backup = localApi.buildUnifiedBackup(storage);
    const raw = storage?.getItem(RESOURCE_KEY);
    backup.namespaces = { ...(backup.namespaces || {}) };
    backup.namespaces.resource_vault = {
      storage_key: RESOURCE_KEY,
      schema_version: RESOURCE_VERSION,
      present: raw !== null && raw !== undefined && raw !== "",
      data: raw ? validateVaultPayload(JSON.parse(raw)) : null,
    };
    return backup;
  }

  function validateUnifiedBackupWithVault(localApi, raw, storage, records = []) {
    if (!localApi?.validateUnifiedBackup) throw new Error("Unified local-data restore engine is unavailable.");
    const base = localApi.validateUnifiedBackup(raw, storage, records);
    const entry = raw?.namespaces?.resource_vault;
    let vault = null;
    const preview = {
      added: [...(base.preview?.added || [])], replaced: [...(base.preview?.replaced || [])],
      absent: [...(base.preview?.absent || [])], ignored: [...(base.preview?.ignored || [])].filter((name) => name !== "resource_vault"),
    };
    if (!entry) preview.absent.push("resource_vault");
    else {
      if (entry.storage_key !== RESOURCE_KEY || Number(entry.schema_version) !== RESOURCE_VERSION) throw new Error("Namespace resource_vault has incompatible metadata.");
      if (!entry.present) preview.absent.push("resource_vault");
      else {
        vault = validateVaultPayload(entry.data);
        (storage?.getItem(RESOURCE_KEY) == null ? preview.added : preview.replaced).push("resource_vault");
      }
    }
    for (const key of ["added", "replaced", "absent", "ignored"]) preview[key] = [...new Set(preview[key])];
    return { base, vault, vault_entry: entry || null, preview };
  }

  function restoreUnifiedBackupWithVault(localApi, storage, raw, records = []) {
    const validated = validateUnifiedBackupWithVault(localApi, raw, storage, records);
    const keys = new Set([RESOURCE_KEY]);
    for (const entry of Object.values(raw?.namespaces || {})) if (entry?.storage_key) keys.add(String(entry.storage_key));
    const before = new Map([...keys].map((key) => [key, storage?.getItem(key) ?? null]));
    try {
      localApi.restoreUnifiedBackup(storage, raw, records);
      if (validated.vault_entry?.present) storage?.setItem(RESOURCE_KEY, JSON.stringify(validated.vault));
      return validated.preview;
    } catch (error) {
      for (const [key, previous] of before.entries()) {
        try { if (previous === null) storage?.removeItem(key); else storage?.setItem(key, previous); } catch { /* best effort */ }
      }
      throw new Error(`Unified restore failed without accepting partial Resource Vault state: ${error.message || error}`);
    }
  }

  function downloadText(root, filename, text, type = "text/plain") {
    const blob = new root.Blob([String(text)], { type });
    const url = root.URL.createObjectURL(blob);
    const anchor = root.document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click(); root.URL.revokeObjectURL(url);
  }

  function shortlistMarkdown(result) {
    const lines = ["# Private Trade Matcher shortlist", "", "Review only. Confirm eligibility, Special Trade status, Stardust cost, Lucky status, and post-trade stats in Pokémon GO.", ""];
    for (const item of result?.possible_mutual_wins || []) lines.push(`- Player A reviews giving ${item.a_gives.name}${item.a_gives.form ? ` (${item.a_gives.form})` : ""}; Player B reviews giving ${item.b_gives.name}${item.b_gives.form ? ` (${item.b_gives.form})` : ""}.`);
    if (!(result?.possible_mutual_wins || []).length) lines.push("- No supported mutual-win pairs were found from duplicate/missing species-form evidence.");
    return lines.join("\n") + "\n";
  }

  async function fetchJson(root, path) {
    const response = await root.fetch(path);
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return response.json();
  }

  function renderTrade(root, result) {
    const target = root.document.getElementById("trade-matcher-root");
    if (!target) return;
    const rows = (result.possible_mutual_wins || []).map((item) => {
      const a = item.a_gives, b = item.b_gives;
      const exactA = (a.candidates || []).map((candidate) => candidate.record_id).filter(Boolean).join(", ") || "none";
      return `<article class="trl-card"><h3>${escapeHtml(a.name)} ↔ ${escapeHtml(b.name)}</h3><p><strong>Player A reviews:</strong> ${escapeHtml(a.name)}${a.form ? ` · ${escapeHtml(a.form)}` : ""} (${a.owned_count} owned). Exact candidate IDs: <code>${escapeHtml(exactA)}</code>.</p><p><strong>Player B reviews:</strong> ${escapeHtml(b.name)}${b.form ? ` · ${escapeHtml(b.form)}` : ""} (${b.owned_count} guest rows). Collector attributes remain unknown.</p><p class="trl-note">Review only. No guaranteed Lucky outcome, Stardust cost, or post-trade IV/CP.</p></article>`;
    }).join("");
    target.innerHTML = `<section><h2>Possible mutual wins</h2>${rows || '<div class="trl-empty">No mutual duplicate/missing pair is supported by this guest file.</div>'}</section><details class="trl-card"><summary>Safety and uncertainty</summary><ul>${result.warnings.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}</ul></details>`;
  }

  async function installTrade(root) {
    const fileInput = root.document.getElementById("trade-guest-file");
    if (!fileInput) return;
    const status = root.document.getElementById("trade-guest-status"), clear = root.document.getElementById("trade-clear-guest"), exportButton = root.document.getElementById("trade-export-shortlist");
    let guestRecords = null, result = null, sourceText = null;
    try {
      const [collection, preflight, knowledge] = await Promise.all([fetchJson(root, "data/pokemon.json"), fetchJson(root, "data/preflight-contract.json"), fetchJson(root, "data/knowledge/species-index.json")]);
      let enrichment = {};
      try { enrichment = JSON.parse(root.localStorage?.getItem(ENRICHMENT_KEY) || "{}"); } catch { enrichment = {}; }
      fileInput.addEventListener("change", async () => {
        const file = fileInput.files?.[0]; if (!file) return;
        try {
          sourceText = await file.text();
          const workflows = root.CollectionActionWorkflows;
          if (!workflows?.parseCsv || !workflows?.analyzePreflight) throw new Error("Shared Scan Inbox preflight engine is unavailable.");
          const analysis = workflows.analyzePreflight(file.name, sourceText, preflight, { records: collection.records || [], export_timestamp: collection.manifest?.export_timestamp });
          if (!analysis.accepted) throw new Error(analysis.errors.map((item) => item.message).slice(0, 4).join(" ") || "Guest CSV preflight failed.");
          guestRecords = guestRecordsFromParsed(workflows.parseCsv(sourceText));
          result = buildTradeMatcher(collection.records || [], guestRecords, knowledge, enrichment);
          sourceText = null;
          renderTrade(root, result);
          if (status) status.textContent = `${guestRecords.length} guest rows parsed in memory. ${result.possible_mutual_wins.length} possible mutual-win pair(s) need review.`;
          if (exportButton) exportButton.disabled = false;
        } catch (error) {
          sourceText = null; guestRecords = null; result = null;
          if (status) status.textContent = `Guest comparison unavailable: ${error.message || error}`;
          if (exportButton) exportButton.disabled = true;
        }
      });
      clear?.addEventListener("click", () => {
        sourceText = null; guestRecords = null; result = null; fileInput.value = "";
        const target = root.document.getElementById("trade-matcher-root"); if (target) target.innerHTML = "";
        if (status) status.textContent = "Guest session cleared. No guest collection data is retained by this lab.";
        if (exportButton) exportButton.disabled = true;
      });
      exportButton?.addEventListener("click", () => { if (result) downloadText(root, "pokemon-go-trade-shortlist.md", shortlistMarkdown(result), "text/markdown"); });
    } catch (error) { if (status) status.textContent = `Trade Matcher unavailable: ${error.message || error}`; }
  }

  function readVaultForm(documentObject, vault) {
    const next = sanitizeVault(vault);
    for (const [key] of DEFAULT_RESOURCES) {
      const amount = documentObject.querySelector(`[data-resource-amount="${key}"]`);
      const reserve = documentObject.querySelector(`[data-resource-reserve="${key}"]`);
      const expiry = documentObject.querySelector(`[data-resource-expiry="${key}"]`);
      next.balances[key] = { amount: nonnegativeOrNull(amount?.value), reserve: nonnegativeOrNull(reserve?.value) || 0, expires_at: String(expiry?.value || ""), note: next.balances[key]?.note || "" };
    }
    return next;
  }

  function renderVaultEditor(root, vault) {
    const grid = root.document.getElementById("resource-fast-grid"); if (!grid) return;
    grid.innerHTML = DEFAULT_RESOURCES.map(([key, label]) => {
      const item = vault.balances[key] || {};
      return `<fieldset class="trl-resource"><legend>${escapeHtml(label)}${SCARCE.has(key) ? " · scarce" : ""}</legend><label>Balance <input inputmode="numeric" data-resource-amount="${key}" value="${item.amount ?? ""}" placeholder="unknown"></label><label>Reserve <input inputmode="numeric" data-resource-reserve="${key}" value="${item.reserve ?? 0}"></label>${/bottle_cap/.test(key) ? `<label>Expires <input type="datetime-local" data-resource-expiry="${key}" value="${escapeHtml(item.expires_at || "")}"></label>` : ""}</fieldset>`;
    }).join("");
  }

  function renderVaultResult(root, vault) {
    const target = root.document.getElementById("resource-vault-root"); if (!target) return;
    const result = evaluateVault(vault);
    const planHtml = result.plan_results.map((plan) => `<article class="trl-card" data-state="${escapeHtml(plan.state)}"><h3>${escapeHtml(plan.name)} · ${escapeHtml(plan.state)}</h3><p>${Object.entries(plan.costs).map(([resource, amount]) => `${escapeHtml(resource)} ${amount}`).join(" · ") || "No costs entered"}</p>${plan.shortages.length ? `<p>Shortage: ${plan.shortages.map((item) => `${escapeHtml(item.resource)} ${item.shortage}`).join(", ")}</p>` : ""}${plan.scarce_resource_warnings.length ? `<p class="trl-warning">Opportunity-cost review: ${escapeHtml(plan.scarce_resource_warnings.join(", "))}.</p>` : ""}</article>`).join("");
    const conflicts = result.conflicts.map((item) => `<li>${escapeHtml(item.kind)} · ${escapeHtml(item.resource || item.plan_id || "resource")}</li>`).join("");
    target.innerHTML = `<section><h2>Plan evaluation</h2><p class="trl-note">Unknown balances remain unknown. Feasible means only that all entered/reserved resource arithmetic fits this local what-if model.</p>${planHtml || '<div class="trl-empty">No selected plans. The vault remains useful as optional balance/reserve storage.</div>'}${conflicts ? `<div class="trl-warning"><strong>Conflicts</strong><ul>${conflicts}</ul></div>` : ""}</section><section class="trl-card"><h2>Commitments and plans</h2><div id="resource-plan-editor"></div></section>`;
    const editor = root.document.getElementById("resource-plan-editor");
    if (editor) editor.innerHTML = vault.plans.map((plan, index) => `<div class="trl-plan"><label>Name <input data-plan-name="${index}" value="${escapeHtml(plan.name)}"></label><label>Priority <input inputmode="numeric" data-plan-priority="${index}" value="${plan.priority}"></label><label>Resource <select data-plan-resource="${index}">${DEFAULT_RESOURCES.map(([key, label]) => `<option value="${key}"${Object.hasOwn(plan.costs, key) ? " selected" : ""}>${escapeHtml(label)}</option>`).join("")}</select></label><label>Cost <input inputmode="numeric" data-plan-cost="${index}" value="${Object.values(plan.costs)[0] ?? ""}"></label><label><input type="checkbox" data-plan-selected="${index}"${plan.selected ? " checked" : ""}> Include</label></div>`).join("");
  }

  function readPlans(documentObject, vault) {
    const next = sanitizeVault(vault);
    next.plans = next.plans.map((plan, index) => {
      const name = documentObject.querySelector(`[data-plan-name="${index}"]`)?.value ?? plan.name;
      const priority = Number(documentObject.querySelector(`[data-plan-priority="${index}"]`)?.value ?? plan.priority) || 0;
      const resource = String(documentObject.querySelector(`[data-plan-resource="${index}"]`)?.value || Object.keys(plan.costs)[0] || "stardust");
      const cost = nonnegativeOrNull(documentObject.querySelector(`[data-plan-cost="${index}"]`)?.value);
      const selected = Boolean(documentObject.querySelector(`[data-plan-selected="${index}"]`)?.checked);
      return { ...plan, name: String(name).slice(0, 120), priority, selected, costs: cost && cost > 0 ? { [resource]: cost } : {} };
    });
    return next;
  }

  async function installVault(root) {
    if (!root.document.getElementById("resource-fast-grid")) return;
    const status = root.document.getElementById("resource-status");
    let vault = loadVault(root.localStorage);
    renderVaultEditor(root, vault); renderVaultResult(root, vault);
    root.document.getElementById("resource-save")?.addEventListener("click", () => {
      vault = readPlans(root.document, readVaultForm(root.document, vault));
      const ok = saveVault(root.localStorage, vault); renderVaultEditor(root, vault); renderVaultResult(root, vault);
      if (status) status.textContent = ok ? "Resource Vault saved locally. No canonical collection or in-game balance was changed." : "Resource Vault could not be saved in browser storage.";
    });
    root.document.getElementById("resource-add-plan")?.addEventListener("click", () => {
      vault = readPlans(root.document, readVaultForm(root.document, vault));
      vault.plans.push({ id: `plan-${Date.now()}`, name: "New plan", priority: 0, selected: true, objective: "", costs: {} }); renderVaultResult(root, vault);
    });
    root.document.getElementById("resource-snapshot")?.addEventListener("click", () => {
      vault = readPlans(root.document, readVaultForm(root.document, vault)); vault = snapshotVault(vault); saveVault(root.localStorage, vault); renderVaultResult(root, vault);
      if (status) status.textContent = `Saved local balance snapshot ${vault.history.length}/${HISTORY_LIMIT}.`;
    });
  }

  function installUnifiedBackupExtension(root) {
    if (!root.document?.getElementById("local-data-backup") || !root.CollectionLocalData) return;
    const status = root.document.getElementById("local-data-preview");
    let pending = null;
    const recordsPromise = fetchJson(root, "data/pokemon.json").then((payload) => payload.records || []).catch(() => []);
    root.document.addEventListener("click", async (event) => {
      const id = event.target?.id;
      if (id === "export-local-data") {
        event.preventDefault(); event.stopImmediatePropagation();
        try {
          const backup = buildUnifiedBackupWithVault(root.CollectionLocalData, root.localStorage);
          downloadText(root, "pokemon-go-collection-local-data.json", JSON.stringify(backup, null, 2) + "\n", "application/json");
          if (status) status.textContent = "Unified backup exported, including Resource Vault state when present.";
        } catch (error) { if (status) status.textContent = `Backup export failed: ${error.message || error}`; }
      } else if (id === "apply-local-data-restore") {
        event.preventDefault(); event.stopImmediatePropagation();
        if (!pending) return;
        try {
          const records = await recordsPromise;
          const preview = restoreUnifiedBackupWithVault(root.CollectionLocalData, root.localStorage, pending, records);
          pending = null;
          event.target.disabled = true;
          if (status) status.textContent = `Restore applied atomically. Added: ${preview.added.join(", ") || "none"}. Replaced: ${preview.replaced.join(", ") || "none"}. Resource Vault is included in this unified restore.`;
        } catch (error) { if (status) status.textContent = `Restore failed: ${error.message || error}`; }
      }
    }, true);
    root.document.addEventListener("change", async (event) => {
      if (event.target?.id !== "restore-local-data") return;
      event.preventDefault(); event.stopImmediatePropagation();
      try {
        const file = event.target.files?.[0]; if (!file) return;
        pending = JSON.parse(await file.text());
        const records = await recordsPromise;
        const { preview } = validateUnifiedBackupWithVault(root.CollectionLocalData, pending, root.localStorage, records);
        const apply = root.document.getElementById("apply-local-data-restore"); if (apply) apply.disabled = false;
        if (status) status.textContent = `Restore preview: add ${preview.added.join(", ") || "none"}; replace ${preview.replaced.join(", ") || "none"}; absent ${preview.absent.join(", ") || "none"}; ignore ${preview.ignored.join(", ") || "none"}. No local data has changed yet.`;
      } catch (error) {
        pending = null; const apply = root.document.getElementById("apply-local-data-restore"); if (apply) apply.disabled = true;
        if (status) status.textContent = `Restore validation failed: ${error.message || error}`;
      }
    }, true);
  }

  function install(root) { installTrade(root); installVault(root); installUnifiedBackupExtension(root); }

  return {
    RESOURCE_KEY, RESOURCE_VERSION, HISTORY_LIMIT, GUEST_UNKNOWNS, DEFAULT_RESOURCES,
    formKey, speciesKey, buildKnowledgeIndex, knowledgeFor, possibleSpecialTrade, explicitTradeEvolution,
    guestRecordsFromParsed, canonicalProtectionReasons, groupBySpecies, buildTradeMatcher, tradeSearch, shortlistMarkdown,
    blankVault, sanitizeBalance, sanitizeCosts, sanitizeVault, validateVaultPayload, migrateLegacyBudget, evaluateVault, snapshotVault, loadVault, saveVault,
    buildUnifiedBackupWithVault, validateUnifiedBackupWithVault, restoreUnifiedBackupWithVault,
    install,
  };
});
