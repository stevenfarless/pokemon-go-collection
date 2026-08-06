"use strict";

const state = {
  records: [],
  filtered: [],
  summary: null,
  page: 1,
};

const elements = {};

function byId(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value, fallback = "—") {
  return value === null || value === undefined || value === ""
    ? fallback
    : Number(value).toLocaleString();
}

function formatPercent(value) {
  return value === null || value === undefined ? "—" : `${Number(value).toFixed(2)}%`;
}

function selectedLeague() {
  const league = elements.leagueFilter.value;
  return league === "all" ? "great" : league;
}

function searchText(record) {
  const pvpNames = Object.values(record.pvp)
    .flatMap((league) => [league.evolution_name, league.evolution_form]);
  return [
    record.name,
    record.form,
    record.pokemon_number,
    record.gender,
    record.moves.fast,
    record.moves.charged,
    record.moves.charged_second,
    record.status.shadow_purified,
    ...pvpNames,
  ].filter(Boolean).join(" ").toLocaleLowerCase();
}

function matchesStatus(record, status) {
  switch (status) {
    case "shadow": return record.status.shadow_purified === "shadow";
    case "purified": return record.status.shadow_purified === "purified";
    case "lucky": return record.status.lucky;
    case "favorite": return record.status.favorite;
    case "hundo": return record.ivs.is_hundo;
    case "nundo": return record.ivs.is_nundo;
    default: return true;
  }
}

function compareNullable(a, b, direction = 1) {
  const av = a ?? Number.NEGATIVE_INFINITY;
  const bv = b ?? Number.NEGATIVE_INFINITY;
  return (av - bv) * direction;
}

function sortRecords(records) {
  const order = elements.sortOrder.value;
  const league = selectedLeague();
  const copy = [...records];
  copy.sort((a, b) => {
    switch (order) {
      case "iv-desc":
        return compareNullable(b.ivs.average_percent, a.ivs.average_percent) || b.cp - a.cp;
      case "name-asc":
        return a.name.localeCompare(b.name) || (a.form || "").localeCompare(b.form || "") || b.cp - a.cp;
      case "dex-asc":
        return a.pokemon_number - b.pokemon_number || a.name.localeCompare(b.name) || b.cp - a.cp;
      case "recent-scan":
        return String(b.dates.scan || "").localeCompare(String(a.dates.scan || "")) || b.cp - a.cp;
      case "pvp-desc":
        return compareNullable(b.pvp[league].rank_percent, a.pvp[league].rank_percent) ||
          compareNullable(a.pvp[league].rank_number, b.pvp[league].rank_number) || b.cp - a.cp;
      default:
        return b.cp - a.cp || compareNullable(b.ivs.average_percent, a.ivs.average_percent);
    }
  });
  return copy;
}

function updateUrl() {
  const params = new URLSearchParams();
  if (elements.search.value) params.set("q", elements.search.value);
  if (elements.statusFilter.value !== "all") params.set("status", elements.statusFilter.value);
  if (elements.leagueFilter.value !== "all") params.set("league", elements.leagueFilter.value);
  if (elements.minimumIv.value) params.set("miniv", elements.minimumIv.value);
  if (elements.sortOrder.value !== "cp-desc") params.set("sort", elements.sortOrder.value);
  if (elements.pageSize.value !== "50") params.set("size", elements.pageSize.value);
  if (state.page > 1) params.set("page", String(state.page));
  const query = params.toString();
  history.replaceState(null, "", query ? `?${query}` : location.pathname);
}

function applyFilters({ resetPage = true } = {}) {
  if (resetPage) state.page = 1;
  const query = elements.search.value.trim().toLocaleLowerCase();
  const status = elements.statusFilter.value;
  const league = elements.leagueFilter.value;
  const minimumIv = Number(elements.minimumIv.value || 0);

  const filtered = state.records.filter((record) => {
    if (query && !searchText(record).includes(query)) return false;
    if (!matchesStatus(record, status)) return false;
    if ((record.ivs.average_percent ?? -1) < minimumIv) return false;
    if (league !== "all" && record.pvp[league].rank_percent === null) return false;
    return true;
  });

  state.filtered = sortRecords(filtered);
  const totalPages = Math.max(1, Math.ceil(state.filtered.length / Number(elements.pageSize.value)));
  state.page = Math.min(Math.max(1, state.page), totalPages);
  renderTable();
  updateUrl();
}

function statusBadges(record) {
  const badges = [];
  if (record.status.shadow_purified !== "normal") badges.push(record.status.shadow_purified);
  if (record.status.lucky) badges.push("lucky");
  if (record.status.favorite) badges.push("favorite");
  if (record.ivs.is_hundo) badges.push("hundo");
  if (record.ivs.is_nundo) badges.push("nundo");
  if (record.status.marked_for_pvp) badges.push("PvP marked");
  return badges.length
    ? badges.map((badge) => `<span class="badge">${escapeHtml(badge)}</span>`).join(" ")
    : '<span class="muted">normal</span>';
}

function pvpCell(record) {
  const league = selectedLeague();
  const data = record.pvp[league];
  if (data.rank_percent === null) return '<span class="muted">No ranking</span>';
  const target = data.evolution_name && data.evolution_name !== record.name
    ? `<small>as ${escapeHtml(data.evolution_name)}</small>`
    : "";
  return `<strong>${formatPercent(data.rank_percent)}</strong><small>Rank #${formatNumber(data.rank_number)}</small>${target}`;
}

