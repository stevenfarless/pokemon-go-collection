"use strict";

(function exposeInsights(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionInsights = api;
  if (root?.document) api.install(root);
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function number(value, fallback = "—") {
    return value === null || value === undefined || value === ""
      ? fallback
      : Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  function percent(value) {
    return value === null || value === undefined ? "—" : `${Number(value).toFixed(2)}%`;
  }

  function label(name, form) {
    return form ? `${name} (${form})` : name;
  }

  function overviewCards(data) {
    const overview = data.overview;
    const cards = [
      [overview.pokemon_count, "Pokémon records", "./"],
      [overview.distinct_species_forms, "species/form groups", "./?sort=name%3Aasc%2Ccp%3Adesc"],
      [overview.single_copy_groups, "single-copy groups", "#single-copy"],
      [overview.duplicate_groups, "duplicate groups", "#duplicates"],
      [overview.highest_cp, "highest CP", `./?cpmin=${overview.highest_cp}&cpmax=${overview.highest_cp}`],
    ];
    return cards.map(([value, text, href]) => `<a class="insight-card" href="${escapeHtml(href)}"><strong>${number(value)}</strong><span>${escapeHtml(text)}</span></a>`).join("");
  }

  function statusCards(cards) {
    return cards.map((card) => `<a class="insight-card" href="${escapeHtml(card.href)}"><strong>${number(card.count)}</strong><span>${escapeHtml(card.label)}</span></a>`).join("");
  }

  function distributionBars(items) {
    const maximum = Math.max(1, ...items.map((item) => item.group_count));
    return items.map((item) => {
      const width = Math.max(1, Math.round((item.group_count / maximum) * 100));
      return `<div class="insight-bar"><span>${number(item.copies)} ${item.copies === 1 ? "copy" : "copies"}</span><span class="insight-bar-track" aria-hidden="true"><span class="insight-bar-fill" style="width:${width}%"></span></span><strong>${number(item.group_count)} groups</strong></div>`;
    }).join("");
  }

  function duplicateRows(items) {
    return items.slice(0, 30).map((item) => `<tr><td><a href="${escapeHtml(item.href)}">#${String(item.pokemon_number).padStart(4, "0")} ${escapeHtml(label(item.name, item.form))}</a></td><td>${number(item.count)}</td><td>${number(item.highest_cp)}</td><td>${percent(item.best_iv_percent)}</td></tr>`).join("");
  }

  function singleRows(items) {
    return items.slice(0, 40).map((item) => `<tr><td><a href="${escapeHtml(item.href)}">#${String(item.pokemon_number).padStart(4, "0")} ${escapeHtml(label(item.name, item.form))}</a></td><td>${number(item.cp)}</td><td>${percent(item.iv_percent)}</td></tr>`).join("");
  }

  function highestRows(items) {
    return items.slice(0, 40).map((item) => `<tr><td><a href="${escapeHtml(item.href)}">#${String(item.pokemon_number).padStart(4, "0")} ${escapeHtml(label(item.name, item.form))}</a></td><td>${number(item.cp)}</td></tr>`).join("");
  }

  function pvpSections(items) {
    return items.map((league) => {
      const rows = league.top_candidates.slice(0, 12).map((item) => `<tr><td><a href="${escapeHtml(item.href)}">${escapeHtml(label(item.name, item.form))}</a></td><td>${percent(item.rank_percent)}</td><td>${number(item.rank_number)}</td><td>${escapeHtml(item.evolution_name || item.name)}</td><td>${number(item.dust_cost)}</td></tr>`).join("");
      return `<section class="insight-section"><h2>${escapeHtml(league.label)}</h2><p class="insight-note"><a href="${escapeHtml(league.href)}">${number(league.eligible_count)} ranked records</a> · ${number(league.rank_99_or_higher)} at 99% or higher. These are Poke Genie IV rankings, not current-meta rankings.</p><div class="insight-table-wrap"><table class="insight-table"><thead><tr><th>Pokémon</th><th>Percentile</th><th>Rank</th><th>Target</th><th>Build dust</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
    }).join("");
  }

  function healthCards(data) {
    const definitions = [
      ["incomplete_scans", "incomplete scans"],
      ["missing_ivs", "missing IV fields"],
      ["missing_levels", "missing level fields"],
      ["missing_moves", "missing move fields"],
      ["missing_selected_pvp", "missing Great League PvP data"],
      ["stale_scans", `scans older than ${number(data.thresholds.stale_scan_days)} days`],
      ["recent_catches", `catches in the last ${number(data.thresholds.recent_catch_days)} days`],
    ];
    return definitions.map(([key, text]) => {
      const href = data.links[key] || "./";
      return `<a class="insight-card" href="${escapeHtml(href)}"><strong>${number(data.counts[key])}</strong><span>${escapeHtml(text)}</span></a>`;
    }).join("");
  }

  function render(documentObject, data) {
    documentObject.getElementById("insights-source").textContent = `${data.source.record_count.toLocaleString()} records from ${data.source.filename}, exported ${data.source.export_timestamp}.`;
    documentObject.getElementById("insights-overview").innerHTML = overviewCards(data);
    documentObject.getElementById("insights-statuses").innerHTML = statusCards(data.overview.status_cards);
    documentObject.getElementById("duplicate-distribution").innerHTML = distributionBars(data.duplicate_distribution);
    documentObject.getElementById("duplicate-rows").innerHTML = duplicateRows(data.top_duplicate_groups);
    documentObject.getElementById("single-copy-rows").innerHTML = singleRows(data.single_copy_groups);
    documentObject.getElementById("highest-cp-rows").innerHTML = highestRows(data.highest_cp_by_species_form);
    documentObject.getElementById("pvp-insights").innerHTML = pvpSections(data.pvp);
    documentObject.getElementById("insights-health").innerHTML = healthCards(data.data_health);
    documentObject.getElementById("insights-limitations").innerHTML = data.limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    documentObject.getElementById("insights-status").textContent = "Collection insights loaded";
  }

  async function load(documentObject, fetchFunction = globalThis.fetch) {
    const status = documentObject.getElementById("insights-status");
    try {
      const response = await fetchFunction("data/insights.json");
      if (!response.ok) throw new Error("Collection insights could not be loaded");
      const data = await response.json();
      render(documentObject, data);
      return data;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Collection insights could not be loaded";
      if (status) status.textContent = message;
      const main = documentObject.querySelector(".insights-main");
      main?.insertAdjacentHTML("afterbegin", `<p class="insights-error">${escapeHtml(message)}. The collection dashboard and published JSON remain available.</p>`);
      return null;
    }
  }

  function install(root) {
    root.document.addEventListener("DOMContentLoaded", () => void load(root.document, root.fetch.bind(root)), { once: true });
  }

  return { escapeHtml, overviewCards, distributionBars, render, load, install };
});
