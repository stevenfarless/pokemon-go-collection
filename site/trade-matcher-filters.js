"use strict";

(function exposeTradeMatcherFilters(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionTradeMatcherFilters = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const normalize = (value) => String(value ?? "").trim().toLocaleLowerCase();
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  const triBool = (value) => normalize(value) === "yes" ? true : normalize(value) === "no" ? false : null;

  function friendFacts(friend = {}) {
    const facts = {};
    for (const key of ["lucky_friend", "forever_friend", "remote_trade_available"]) {
      const value = triBool(friend[key]);
      if (value !== null) facts[key] = value;
    }
    const used = triBool(friend.remote_trade_used_today);
    if (used !== null) facts.remote_trades_completed_today = used ? 1 : 0;
    return facts;
  }

  function pokemonFacts(record = {}, enrichment = {}, guest = false) {
    const facts = {};
    const status = normalize(record?.status?.shadow_purified);
    if (["shadow", "1"].includes(status)) facts.shadow = true;
    else if (["normal", "purified", "2", ""].includes(status)) facts.shadow = false;
    const dex = Number(record?.pokemon_number || 0);
    if (dex === 808) {
      facts.mythical = true;
      facts.mythical_trade_blocked = false;
    }
    if (!guest) {
      const local = enrichment?.records?.[String(record?.identity?.record_id || "")] || {};
      for (const [source, target] of [["already_traded", "previously_traded"], ["shiny", "shiny"]]) {
        const value = triBool(local[source]);
        if (value !== null) facts[target] = value;
      }
    }
    return facts;
  }

  function aggregateEvaluations(values = []) {
    if (!values.length) return "unknown";
    if (values.some((item) => item?.state === "eligible")) return "eligible";
    if (values.some((item) => item?.state === "unknown")) return "unknown";
    return "blocked";
  }

  function evaluatePair(pair, context = {}) {
    const rules = context.rules;
    if (!rules?.evaluateTrade) throw new Error("Shared trade-rule engine is unavailable.");
    const mode = context.mode || "in_person";
    const friend = friendFacts(context.friend || {});
    const trainer = { level: context.trainer_level === "" ? null : context.trainer_level };
    const registry = context.registry || {};
    const enrichment = context.enrichment || {};
    const a = (pair?.a_gives?.candidates || []).map((candidate) => {
      const record = context.player_a?.get?.(candidate.record_id) || {};
      return { id: candidate.record_id, evaluation: rules.evaluateTrade(mode, pokemonFacts(record, enrichment, false), friend, trainer, registry) };
    });
    const b = (pair?.b_gives?.candidates || []).map((candidate) => {
      const record = context.player_b?.get?.(candidate.guest_id) || {};
      return { id: candidate.guest_id || `guest-row-${candidate.row_number || "?"}`, evaluation: rules.evaluateTrade(mode, pokemonFacts(record, enrichment, true), friend, trainer, registry) };
    });
    const aState = aggregateEvaluations(a.map((item) => item.evaluation));
    const bState = aggregateEvaluations(b.map((item) => item.evaluation));
    const state = aState === "blocked" || bState === "blocked" ? "blocked" : aState === "unknown" || bState === "unknown" ? "unknown" : "eligible";
    return { state, mode, a, b, lucky_friend: friend.lucky_friend === true, exact_stardust_cost: null, post_trade_stats_guaranteed: false };
  }

  function rarityFor(entry) {
    const tags = (entry?.source_tags || []).map(normalize).join(" ");
    if (/ultra[ -]?beast/.test(tags)) return "ultra-beast";
    if (/mythical/.test(tags)) return "mythical";
    if (/legendary/.test(tags)) return "legendary";
    return "unknown";
  }

  function buildKnowledge(payload) {
    const byName = new Map();
    for (const entry of payload?.entries || []) {
      for (const value of [entry.display_name, entry.base_name]) {
        const key = normalize(value);
        if (!key) continue;
        if (!byName.has(key)) byName.set(key, []);
        byName.get(key).push(entry);
      }
    }
    return byName;
  }

  function entriesForName(name, knowledge) { return knowledge.get(normalize(name)) || []; }

  function pairNames(article) {
    const heading = article.querySelector("h3")?.textContent || "";
    const parts = heading.split("↔").map((value) => value.trim()).filter(Boolean);
    return { heading: heading.trim(), names: parts.slice(0, 2) };
  }

  function pairMetadata(article, knowledge) {
    const { heading, names } = pairNames(article);
    const entries = names.flatMap((name) => entriesForName(name, knowledge));
    const families = [...new Set(entries.map((entry) => String(entry?.family?.id || entry?.family_id || "")).filter(Boolean))].sort();
    const rarities = [...new Set(entries.map(rarityFor))];
    return { key: normalize(heading), heading, families, rarities };
  }

  function activeFilters(documentObject) {
    return {
      goal: normalize(documentObject.getElementById("trade-goal-filter")?.value),
      family: String(documentObject.getElementById("trade-family-filter")?.value || ""),
      rarity: String(documentObject.getElementById("trade-rarity-filter")?.value || ""),
    };
  }

  async function fetchJson(root, path) {
    const response = await root.fetch(path);
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return response.json();
  }

  function loadScript(root, src, globalName) {
    if (root[globalName]) return Promise.resolve(root[globalName]);
    return new Promise((resolve, reject) => {
      const script = root.document.createElement("script");
      script.src = src;
      script.addEventListener("load", () => root[globalName] ? resolve(root[globalName]) : reject(new Error(`${globalName} did not initialize.`)), { once: true });
      script.addEventListener("error", () => reject(new Error(`${src} could not be loaded.`)), { once: true });
      root.document.head.appendChild(script);
    });
  }

  async function runtime(root) {
    let assets = {};
    try { assets = (await fetchJson(root, "data/build-manifest.json"))?.assets || {}; } catch { assets = {}; }
    const workflows = await loadScript(root, assets.action_workflows || "assets/action-workflows.js", "CollectionActionWorkflows");
    const stateApi = await loadScript(root, assets.friendship_trade_state || "friendship-trade-state.js", "CollectionFriendshipTradeState");
    const rules = await loadScript(root, assets.trade_rules || "trade-rules.js", "CollectionTradeRules");
    const [collection, registry] = await Promise.all([
      fetchJson(root, "data/pokemon.json"),
      fetchJson(root, "data/knowledge/trade-rules.v1.json"),
    ]);
    return { workflows, stateApi, rules, collection, registry };
  }

  function install(rootObject) {
    const documentObject = rootObject.document;
    const fileInput = documentObject.getElementById("trade-guest-file");
    const results = documentObject.getElementById("trade-matcher-root");
    if (!fileInput || !results || documentObject.getElementById("trade-review-filters")) return;

    const panel = documentObject.createElement("section");
    panel.id = "trade-review-filters";
    panel.className = "trl-card";
    panel.setAttribute("aria-labelledby", "trade-review-filters-heading");
    panel.innerHTML = `<h2 id="trade-review-filters-heading">Review filters and eligibility</h2>
      <p class="trl-note">Filters, selected friend, and manual exclusions stay in this tab. Eligibility uses the shared reviewed trade-rule engine and keeps missing facts unknown.</p>
      <div class="trl-grid">
        <label>Local friend <select id="trade-friend-select"><option value="">No saved friend selected</option></select></label>
        <label>Trade mode <select id="trade-mode-select"><option value="in_person">In person</option><option value="remote">Remote Trade</option></select></label>
        <label>Trainer level <input id="trade-trainer-level" type="number" min="1" step="1" placeholder="unknown"></label>
        <label>Goal species or form <input id="trade-goal-filter" type="search" autocomplete="off" placeholder="e.g. Eevee"></label>
        <label>Evolution family <select id="trade-family-filter"><option value="">Any family</option></select></label>
        <label>Rarity category <select id="trade-rarity-filter"><option value="">Any category</option><option value="legendary">Legendary</option><option value="mythical">Mythical</option><option value="ultra-beast">Ultra Beast</option><option value="unknown">Other / unknown</option></select></label>
      </div>
      <div class="trl-actions"><button id="trade-clear-exclusions" type="button">Clear manual exclusions</button></div>
      <p id="trade-filter-status" role="status">Loading shared trade-rule dependencies…</p>`;
    fileInput.closest("section")?.insertAdjacentElement("afterend", panel);
    fileInput.disabled = true;

    const excluded = new Set();
    let knowledge = new Map(), applying = false, comparison = null, guest = [], runtimeState = null, enrichment = {};

    const refreshFamilyOptions = () => {
      const select = documentObject.getElementById("trade-family-filter");
      if (!select) return;
      const previous = select.value;
      const families = new Set();
      for (const article of results.querySelectorAll("article.trl-card")) for (const family of pairMetadata(article, knowledge).families) families.add(family);
      select.innerHTML = '<option value="">Any family</option>' + [...families].sort().map((family) => `<option value="${escapeHtml(family)}">${escapeHtml(family)}</option>`).join("");
      if ([...select.options].some((option) => option.value === previous)) select.value = previous;
    };

    const eligibilityContext = () => {
      if (!runtimeState) return null;
      const friendState = runtimeState.stateApi.read(rootObject.localStorage);
      const selected = documentObject.getElementById("trade-friend-select")?.value || "";
      const friend = friendState.friends.find((item) => item.id === selected) || {};
      const playerA = new Map((runtimeState.collection.records || []).map((record) => [String(record?.identity?.record_id || ""), record]));
      const playerB = new Map(guest.map((record) => [record.guest_id, record]));
      return { rules: runtimeState.rules, registry: runtimeState.registry, friend, mode: documentObject.getElementById("trade-mode-select")?.value || "in_person", trainer_level: documentObject.getElementById("trade-trainer-level")?.value || "", player_a: playerA, player_b: playerB, enrichment };
    };

    const decorateEligibility = () => {
      if (!comparison || !runtimeState) return;
      const context = eligibilityContext();
      const articles = [...results.querySelectorAll("article.trl-card")];
      for (const [index, article] of articles.entries()) {
        const pair = comparison.possible_mutual_wins?.[index];
        if (!pair) continue;
        const evaluated = evaluatePair(pair, context);
        article.querySelector("[data-trade-eligibility]")?.remove();
        const details = documentObject.createElement("div");
        details.dataset.tradeEligibility = "true";
        details.className = "trl-note";
        const summary = (item) => runtimeState.rules.summarizeEligibility(item.evaluation);
        details.innerHTML = `<p><strong>${escapeHtml(evaluated.mode === "remote" ? "Remote Trade" : "In-person trade")} eligibility:</strong> ${escapeHtml(evaluated.state)}. ${evaluated.lucky_friend ? "Selected friend is marked Lucky Friend. " : ""}Exact Stardust cost and post-trade IV/CP remain unclaimed.</p><ul>${evaluated.a.map((item) => `<li>Player A <code>${escapeHtml(item.id)}</code>: ${escapeHtml(summary(item))}</li>`).join("")}${evaluated.b.map((item) => `<li>Player B ${escapeHtml(item.id)}: ${escapeHtml(summary(item))}</li>`).join("")}</ul><p>Rules reviewed ${escapeHtml(runtimeState.registry.reviewed_at || "unknown date")}.</p>`;
        article.appendChild(details);
      }
    };

    const apply = () => {
      if (applying) return;
      applying = true;
      try {
        const filters = activeFilters(documentObject);
        const articles = [...results.querySelectorAll("article.trl-card")];
        let shown = 0;
        for (const article of articles) {
          const metadata = pairMetadata(article, knowledge);
          article.dataset.tradePairKey = metadata.key;
          if (!article.querySelector("[data-trade-exclude]")) {
            const controls = documentObject.createElement("p"); controls.className = "trl-actions";
            controls.innerHTML = '<button type="button" data-trade-exclude>Exclude pair</button>'; article.appendChild(controls);
          }
          const visible = (!filters.goal || normalize(metadata.heading).includes(filters.goal)) && (!filters.family || metadata.families.includes(filters.family)) && (!filters.rarity || metadata.rarities.includes(filters.rarity)) && !excluded.has(metadata.key);
          article.hidden = !visible; if (visible) shown += 1;
        }
        decorateEligibility();
        const status = documentObject.getElementById("trade-filter-status");
        if (status) status.textContent = runtimeState ? (articles.length ? `${shown} of ${articles.length} possible pair(s) shown. ${excluded.size} manually excluded.` : "Eligibility runtime ready. Choose a guest CSV to compare.") : "Loading shared trade-rule dependencies…";
      } finally { applying = false; }
    };

    panel.addEventListener("input", apply);
    panel.addEventListener("change", apply);
    panel.addEventListener("click", (event) => { if (event.target?.id === "trade-clear-exclusions") { excluded.clear(); apply(); } });
    results.addEventListener("click", (event) => { const button = event.target?.closest?.("[data-trade-exclude]"); if (!button) return; const key = button.closest("article.trl-card")?.dataset?.tradePairKey; if (key) excluded.add(key); apply(); });

    const observer = new MutationObserver(() => { if (applying) return; refreshFamilyOptions(); apply(); });
    observer.observe(results, { childList: true, subtree: true });

    documentObject.getElementById("trade-clear-guest")?.addEventListener("click", () => {
      excluded.clear(); comparison = null; guest = [];
      for (const id of ["trade-goal-filter", "trade-family-filter", "trade-rarity-filter"]) { const control = documentObject.getElementById(id); if (control) control.value = ""; }
      refreshFamilyOptions(); apply();
    });

    documentObject.getElementById("trade-export-shortlist")?.addEventListener("click", (event) => {
      const filters = activeFilters(documentObject);
      if (!filters.goal && !filters.family && !filters.rarity && excluded.size === 0) return;
      event.preventDefault(); event.stopImmediatePropagation();
      const headings = [...results.querySelectorAll("article.trl-card:not([hidden]) h3")].map((node) => node.textContent.trim());
      const text = ["# Private Trade Matcher filtered shortlist", "", "Review only. Eligibility details come from the reviewed shared rule engine; unresolved facts still require confirmation.", "", ...(headings.length ? headings.map((heading) => `- ${heading}`) : ["- No pairs match the current review filters."]), ""].join("\n");
      const blob = new rootObject.Blob([text], { type: "text/markdown" }); const url = rootObject.URL.createObjectURL(blob); const anchor = documentObject.createElement("a"); anchor.href = url; anchor.download = "pokemon-go-trade-shortlist-filtered.md"; anchor.click(); rootObject.URL.revokeObjectURL(url);
    }, true);

    const ready = runtime(rootObject).then((state) => {
      runtimeState = state;
      try { enrichment = JSON.parse(rootObject.localStorage?.getItem("pokemon-go-collection:enrichment:v1") || "{}"); } catch { enrichment = {}; }
      const friendSelect = documentObject.getElementById("trade-friend-select");
      const friends = state.stateApi.read(rootObject.localStorage).friends;
      if (friendSelect) friendSelect.innerHTML = '<option value="">No saved friend selected</option>' + friends.map((friend) => `<option value="${escapeHtml(friend.id)}">${escapeHtml(friend.label || friend.id)}</option>`).join("");
      fileInput.disabled = false; apply(); return state;
    }).catch((error) => {
      const status = documentObject.getElementById("trade-filter-status");
      if (status) status.textContent = `Trade eligibility runtime unavailable: ${error.message || error}`;
      const guestStatus = documentObject.getElementById("trade-guest-status");
      if (guestStatus) guestStatus.textContent = "Guest comparison disabled until the shared parser and trade-rule runtime load successfully.";
      throw error;
    });

    fileInput.addEventListener("change", async () => {
      const file = fileInput.files?.[0]; if (!file) return;
      try {
        const state = await ready;
        const parsed = state.workflows.parseCsv(await file.text());
        guest = rootObject.CollectionTradeResourceLabs.guestRecordsFromParsed(parsed);
        const knowledgePayload = await fetchJson(rootObject, "data/knowledge/species-index.json");
        knowledge = buildKnowledge(knowledgePayload);
        comparison = rootObject.CollectionTradeResourceLabs.buildTradeMatcher(state.collection.records || [], guest, knowledgePayload, enrichment);
        rootObject.setTimeout?.(() => { refreshFamilyOptions(); apply(); }, 0);
      } catch { comparison = null; guest = []; }
    });

    fetchJson(rootObject, "data/knowledge/pokemon-go.json").then((payload) => { knowledge = buildKnowledge(payload); refreshFamilyOptions(); apply(); }).catch(() => apply());
  }

  return { triBool, friendFacts, pokemonFacts, aggregateEvaluations, evaluatePair, buildKnowledge, pairMetadata, activeFilters, install };
});
