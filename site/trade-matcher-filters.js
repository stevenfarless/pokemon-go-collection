"use strict";

(function installTradeMatcherFilters(root) {
  if (!root?.document) return;

  const normalize = (value) => String(value ?? "").trim().toLocaleLowerCase();
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

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

  function entriesForName(name, knowledge) {
    return knowledge.get(normalize(name)) || [];
  }

  function pairNames(article) {
    const heading = article.querySelector("h3")?.textContent || "";
    const parts = heading.split("↔").map((value) => value.trim()).filter(Boolean);
    return { heading: heading.trim(), names: parts.slice(0, 2) };
  }

  function pairMetadata(article, knowledge) {
    const { heading, names } = pairNames(article);
    const entries = names.flatMap((name) => entriesForName(name, knowledge));
    const families = [...new Set(entries.map((entry) => String(entry?.family?.id || "")).filter(Boolean))].sort();
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

  function install(rootObject) {
    const documentObject = rootObject.document;
    const fileInput = documentObject.getElementById("trade-guest-file");
    const results = documentObject.getElementById("trade-matcher-root");
    if (!fileInput || !results || documentObject.getElementById("trade-review-filters")) return;

    const panel = documentObject.createElement("section");
    panel.id = "trade-review-filters";
    panel.className = "trl-card";
    panel.setAttribute("aria-labelledby", "trade-review-filters-heading");
    panel.innerHTML = `<h2 id="trade-review-filters-heading">Review filters</h2>
      <p class="trl-note">Filters and manual exclusions stay in this tab and apply only to the current guest comparison.</p>
      <div class="trl-grid">
        <label>Goal species or form <input id="trade-goal-filter" type="search" autocomplete="off" placeholder="e.g. Eevee"></label>
        <label>Evolution family <select id="trade-family-filter"><option value="">Any family</option></select></label>
        <label>Rarity category <select id="trade-rarity-filter"><option value="">Any category</option><option value="legendary">Legendary</option><option value="mythical">Mythical</option><option value="ultra-beast">Ultra Beast</option><option value="unknown">Other / unknown</option></select></label>
      </div>
      <div class="trl-actions"><button id="trade-clear-exclusions" type="button">Clear manual exclusions</button></div>
      <p id="trade-filter-status" role="status">Filters become available after a guest comparison is loaded.</p>`;
    fileInput.closest("section")?.insertAdjacentElement("afterend", panel);

    const excluded = new Set();
    let knowledge = new Map();
    let applying = false;

    const refreshFamilyOptions = () => {
      const select = documentObject.getElementById("trade-family-filter");
      if (!select) return;
      const previous = select.value;
      const families = new Set();
      for (const article of results.querySelectorAll("article.trl-card")) {
        for (const family of pairMetadata(article, knowledge).families) families.add(family);
      }
      select.innerHTML = '<option value="">Any family</option>' + [...families].sort().map((family) => `<option value="${escapeHtml(family)}">${escapeHtml(family)}</option>`).join("");
      if ([...select.options].some((option) => option.value === previous)) select.value = previous;
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
            const controls = documentObject.createElement("p");
            controls.className = "trl-actions";
            controls.innerHTML = '<button type="button" data-trade-exclude>Exclude pair</button>';
            article.appendChild(controls);
          }
          const goalMatches = !filters.goal || normalize(metadata.heading).includes(filters.goal);
          const familyMatches = !filters.family || metadata.families.includes(filters.family);
          const rarityMatches = !filters.rarity || metadata.rarities.includes(filters.rarity);
          const visible = goalMatches && familyMatches && rarityMatches && !excluded.has(metadata.key);
          article.hidden = !visible;
          if (visible) shown += 1;
        }
        const status = documentObject.getElementById("trade-filter-status");
        if (status) status.textContent = articles.length ? `${shown} of ${articles.length} possible pair(s) shown. ${excluded.size} manually excluded.` : "Filters become available after a guest comparison is loaded.";
      } finally {
        applying = false;
      }
    };

    panel.addEventListener("input", apply);
    panel.addEventListener("change", apply);
    panel.addEventListener("click", (event) => {
      if (event.target?.id === "trade-clear-exclusions") {
        excluded.clear();
        apply();
      }
    });
    results.addEventListener("click", (event) => {
      const button = event.target?.closest?.("[data-trade-exclude]");
      if (!button) return;
      const article = button.closest("article.trl-card");
      const key = article?.dataset?.tradePairKey;
      if (key) excluded.add(key);
      apply();
    });

    const observer = new MutationObserver(() => {
      if (applying) return;
      refreshFamilyOptions();
      apply();
    });
    observer.observe(results, { childList: true, subtree: true });

    documentObject.getElementById("trade-clear-guest")?.addEventListener("click", () => {
      excluded.clear();
      for (const id of ["trade-goal-filter", "trade-family-filter", "trade-rarity-filter"]) {
        const control = documentObject.getElementById(id);
        if (control) control.value = "";
      }
      refreshFamilyOptions();
      apply();
    });

    documentObject.getElementById("trade-export-shortlist")?.addEventListener("click", (event) => {
      const filters = activeFilters(documentObject);
      if (!filters.goal && !filters.family && !filters.rarity && excluded.size === 0) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const headings = [...results.querySelectorAll("article.trl-card:not([hidden]) h3")].map((node) => node.textContent.trim());
      const text = ["# Private Trade Matcher filtered shortlist", "", "Review only. Confirm trade eligibility, cost, Lucky outcome, and post-trade stats in Pokémon GO.", "", ...(headings.length ? headings.map((heading) => `- ${heading}`) : ["- No pairs match the current review filters."]), ""].join("\n");
      const blob = new rootObject.Blob([text], { type: "text/markdown" });
      const url = rootObject.URL.createObjectURL(blob);
      const anchor = documentObject.createElement("a");
      anchor.href = url;
      anchor.download = "pokemon-go-trade-shortlist-filtered.md";
      anchor.click();
      rootObject.URL.revokeObjectURL(url);
    }, true);

    rootObject.fetch("data/knowledge/pokemon-go.json")
      .then((response) => { if (!response.ok) throw new Error(`knowledge returned HTTP ${response.status}`); return response.json(); })
      .then((payload) => { knowledge = buildKnowledge(payload); refreshFamilyOptions(); apply(); })
      .catch(() => { knowledge = new Map(); apply(); });
  }

  const start = () => install(root);
  if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})(typeof globalThis !== "undefined" ? globalThis : this);
