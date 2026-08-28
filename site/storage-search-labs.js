"use strict";

(function exposeStorageSearchLabs(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionStorageSearchLabs = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const SEARCH_TEMPLATES_KEY = "pokemon-go-collection:search-templates:v1";
  const CLEANUP_KEY = "pokemon-go-collection:storage-cleanup:v1";
  const ENRICHMENT_KEY = "pokemon-go-collection:enrichment:v1";
  const ANNOTATIONS_KEY = "pokemon-go-collection:annotations:v2";
  const HARD_LOCAL_FIELDS = ["shiny", "costume", "background", "dynamax", "gigantamax", "reserved_trade", "legacy_move_review"];
  const PROTECT_LABELS = new Set(["Keep", "Trade", "Build later", "Elite TM candidate", "Remove Frustration", "Evolve during event"]);
  const TIER_ORDER = Object.freeze({ conservative: 0, balanced: 1, aggressive: 2, protected: 3 });

  const normalize = (value) => String(value ?? "").trim().toLocaleLowerCase();
  const recordId = (record) => String(record?.identity?.record_id || record?.record_id || "");
  const slug = (value) => normalize(value).replace(/[’']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "normal";
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  function safeJsonParse(text, fallback = null) {
    try { return JSON.parse(String(text || "")); } catch { return fallback; }
  }

  function registryMaps(registry) {
    const operators = Array.isArray(registry?.operators) ? registry.operators : [];
    const byId = new Map(operators.map((item) => [String(item.id), item]));
    const bare = new Map();
    const types = new Set();
    const regions = new Set();
    for (const operator of operators) {
      for (const token of operator.tokens || []) bare.set(normalize(token), operator);
      if (operator.id === "type") for (const token of operator.tokens || []) types.add(normalize(token));
      if (operator.id === "region") for (const token of operator.tokens || []) regions.add(normalize(token));
    }
    return { operators, byId, bare, types, regions };
  }

  function splitExpression(expression, registry) {
    const raw = String(expression || "").trim();
    const groupingUnsupported = /[()]/.test(raw) && registry?.boolean?.grouping_supported === false;
    const separators = new Set([...(registry?.boolean?.and || ["&"]), ...(registry?.boolean?.or || ["|", ",", ":", ";"])]);
    const terms = [];
    const joins = [];
    let buffer = "";
    for (const character of raw) {
      if (separators.has(character)) {
        terms.push(buffer.trim());
        joins.push(character);
        buffer = "";
      } else buffer += character;
    }
    terms.push(buffer.trim());
    return { raw, terms, joins, groupingUnsupported };
  }

  function numericRangeMatches(value) {
    return /^(?:\d+|-\d+|\d+-|\d+-\d+)$/.test(String(value || ""));
  }

  function validateTerm(rawTerm, registry) {
    const maps = registryMaps(registry);
    let raw = String(rawTerm || "").trim();
    if (!raw) return { valid: false, exact: false, raw, reason: "Empty search term." };
    let negated = false;
    if (raw.startsWith("!")) {
      negated = true;
      raw = raw.slice(1).trim();
      if (!raw) return { valid: false, exact: false, raw: rawTerm, reason: "Exclusion ! must be followed by a search term." };
    }
    const value = normalize(raw);
    const bareOperator = maps.bare.get(value);
    if (bareOperator) return { valid: true, exact: true, raw: rawTerm, token: raw, negated, operator_id: bareOperator.id, interpretation: bareOperator.label };

    if (/^\d+$/.test(value)) {
      const number = Number(value);
      if (number >= 1) return { valid: true, exact: true, raw: rawTerm, token: raw, negated, operator_id: "dex", interpretation: "Pokédex number" };
    }

    for (const operator of maps.operators) {
      const kind = String(operator.kind || "");
      if (kind === "numeric-range-prefix" && value.startsWith(normalize(operator.prefix))) {
        const suffix = value.slice(String(operator.prefix).length);
        return numericRangeMatches(suffix)
          ? { valid: true, exact: true, raw: rawTerm, token: raw, negated, operator_id: operator.id, interpretation: operator.label }
          : { valid: false, exact: false, raw: rawTerm, reason: `${operator.label} requires a documented numeric/range form.` };
      }
      if (kind === "integer-prefix" && value.startsWith(normalize(operator.prefix))) {
        const suffix = value.slice(String(operator.prefix).length);
        if (/^\d+$/.test(suffix) && Number(suffix) >= Number(operator.minimum || 0)) {
          return { valid: true, exact: true, raw: rawTerm, token: raw, negated, operator_id: operator.id, interpretation: operator.label };
        }
        return { valid: false, exact: false, raw: rawTerm, reason: `${operator.label} requires an integer in the reviewed range.` };
      }
      if (["enum-pattern", "prefixed-value-pattern"].includes(kind) && operator.pattern) {
        let pattern;
        try { pattern = new RegExp(operator.pattern, "i"); } catch { pattern = null; }
        if (pattern?.test(raw)) return { valid: true, exact: true, raw: rawTerm, token: raw, negated, operator_id: operator.id, interpretation: operator.label };
      }
    }

    if (raw.startsWith("+")) {
      return raw.length > 1
        ? { valid: true, exact: true, raw: rawTerm, token: raw, negated, operator_id: "family", interpretation: "Evolutionary family" }
        : { valid: false, exact: false, raw: rawTerm, reason: "Family search requires a Pokémon name after +." };
    }
    if (raw.startsWith("#")) {
      return raw.length > 1
        ? { valid: true, exact: true, raw: rawTerm, token: raw, negated, operator_id: "tag", interpretation: "Tag" }
        : { valid: false, exact: false, raw: rawTerm, reason: "Tag search requires a tag name after #." };
    }
    if (raw.startsWith("@")) {
      return raw.length > 1
        ? { valid: true, exact: true, raw: rawTerm, token: raw, negated, operator_id: "move", interpretation: "Move name/type" }
        : { valid: false, exact: false, raw: rawTerm, reason: "Move search requires a move name/type after @." };
    }

    if (/^(?:cp|hp|distance|age|year|mega|buddy)\b/i.test(raw) || /^(?:cp|hp|distance|age|year|mega|buddy)\S+/i.test(raw)) {
      return { valid: false, exact: false, raw: rawTerm, reason: "This looks like a documented operator but does not match a reviewed form." };
    }

    if (value && !/[&|,:;]/.test(value)) {
      return {
        valid: true,
        exact: false,
        raw: rawTerm,
        token: raw,
        negated,
        operator_id: "name-or-nickname",
        interpretation: "Bare text search",
        reason: "Bare text is supported, but the app cannot prove whether Pokémon GO will interpret it as a species name, nickname, type, region, or another documented bare term.",
      };
    }
    return { valid: false, exact: false, raw: rawTerm, reason: "Unsupported or ambiguous search syntax." };
  }

  function analyzeSearch(expression, registry) {
    const split = splitExpression(expression, registry);
    const analyzed = split.terms.map((term) => validateTerm(term, registry));
    const emptyTerm = analyzed.some((item) => !item.valid && item.reason === "Empty search term.");
    const invalid = analyzed.filter((item) => !item.valid);
    const approximate = analyzed.filter((item) => item.valid && !item.exact);
    const knownJoins = new Set([...(registry?.boolean?.and || ["&"]), ...(registry?.boolean?.or || ["|", ",", ":", ";"])]);
    const invalidJoin = split.joins.find((join) => !knownJoins.has(join));
    const valid = Boolean(split.raw) && !split.groupingUnsupported && !emptyTerm && !invalid.length && !invalidJoin;
    return {
      expression: split.raw,
      valid,
      verified_exact: valid && approximate.length === 0,
      grouping_supported: !split.groupingUnsupported,
      terms: analyzed,
      joins: split.joins,
      invalid,
      approximate,
      warnings: [
        ...(split.groupingUnsupported ? ["Parenthesized grouping is not documented by the reviewed official source and is intentionally rejected."] : []),
        ...approximate.map((item) => item.reason).filter(Boolean),
      ],
    };
  }

  function buildToken(operatorId, value, negated, registry) {
    const operator = registryMaps(registry).byId.get(String(operatorId));
    if (!operator) return { ok: false, reason: "Unknown operator." };
    const input = String(value || "").trim();
    let token = "";
    switch (operator.kind) {
      case "bare":
        token = input && (operator.tokens || []).map(normalize).includes(normalize(input)) ? input : String((operator.tokens || [])[0] || "");
        break;
      case "enum-bare":
        if (!(operator.tokens || []).map(normalize).includes(normalize(input))) return { ok: false, reason: `Choose one of: ${(operator.tokens || []).join(", ")}.` };
        token = input;
        break;
      case "numeric-range-prefix":
        if (!numericRangeMatches(input)) return { ok: false, reason: "Use a number, -maximum, minimum-, or minimum-maximum." };
        token = `${operator.prefix}${input}`;
        break;
      case "integer-prefix":
        if (!/^\d+$/.test(input) || Number(input) < Number(operator.minimum || 0)) return { ok: false, reason: "Enter a valid integer." };
        token = `${operator.prefix}${input}`;
        break;
      case "prefixed-value":
        if (!input) return { ok: false, reason: "This operator requires a value." };
        token = `${operator.prefix}${input}`;
        break;
      case "prefixed-value-pattern":
      case "enum-pattern": {
        if (!input) return { ok: false, reason: "This operator requires a value." };
        const candidates = [input];
        if (operator.id === "megalevel" && !/^mega/i.test(input)) candidates.push(`mega${input}`);
        if (operator.id === "buddy" && !/^buddy/i.test(input)) candidates.push(`buddy${input}`);
        let matched = null;
        for (const candidate of candidates) {
          try { if (new RegExp(operator.pattern, "i").test(candidate)) { matched = candidate; break; } } catch { /* invalid registry pattern */ }
        }
        if (!matched) return { ok: false, reason: `Value does not match the reviewed ${operator.label} form.` };
        token = matched;
        break;
      }
      case "integer-bare":
        if (!/^\d+$/.test(input) || Number(input) < Number(operator.minimum || 1)) return { ok: false, reason: "Enter a Pokédex number." };
        token = input;
        break;
      case "free-text":
        if (!input) return { ok: false, reason: "Enter search text." };
        token = input;
        break;
      default:
        return { ok: false, reason: `Builder does not support operator kind ${operator.kind}.` };
    }
    const full = `${negated ? "!" : ""}${token}`;
    const analyzed = validateTerm(full, registry);
    return analyzed.valid ? { ok: true, token: full, exact: analyzed.exact, operator } : { ok: false, reason: analyzed.reason };
  }

  function validateTemplatePayload(raw) {
    if (!raw || Number(raw.version) !== 1 || !Array.isArray(raw.templates)) return null;
    const names = new Set();
    const templates = [];
    for (const item of raw.templates) {
      const name = String(item?.name || "").trim();
      const expression = String(item?.expression || "").trim();
      const key = normalize(name);
      if (!name || !expression || names.has(key)) return null;
      names.add(key);
      templates.push({ name, expression, updated_at: String(item?.updated_at || "") });
    }
    return { version: 1, templates };
  }

  function loadTemplates(storage) {
    const parsed = safeJsonParse(storage?.getItem(SEARCH_TEMPLATES_KEY), null);
    return validateTemplatePayload(parsed) || { version: 1, templates: [] };
  }

  function saveTemplates(storage, payload) {
    const normalized = validateTemplatePayload(payload);
    if (!normalized) return false;
    try { storage?.setItem(SEARCH_TEMPLATES_KEY, JSON.stringify(normalized)); return true; } catch { return false; }
  }

  function saveTemplate(storage, name, expression, timestamp = new Date().toISOString()) {
    const payload = loadTemplates(storage);
    const cleanName = String(name || "").trim();
    const cleanExpression = String(expression || "").trim();
    if (!cleanName || !cleanExpression) return payload;
    const index = payload.templates.findIndex((item) => normalize(item.name) === normalize(cleanName));
    const entry = { name: cleanName, expression: cleanExpression, updated_at: timestamp };
    if (index >= 0) payload.templates[index] = entry;
    else payload.templates.push(entry);
    payload.templates.sort((a, b) => a.name.localeCompare(b.name));
    saveTemplates(storage, payload);
    return payload;
  }

  function normalizeCleanupState(raw) {
    if (!raw || Number(raw.version) !== 1 || !raw.decisions || typeof raw.decisions !== "object" || Array.isArray(raw.decisions)) return { version: 1, decisions: {}, config: {} };
    const decisions = {};
    for (const [id, value] of Object.entries(raw.decisions)) {
      if (["review", "approve", "exclude"].includes(String(value))) decisions[String(id)] = String(value);
    }
    return { version: 1, decisions, config: raw.config && typeof raw.config === "object" ? { ...raw.config } : {} };
  }

  function loadCleanupState(storage) {
    return normalizeCleanupState(safeJsonParse(storage?.getItem(CLEANUP_KEY), null));
  }

  function saveCleanupState(storage, state) {
    const normalized = normalizeCleanupState(state);
    try { storage?.setItem(CLEANUP_KEY, JSON.stringify(normalized)); return true; } catch { return false; }
  }

  function readLocalEnrichment(storage) {
    const raw = safeJsonParse(storage?.getItem(ENRICHMENT_KEY), null);
    return raw && Number(raw.version) === 1 && raw.records && typeof raw.records === "object" ? raw.records : {};
  }

  function readLocalAnnotations(storage) {
    const raw = safeJsonParse(storage?.getItem(ANNOTATIONS_KEY), null);
    return raw && Number(raw.version) === 2 && raw.records && typeof raw.records === "object" ? raw.records : {};
  }

  function scanAgeDays(record, referenceTimestamp) {
    const scan = Date.parse(record?.dates?.scan || "");
    const reference = Date.parse(referenceTimestamp || "");
    if (!Number.isFinite(scan) || !Number.isFinite(reference)) return null;
    return Math.max(0, Math.floor((reference - scan) / 86400000));
  }

  function isIncomplete(record) {
    return [record?.ivs?.average_percent, record?.ivs?.attack, record?.ivs?.defense, record?.ivs?.stamina,
      record?.level?.minimum, record?.moves?.fast, record?.moves?.charged]
      .some((value) => value === null || value === undefined || value === "");
  }

  function pvpScore(record) {
    const values = ["great", "ultra", "little"].map((league) => Number(record?.pvp?.[league]?.rank_percent)).filter(Number.isFinite);
    return values.length ? Math.max(...values) : 0;
  }

  function explicitHardProtections(record, enrichment, annotation, ivThreshold, decision) {
    const reasons = [];
    const status = record?.status || {};
    const ivs = record?.ivs || {};
    const shadow = normalize(status.shadow_purified);
    if (ivs.is_hundo) reasons.push("hundo");
    if (ivs.is_nundo) reasons.push("nundo");
    if (ivs.average_percent != null && Number(ivs.average_percent) >= Number(ivThreshold)) reasons.push(`IV ≥ ${Number(ivThreshold).toFixed(1)}%`);
    if (status.favorite) reasons.push("favorite");
    if (status.lucky) reasons.push("lucky");
    if (status.marked_for_pvp) reasons.push("marked for PvP");
    if (["shadow", "purified"].includes(shadow)) reasons.push(shadow);
    if (record?.moves?.charged_second) reasons.push("second Charged Move unlocked");
    if (slug(record?.form) !== "normal") reasons.push("unusual form");
    if (pvpScore(record) >= 98) reasons.push("strong PvP candidate");
    for (const field of HARD_LOCAL_FIELDS) {
      if (String(enrichment?.[field] || "unknown") === "yes") reasons.push(`user-confirmed ${field.replaceAll("_", " ")}`);
    }
    for (const label of annotation?.labels || []) if (PROTECT_LABELS.has(String(label))) reasons.push(`manual label: ${label}`);
    if (["protect", "blocked"].includes(String(decision?.status || ""))) reasons.push(`decision card: ${decision.status}`);
    return [...new Set(reasons)];
  }

  function uncertainties(record, enrichment, decision, referenceTimestamp) {
    const reasons = [];
    for (const field of HARD_LOCAL_FIELDS) if (!enrichment || String(enrichment[field] || "unknown") === "unknown") reasons.push(`unknown ${field.replaceAll("_", " ")}`);
    if (isIncomplete(record)) reasons.push("incomplete scan");
    const age = scanAgeDays(record, referenceTimestamp);
    if (age !== null && age > 30) reasons.push(`stale scan (${age} days)`);
    if ((decision?.unknown_protection_classes || []).length) reasons.push("decision card reports unsupported protection classes");
    return [...new Set(reasons)];
  }

  function groupKey(record) {
    return `${Number(record?.pokemon_number || 0)}:${slug(record?.form)}`;
  }

  function keeperScore(candidate) {
    const hard = candidate.hard_protections.length ? 1 : 0;
    return [hard, pvpScore(candidate.record), Number(candidate.record?.ivs?.average_percent || 0), Number(candidate.record?.cp || 0)];
  }

  function compareKeeper(left, right) {
    const a = keeperScore(left), b = keeperScore(right);
    for (let index = 0; index < a.length; index += 1) if (a[index] !== b[index]) return b[index] - a[index];
    return recordId(left.record).localeCompare(recordId(right.record));
  }

  function candidateTier(hardProtections, uncertaintyReasons) {
    if (hardProtections.length) return "protected";
    const collectorUnknown = uncertaintyReasons.some((reason) => reason.startsWith("unknown ") || reason.includes("unsupported protection"));
    if (collectorUnknown) return "aggressive";
    if (uncertaintyReasons.length) return "balanced";
    return "conservative";
  }

  function buildCleanupPlan(records, options = {}, context = {}) {
    const slotsNeeded = Math.max(1, Math.floor(Number(options.slotsNeeded) || 1));
    const ivThreshold = Math.min(100, Math.max(0, Number(options.ivThreshold ?? 90)));
    const referenceTimestamp = String(context.referenceTimestamp || new Date().toISOString());
    const enrichment = context.enrichment || {};
    const annotations = context.annotations || {};
    const decisionById = context.decisionById || new Map();
    const groups = new Map();
    for (const record of records || []) {
      const id = recordId(record);
      if (!id) continue;
      const key = groupKey(record);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(record);
    }
    const candidates = [];
    const protectedKeepers = [];
    for (const [key, members] of groups) {
      if (members.length < 2) continue;
      const reviewed = members.map((record) => {
        const id = recordId(record);
        const hard = explicitHardProtections(record, enrichment[id], annotations[id], ivThreshold, decisionById.get(id));
        const unknowns = uncertainties(record, enrichment[id], decisionById.get(id), referenceTimestamp);
        return { record, hard_protections: hard, uncertainties: unknowns };
      }).sort(compareKeeper);
      const keeper = reviewed[0];
      protectedKeepers.push({ group_key: key, record_id: recordId(keeper.record), reason: "At least one copy is retained as the group keeper before any cleanup review." });
      for (const item of reviewed.slice(1)) {
        const tier = candidateTier(item.hard_protections, item.uncertainties);
        candidates.push({
          group_key: key,
          group_count: members.length,
          keeper_record_id: recordId(keeper.record),
          record_id: recordId(item.record),
          pokemon_number: item.record.pokemon_number,
          name: item.record.name,
          form: item.record.form,
          cp: item.record.cp,
          iv_percent: item.record?.ivs?.average_percent ?? null,
          pvp_best_percent: pvpScore(item.record),
          tier,
          hard_protections: item.hard_protections,
          uncertainties: item.uncertainties,
          automatic_transfer_safe: false,
          action: "review_only",
        });
      }
    }
    candidates.sort((a, b) => TIER_ORDER[a.tier] - TIER_ORDER[b.tier]
      || a.hard_protections.length - b.hard_protections.length
      || a.uncertainties.length - b.uncertainties.length
      || Number(a.iv_percent || 0) - Number(b.iv_percent || 0)
      || Number(a.cp || 0) - Number(b.cp || 0)
      || a.record_id.localeCompare(b.record_id));
    const allowedTier = String(options.aggressiveness || "conservative");
    const allowedMax = TIER_ORDER[allowedTier] ?? 0;
    const available = candidates.filter((candidate) => TIER_ORDER[candidate.tier] <= allowedMax && candidate.tier !== "protected");
    const tierCounts = { conservative: 0, balanced: 0, aggressive: 0, protected: 0 };
    for (const candidate of candidates) tierCounts[candidate.tier] += 1;
    return {
      slots_needed: slotsNeeded,
      iv_threshold: ivThreshold,
      aggressiveness: allowedTier,
      tier_counts: tierCounts,
      available_review_candidates: available.length,
      enough_review_candidates: available.length >= slotsNeeded,
      candidates,
      group_keepers: protectedKeepers,
      automatic_transfer_safe: false,
      safety: "Candidates are review-only. Missing/unknown data never proves expendability, and the app never performs a transfer.",
    };
  }

  function cleanupLocator(candidate, registry, ivThreshold = 90) {
    const terms = [];
    if (candidate?.pokemon_number) terms.push(String(Number(candidate.pokemon_number)));
    if (candidate?.cp) terms.push(`cp${Number(candidate.cp)}`);
    terms.push("!favorite", "!lucky", "!shadow", "!purified", "!4*", "!shiny", "!costume", "!background", "!dynamax", "!gigantamax", "!@special", "!defender");
    const expression = terms.join("&");
    const analysis = analyzeSearch(expression, registry);
    const gaps = [
      "Pokémon GO search cannot select a canonical record ID; verify the exact Pokémon before acting.",
      `An arbitrary IV threshold such as ${Number(ivThreshold).toFixed(1)}% is not exactly representable by the reviewed official search contract.`,
      "Local notes, reservations, scan freshness, and unsupported progress states are not represented by this locator.",
      "Nundo protection is not encoded because excluding the individual 0-stat bands would over-exclude many non-nundos.",
    ];
    return { expression, syntax_verified: analysis.valid && analysis.verified_exact, exact_record_selector: false, representational_gaps: gaps };
  }

  function buildApprovedBatches(plan, cleanupState, registry) {
    const approved = plan.candidates.filter((candidate) => cleanupState?.decisions?.[candidate.record_id] === "approve" && candidate.tier !== "protected");
    return approved.map((candidate) => ({
      record_id: candidate.record_id,
      name: candidate.name,
      tier: candidate.tier,
      ...cleanupLocator(candidate, registry, plan.iv_threshold),
    }));
  }

  async function fetchJson(root, path) {
    const response = await root.fetch(path);
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return response.json();
  }

  function copyText(root, text) {
    if (root.navigator?.clipboard?.writeText) return root.navigator.clipboard.writeText(String(text));
    const area = root.document.createElement("textarea");
    area.value = String(text); area.setAttribute("readonly", ""); area.style.position = "fixed"; area.style.opacity = "0";
    root.document.body.append(area); area.select(); root.document.execCommand?.("copy"); area.remove();
    return Promise.resolve();
  }

  function renderSearchAnalysis(documentObject, analysis, registry) {
    const root = documentObject.getElementById("search-builder-root");
    if (!root) return;
    const status = analysis.valid ? (analysis.verified_exact ? "Verified against reviewed syntax" : "Valid with approximate bare-text interpretation") : "Needs correction";
    const source = registry?.source || {};
    const terms = analysis.terms.map((item) => `<li><code>${escapeHtml(item.raw)}</code> · ${item.valid ? escapeHtml(item.interpretation || "supported") : `<strong>invalid:</strong> ${escapeHtml(item.reason)}`}${item.valid && !item.exact ? " · approximate interpretation" : ""}</li>`).join("");
    root.innerHTML = `<section class="ssl-card"><h2>Interpretation</h2><p><strong>${escapeHtml(status)}</strong></p><p>${analysis.valid ? "No requested token was silently dropped." : "Fix every invalid term before using this as a verified handoff."}</p><ul>${terms}</ul>${analysis.warnings.length ? `<p class="ssl-warning">${escapeHtml(analysis.warnings.join(" "))}</p>` : ""}<p class="ssl-note">Source: ${escapeHtml(source.authority || "Official")} · ${escapeHtml(source.title || "Inventory search")} · reviewed ${escapeHtml(registry?.reviewed_at || "unknown")}. Parenthesized grouping is not claimed.</p></section>`;
  }

  function renderTemplates(root, payload, rawControl) {
    const target = root.document.getElementById("search-template-list");
    if (!target) return;
    target.innerHTML = payload.templates.length ? `<ul class="ssl-template-list">${payload.templates.map((item) => `<li><button type="button" data-template-name="${escapeHtml(item.name)}">${escapeHtml(item.name)}</button><code>${escapeHtml(item.expression)}</code></li>`).join("")}</ul>` : '<p class="ssl-note">No saved local templates.</p>';
    target.querySelectorAll("[data-template-name]").forEach((button) => button.addEventListener("click", () => {
      const item = payload.templates.find((entry) => entry.name === button.dataset.templateName);
      if (item && rawControl) { rawControl.value = item.expression; rawControl.dispatchEvent(new Event("input", { bubbles: true })); }
    }));
  }

  async function installSearchBuilder(root) {
    const mount = root.document.getElementById("search-builder-root");
    if (!mount) return;
    const registry = await fetchJson(root, "data/search-operator-registry.json");
    const operator = root.document.getElementById("search-operator");
    const value = root.document.getElementById("search-value");
    const negated = root.document.getElementById("search-negated");
    const join = root.document.getElementById("search-join");
    const raw = root.document.getElementById("search-raw");
    const status = root.document.getElementById("search-status");
    if (operator) operator.innerHTML = (registry.operators || []).map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)} (${escapeHtml(item.id)})</option>`).join("");
    const analyze = () => {
      const result = analyzeSearch(raw?.value || "", registry);
      renderSearchAnalysis(root.document, result, registry);
      if (status) status.textContent = result.valid ? (result.verified_exact ? "Search syntax verified against the reviewed registry." : "Search is valid, with at least one approximate bare-text interpretation.") : "Search contains unsupported or invalid syntax.";
      return result;
    };
    raw?.addEventListener("input", analyze);
    root.document.getElementById("search-add-term")?.addEventListener("click", () => {
      const built = buildToken(operator?.value, value?.value, Boolean(negated?.checked), registry);
      if (!built.ok) { if (status) status.textContent = built.reason; return; }
      const current = String(raw?.value || "").trim();
      if (raw) raw.value = current ? `${current}${join?.value || "&"}${built.token}` : built.token;
      if (value) value.value = "";
      analyze();
    });
    root.document.getElementById("search-copy")?.addEventListener("click", async () => {
      const result = analyze();
      if (!result.valid) { if (status) status.textContent = "Fix invalid syntax before copying."; return; }
      await copyText(root, result.expression);
      if (status) status.textContent = "Search copied. Verify the resulting Pokémon list in Pokémon GO before consequential actions.";
    });
    let templates = loadTemplates(root.localStorage);
    renderTemplates(root, templates, raw);
    root.document.getElementById("search-save-template")?.addEventListener("click", () => {
      const result = analyze();
      const name = root.document.getElementById("search-template-name")?.value || "";
      if (!result.valid || !String(name).trim()) { if (status) status.textContent = "Provide a name and a valid search before saving."; return; }
      templates = saveTemplate(root.localStorage, name, result.expression);
      renderTemplates(root, templates, raw);
      if (status) status.textContent = "Template saved locally and included in unified local-data backup.";
    });
    analyze();
  }

  function decisionMap(payload) {
    const cards = Array.isArray(payload?.cards) ? payload.cards : [];
    return new Map(cards.map((card) => [String(card.record_id || ""), card]).filter(([id]) => id));
  }

  function renderCleanup(root, plan, state, registry) {
    const mount = root.document.getElementById("storage-cleanup-root");
    if (!mount) return;
    const allowedMax = TIER_ORDER[plan.aggressiveness] ?? 0;
    const visible = plan.candidates.filter((candidate) => candidate.tier === "protected" || TIER_ORDER[candidate.tier] <= allowedMax);
    const summary = `<section class="ssl-card"><h2>Review capacity</h2><p><strong>${plan.available_review_candidates.toLocaleString()}</strong> review candidates are available at this aggressiveness for a target of <strong>${plan.slots_needed.toLocaleString()}</strong> slots.</p><p>${plan.enough_review_candidates ? "The target can be filled with review candidates, subject to manual in-game verification." : "The target cannot be filled at this risk level without reviewing more uncertain/protected records."}</p><p class="ssl-note">Tiers: conservative ${plan.tier_counts.conservative}, balanced ${plan.tier_counts.balanced}, aggressive ${plan.tier_counts.aggressive}, protected ${plan.tier_counts.protected}. No tier means automatically safe to transfer.</p></section>`;
    const cards = visible.map((candidate) => {
      const choice = state.decisions[candidate.record_id] || "review";
      const hard = candidate.hard_protections.length ? `<p><strong>Protections:</strong> ${escapeHtml(candidate.hard_protections.join(", "))}</p>` : "";
      const uncertain = candidate.uncertainties.length ? `<p><strong>Uncertainty:</strong> ${escapeHtml(candidate.uncertainties.join(", "))}</p>` : "";
      const locator = cleanupLocator(candidate, registry, plan.iv_threshold);
      return `<article class="ssl-candidate" data-tier="${escapeHtml(candidate.tier)}"><header><div><p class="ssl-eyebrow">${escapeHtml(candidate.tier)} review</p><h3>#${candidate.pokemon_number} ${escapeHtml(candidate.name)}${candidate.form ? ` · ${escapeHtml(candidate.form)}` : ""}</h3></div><span>CP ${candidate.cp ?? "?"} · IV ${candidate.iv_percent == null ? "?" : `${Number(candidate.iv_percent).toFixed(1)}%`}</span></header><p>Group has ${candidate.group_count} copies. Keeper: <code>${escapeHtml(candidate.keeper_record_id)}</code></p>${hard}${uncertain}<label>Local review decision <select data-cleanup-decision="${escapeHtml(candidate.record_id)}" ${candidate.tier === "protected" ? "disabled" : ""}><option value="review" ${choice === "review" ? "selected" : ""}>Keep in review</option><option value="approve" ${choice === "approve" ? "selected" : ""}>Approve for in-game verification queue</option><option value="exclude" ${choice === "exclude" ? "selected" : ""}>Exclude from cleanup</option></select></label><details><summary>Pokémon GO locator</summary><code>${escapeHtml(locator.expression)}</code><ul>${locator.representational_gaps.map((gap) => `<li>${escapeHtml(gap)}</li>`).join("")}</ul></details><p class="ssl-note">Canonical record: <code>${escapeHtml(candidate.record_id)}</code>. Automatic transfer safe: <strong>no</strong>.</p></article>`;
    }).join("");
    mount.innerHTML = summary + `<section class="ssl-results"><h2>Ranked review queue</h2>${cards || '<p class="ssl-note">No duplicate review candidates at this level.</p>'}</section>`;
    mount.querySelectorAll("[data-cleanup-decision]").forEach((select) => select.addEventListener("change", () => {
      state.decisions[select.dataset.cleanupDecision] = select.value;
      saveCleanupState(root.localStorage, state);
      const batches = buildApprovedBatches(plan, state, registry);
      const copy = root.document.getElementById("cleanup-copy-batches");
      if (copy) copy.disabled = batches.length === 0;
    }));
    const copy = root.document.getElementById("cleanup-copy-batches");
    if (copy) copy.disabled = buildApprovedBatches(plan, state, registry).length === 0;
  }

  async function installCleanup(root) {
    const mount = root.document.getElementById("storage-cleanup-root");
    if (!mount) return;
    const status = root.document.getElementById("cleanup-status");
    const [collection, decisions, registry] = await Promise.all([
      fetchJson(root, "data/pokemon.json"),
      fetchJson(root, "data/decisions/records.json").catch(() => ({ cards: [] })),
      fetchJson(root, "data/search-operator-registry.json"),
    ]);
    const records = collection.records || [];
    let state = loadCleanupState(root.localStorage);
    let currentPlan = null;
    const run = () => {
      const slotsNeeded = root.document.getElementById("cleanup-slots")?.value || 50;
      const ivThreshold = root.document.getElementById("cleanup-iv-threshold")?.value || 90;
      const aggressiveness = root.document.getElementById("cleanup-aggressiveness")?.value || "conservative";
      currentPlan = buildCleanupPlan(records, { slotsNeeded, ivThreshold, aggressiveness }, {
        enrichment: readLocalEnrichment(root.localStorage),
        annotations: readLocalAnnotations(root.localStorage),
        decisionById: decisionMap(decisions),
        referenceTimestamp: collection?.manifest?.generated_at_utc || new Date().toISOString(),
      });
      state.config = { slotsNeeded: Number(slotsNeeded), ivThreshold: Number(ivThreshold), aggressiveness };
      saveCleanupState(root.localStorage, state);
      renderCleanup(root, currentPlan, state, registry);
      if (status) status.textContent = currentPlan.enough_review_candidates
        ? `Review queue ready: ${currentPlan.available_review_candidates} candidates at or below ${aggressiveness} risk.`
        : `Only ${currentPlan.available_review_candidates} candidates are available at or below ${aggressiveness} risk for a ${currentPlan.slots_needed}-slot target.`;
    };
    root.document.getElementById("cleanup-run")?.addEventListener("click", run);
    root.document.getElementById("cleanup-copy-batches")?.addEventListener("click", async () => {
      if (!currentPlan) return;
      const batches = buildApprovedBatches(currentPlan, state, registry);
      if (!batches.length) return;
      const text = batches.map((batch, index) => `Batch ${index + 1}: ${batch.name} (${batch.tier})\n${batch.expression}\nManual gaps: ${batch.representational_gaps.join(" | ")}`).join("\n\n");
      await copyText(root, text);
      if (status) status.textContent = `Copied ${batches.length} approved locator batch${batches.length === 1 ? "" : "es"}. Each still requires exact in-game verification.`;
    });
    if (state.config.slotsNeeded) root.document.getElementById("cleanup-slots").value = state.config.slotsNeeded;
    if (state.config.ivThreshold != null) root.document.getElementById("cleanup-iv-threshold").value = state.config.ivThreshold;
    if (["conservative", "balanced", "aggressive"].includes(state.config.aggressiveness)) root.document.getElementById("cleanup-aggressiveness").value = state.config.aggressiveness;
    run();
  }

  async function install(root) {
    try { await installSearchBuilder(root); } catch (error) {
      const status = root.document?.getElementById("search-status");
      if (status) status.textContent = `Search Builder unavailable: ${error.message || error}`;
    }
    try { await installCleanup(root); } catch (error) {
      const status = root.document?.getElementById("cleanup-status");
      if (status) status.textContent = `Storage Cleanup unavailable: ${error.message || error}`;
    }
  }

  return {
    SEARCH_TEMPLATES_KEY, CLEANUP_KEY, ENRICHMENT_KEY, ANNOTATIONS_KEY, TIER_ORDER,
    registryMaps, splitExpression, validateTerm, analyzeSearch, buildToken,
    validateTemplatePayload, loadTemplates, saveTemplates, saveTemplate,
    normalizeCleanupState, loadCleanupState, saveCleanupState,
    explicitHardProtections, uncertainties, buildCleanupPlan, cleanupLocator, buildApprovedBatches,
    install,
  };
});