function renderTable() {
  const pageSize = Number(elements.pageSize.value);
  const totalPages = Math.max(1, Math.ceil(state.filtered.length / pageSize));
  const start = (state.page - 1) * pageSize;
  const pageRecords = state.filtered.slice(start, start + pageSize);

  elements.body.innerHTML = pageRecords.map((record) => {
    const form = record.form ? `<small>${escapeHtml(record.form)}</small>` : "";
    const gender = record.gender ? ` ${escapeHtml(record.gender)}` : "";
    const chargedMoves = [record.moves.charged, record.moves.charged_second].filter(Boolean).map(escapeHtml).join(" · ");
    return `<tr>
      <td><strong>#${String(record.pokemon_number).padStart(4, "0")} ${escapeHtml(record.name)}${gender}</strong>${form}</td>
      <td><strong>${formatNumber(record.cp)}</strong><small>${formatNumber(record.hp)} HP</small></td>
      <td><strong>${formatPercent(record.ivs.average_percent)}</strong><small>${formatNumber(record.ivs.attack)}/${formatNumber(record.ivs.defense)}/${formatNumber(record.ivs.stamina)} · ${formatNumber(record.ivs.total)}/45</small></td>
      <td><strong>${formatNumber(record.level.minimum)}</strong>${record.level.maximum !== record.level.minimum ? `<small>max ${formatNumber(record.level.maximum)}</small>` : ""}</td>
      <td><strong>${escapeHtml(record.moves.fast || "Unknown")}</strong><small>${chargedMoves || "No charged move scanned"}</small></td>
      <td><div class="badges">${statusBadges(record)}</div></td>
      <td>${pvpCell(record)}</td>
      <td><strong>${escapeHtml(record.dates.catch || "Unknown catch")}</strong><small>Scanned ${escapeHtml(record.dates.scan || "unknown")}</small></td>
    </tr>`;
  }).join("");

  const first = state.filtered.length ? start + 1 : 0;
  const last = Math.min(start + pageSize, state.filtered.length);
  elements.resultCount.textContent = `${state.filtered.length.toLocaleString()} results · showing ${first.toLocaleString()}–${last.toLocaleString()}`;
  elements.pageLabel.textContent = `Page ${state.page.toLocaleString()} of ${totalPages.toLocaleString()}`;
  elements.previous.disabled = state.page <= 1;
  elements.next.disabled = state.page >= totalPages;
}

function renderSummary() {
  const summary = state.summary;
  byId("total-count").textContent = summary.pokemon_count.toLocaleString();
  byId("species-count").textContent = summary.distinct_species_forms.toLocaleString();
  byId("hundo-count").textContent = summary.hundo_count.toLocaleString();
  byId("shadow-count").textContent = summary.shadow_count.toLocaleString();
  byId("lucky-count").textContent = summary.lucky_count.toLocaleString();
  byId("highest-cp").textContent = summary.highest_cp.toLocaleString();
}

function loadUrlState() {
  const params = new URLSearchParams(location.search);
  elements.search.value = params.get("q") || "";
  elements.statusFilter.value = params.get("status") || "all";
  elements.leagueFilter.value = params.get("league") || "all";
  elements.minimumIv.value = params.get("miniv") || "";
  elements.sortOrder.value = params.get("sort") || "cp-desc";
  elements.pageSize.value = params.get("size") || "50";
  state.page = Math.max(1, Number(params.get("page") || 1));
}

function resetFilters() {
  elements.search.value = "";
  elements.statusFilter.value = "all";
  elements.leagueFilter.value = "all";
  elements.minimumIv.value = "";
  elements.sortOrder.value = "cp-desc";
  elements.pageSize.value = "50";
  state.page = 1;
  applyFilters({ resetPage: false });
}

async function initialize() {
  Object.assign(elements, {
    search: byId("search"),
    statusFilter: byId("status-filter"),
    leagueFilter: byId("league-filter"),
    minimumIv: byId("minimum-iv"),
    sortOrder: byId("sort-order"),
    pageSize: byId("page-size"),
    reset: byId("reset-filters"),
    resultCount: byId("result-count"),
    body: byId("pokemon-body"),
    previous: byId("previous-page"),
    next: byId("next-page"),
    pageLabel: byId("page-label"),
  });

  loadUrlState();

  try {
    const [collectionResponse, summaryResponse] = await Promise.all([
      fetch("data/pokemon.json"),
      fetch("data/collection-summary.json"),
    ]);
    if (!collectionResponse.ok || !summaryResponse.ok) throw new Error("Collection data could not be loaded");
    const collection = await collectionResponse.json();
    state.records = collection.records;
    state.summary = await summaryResponse.json();
    renderSummary();
    applyFilters({ resetPage: false });
  } catch (error) {
    elements.resultCount.textContent = error instanceof Error ? error.message : "Collection data could not be loaded";
    elements.body.innerHTML = '<tr><td colspan="8">The dashboard data failed to load. Use the CSV or JSON download links above.</td></tr>';
    return;
  }

  const filterElements = [elements.search, elements.statusFilter, elements.leagueFilter, elements.minimumIv, elements.sortOrder, elements.pageSize];
  filterElements.forEach((element) => element.addEventListener("input", () => applyFilters()));
  elements.reset.addEventListener("click", resetFilters);
  elements.previous.addEventListener("click", () => {
    state.page -= 1;
    renderTable();
    updateUrl();
    document.querySelector(".table-card").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  elements.next.addEventListener("click", () => {
    state.page += 1;
    renderTable();
    updateUrl();
    document.querySelector(".table-card").scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

document.addEventListener("DOMContentLoaded", initialize);
