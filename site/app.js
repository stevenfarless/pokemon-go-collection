"use strict";

const DEFAULT_SORTS = Object.freeze([{ field: "cp", direction: "desc" }]);

const SORT_FIELDS = Object.freeze({
  name: { label: "Pokémon name", defaultDirection: "asc" },
  dex: { label: "Pokédex number", defaultDirection: "asc" },
  cp: { label: "CP", defaultDirection: "desc" },
  hp: { label: "HP", defaultDirection: "desc" },
  iv: { label: "IV %", defaultDirection: "desc" },
  attack: { label: "Attack IV", defaultDirection: "desc" },
  defense: { label: "Defense IV", defaultDirection: "desc" },
  stamina: { label: "HP IV", defaultDirection: "desc" },
  level: { label: "Level", defaultDirection: "desc" },
  pvp: { label: "PvP percentile", defaultDirection: "desc" },
  "pvp-rank": { label: "PvP rank number", defaultDirection: "asc" },
  catch: { label: "Catch date", defaultDirection: "desc" },
  scan: { label: "Scan date", defaultDirection: "desc" },
});

const LEGACY_SORTS = Object.freeze({
  "cp-desc": [{ field: "cp", direction: "desc" }, { field: "iv", direction: "desc" }],
  "iv-desc": [{ field: "iv", direction: "desc" }, { field: "cp", direction: "desc" }],
  "name-asc": [{ field: "name", direction: "asc" }, { field: "cp", direction: "desc" }],
  "dex-asc": [{ field: "dex", direction: "asc" }, { field: "name", direction: "asc" }, { field: "cp", direction: "desc" }],
  "recent-scan": [{ field: "scan", direction: "desc" }, { field: "cp", direction: "desc" }],
  "pvp-desc": [{ field: "pvp", direction: "desc" }, { field: "pvp-rank", direction: "asc" }, { field: "cp", direction: "desc" }],
});

const state = {
  records: [],
  filtered: [],
  summary: null,
  page: 1,
  sorts: DEFAULT_SORTS.map((criterion) => ({ ...criterion })),
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

function cloneDefaultSorts() {
  return DEFAULT_SORTS.map((criterion) => ({ ...criterion }));
}

function normalizeSorts(sorts) {
  const normalized = [];
  const usedFields = new Set();

  for (const criterion of Array.isArray(sorts) ? sorts : []) {
    const field = String(criterion?.field || "");
    const direction = criterion?.direction === "asc" ? "asc" : "desc";
    if (!SORT_FIELDS[field] || usedFields.has(field)) continue;
    normalized.push({ field, direction });
    usedFields.add(field);
  }

  return normalized.length ? normalized : cloneDefaultSorts();
}

function parseSortParam(value) {
  if (!value) return cloneDefaultSorts();
  if (LEGACY_SORTS[value]) return normalizeSorts(LEGACY_SORTS[value]);

  return normalizeSorts(
    String(value)
      .split(",")
      .map((part) => {
        const [field, direction] = part.split(":");
        return { field, direction };
      }),
  );
}

function serializeSorts(sorts) {
  return normalizeSorts(sorts)
    .map(({ field, direction }) => `${field}:${direction}`)
    .join(",");
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

function getSortValue(record, field, league) {
  switch (field) {
    case "name": return `${record.name || ""}\u0000${record.form || ""}`;
    case "dex": return record.pokemon_number;
    case "cp": return record.cp;
    case "hp": return record.hp;
    case "iv": return record.ivs.average_percent;
    case "attack": return record.ivs.attack;
    case "defense": return record.ivs.defense;
    case "stamina": return record.ivs.stamina;
    case "level": return record.level.minimum;
    case "pvp": return record.pvp[league]?.rank_percent;
    case "pvp-rank": return record.pvp[league]?.rank_number;
    case "catch": return record.dates.catch;
    case "scan": return record.dates.scan;
    default: return null;
  }
}

function compareValues(a, b, direction) {
  const aMissing = a === null || a === undefined || a === "";
  const bMissing = b === null || b === undefined || b === "";
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;

  let comparison;
  if (typeof a === "number" && typeof b === "number") {
    comparison = a - b;
  } else {
    comparison = String(a).localeCompare(String(b), undefined, {
      numeric: true,
      sensitivity: "base",
    });
  }

  return direction === "desc" ? -comparison : comparison;
}

function sortRecordsByCriteria(records, sorts, league = "great") {
  const criteria = normalizeSorts(sorts);
  return records
    .map((record, index) => ({ record, index }))
    .sort((left, right) => {
      for (const criterion of criteria) {
        const comparison = compareValues(
          getSortValue(left.record, criterion.field, league),
          getSortValue(right.record, criterion.field, league),
          criterion.direction,
        );
        if (comparison !== 0) return comparison;
      }
      return left.index - right.index;
    })
    .map(({ record }) => record);
}

function sortRecords(records) {
  return sortRecordsByCriteria(records, state.sorts, selectedLeague());
}

function directionLabel(direction) {
  return direction === "asc" ? "ascending" : "descending";
}

function directionArrow(direction) {
  return direction === "asc" ? "↑" : "↓";
}

function sortDescription(criterion) {
  return `${SORT_FIELDS[criterion.field].label} ${directionArrow(criterion.direction)}`;
}

function updateUrl() {
  const params = new URLSearchParams();
  if (elements.search.value) params.set("q", elements.search.value);
  if (elements.statusFilter.value !== "all") params.set("status", elements.statusFilter.value);
  if (elements.leagueFilter.value !== "all") params.set("league", elements.leagueFilter.value);
  if (elements.minimumIv.value) params.set("miniv", elements.minimumIv.value);
  if (serializeSorts(state.sorts) !== serializeSorts(DEFAULT_SORTS)) {
    params.set("sort", serializeSorts(state.sorts));
  }
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

function renderSortControls() {
  const usedFields = new Set(state.sorts.map(({ field }) => field));
  elements.sortLevels.innerHTML = state.sorts.map((criterion, index) => {
    const options = Object.entries(SORT_FIELDS).map(([field, config]) => {
      const selected = field === criterion.field ? " selected" : "";
      const disabled = usedFields.has(field) && field !== criterion.field ? " disabled" : "";
      return `<option value="${field}"${selected}${disabled}>${escapeHtml(config.label)}</option>`;
    }).join("");

    return `<div class="sort-level" data-sort-index="${index}">
      <span class="sort-priority" aria-label="Sort priority ${index + 1}">${index + 1}</span>
      <label>
        <span class="visually-hidden">Column for sort priority ${index + 1}</span>
        <select data-sort-field="${index}">${options}</select>
      </label>
      <label>
        <span class="visually-hidden">Direction for sort priority ${index + 1}</span>
        <select data-sort-direction="${index}">
          <option value="desc"${criterion.direction === "desc" ? " selected" : ""}>Descending</option>
          <option value="asc"${criterion.direction === "asc" ? " selected" : ""}>Ascending</option>
        </select>
      </label>
      <div class="sort-actions">
        <button type="button" data-sort-up="${index}" aria-label="Move sort priority ${index + 1} earlier"${index === 0 ? " disabled" : ""}>↑</button>
        <button type="button" data-sort-down="${index}" aria-label="Move sort priority ${index + 1} later"${index === state.sorts.length - 1 ? " disabled" : ""}>↓</button>
        <button type="button" data-sort-remove="${index}" aria-label="Remove sort priority ${index + 1}"${state.sorts.length === 1 ? " disabled" : ""}>Remove</button>
      </div>
    </div>`;
  }).join("");

  elements.sortSummary.textContent = `Active order: ${state.sorts
    .map((criterion, index) => `${index + 1}. ${sortDescription(criterion)}`)
    .join(" → ")}`;

  elements.addSort.disabled = state.sorts.length >= Object.keys(SORT_FIELDS).length;

  elements.sortLevels.querySelectorAll("[data-sort-field]").forEach((select) => {
    select.addEventListener("change", () => {
      const index = Number(select.dataset.sortField);
      state.sorts[index] = {
        field: select.value,
        direction: state.sorts[index].direction,
      };
      state.sorts = normalizeSorts(state.sorts);
      renderSortControls();
      applyFilters();
    });
  });

  elements.sortLevels.querySelectorAll("[data-sort-direction]").forEach((select) => {
    select.addEventListener("change", () => {
      const index = Number(select.dataset.sortDirection);
      state.sorts[index].direction = select.value === "asc" ? "asc" : "desc";
      renderSortControls();
      applyFilters();
    });
  });

  elements.sortLevels.querySelectorAll("[data-sort-up]").forEach((button) => {
    button.addEventListener("click", () => moveSort(Number(button.dataset.sortUp), -1));
  });
  elements.sortLevels.querySelectorAll("[data-sort-down]").forEach((button) => {
    button.addEventListener("click", () => moveSort(Number(button.dataset.sortDown), 1));
  });
  elements.sortLevels.querySelectorAll("[data-sort-remove]").forEach((button) => {
    button.addEventListener("click", () => removeSort(Number(button.dataset.sortRemove)));
  });

  renderSortIndicators();
}

function addSort() {
  const usedFields = new Set(state.sorts.map(({ field }) => field));
  const field = Object.keys(SORT_FIELDS).find((candidate) => !usedFields.has(candidate));
  if (!field) return;
  state.sorts.push({
    field,
    direction: SORT_FIELDS[field].defaultDirection,
  });
  renderSortControls();
  applyFilters();
}

function moveSort(index, offset) {
  const target = index + offset;
  if (target < 0 || target >= state.sorts.length) return;
  [state.sorts[index], state.sorts[target]] = [state.sorts[target], state.sorts[index]];
  renderSortControls();
  applyFilters();
}

function removeSort(index) {
  if (state.sorts.length <= 1) return;
  state.sorts.splice(index, 1);
  state.sorts = normalizeSorts(state.sorts);
  renderSortControls();
  applyFilters();
}

function setPrimarySort(field) {
  const current = state.sorts[0];
  if (current?.field === field) {
    current.direction = current.direction === "asc" ? "desc" : "asc";
  } else {
    state.sorts = [{
      field,
      direction: SORT_FIELDS[field].defaultDirection,
    }];
  }
  renderSortControls();
  applyFilters();
}

function addOrToggleSort(field) {
  const index = state.sorts.findIndex((criterion) => criterion.field === field);
  if (index >= 0) {
    state.sorts[index].direction = state.sorts[index].direction === "asc" ? "desc" : "asc";
  } else {
    state.sorts.push({
      field,
      direction: SORT_FIELDS[field].defaultDirection,
    });
  }
  renderSortControls();
  applyFilters();
}

function renderSortIndicators() {
  document.querySelectorAll("[data-sort-key]").forEach((button) => {
    const field = button.dataset.sortKey;
    const index = state.sorts.findIndex((criterion) => criterion.field === field);
    const indicator = button.querySelector(".sort-indicator");
    const header = button.closest("th");
    const baseLabel = SORT_FIELDS[field]?.label || button.textContent.trim();

    if (index >= 0) {
      const criterion = state.sorts[index];
      indicator.textContent = `${index + 1}${directionArrow(criterion.direction)}`;
      button.setAttribute(
        "aria-label",
        `${baseLabel}, sort priority ${index + 1}, ${directionLabel(criterion.direction)}. Click to make primary or toggle primary direction; Shift-click to add or toggle this priority.`,
      );
      header.setAttribute("aria-sort", index === 0 ? directionLabel(criterion.direction) : "other");
    } else {
      indicator.textContent = "";
      button.setAttribute(
        "aria-label",
        `${baseLabel}, unsorted. Click to make primary; Shift-click to add as another priority.`,
      );
      header.removeAttribute("aria-sort");
    }
  });
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
  renderSortIndicators();
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
  state.sorts = parseSortParam(params.get("sort"));
  elements.pageSize.value = params.get("size") || "50";
  state.page = Math.max(1, Number(params.get("page") || 1));
}

function resetFilters() {
  elements.search.value = "";
  elements.statusFilter.value = "all";
  elements.leagueFilter.value = "all";
  elements.minimumIv.value = "";
  state.sorts = cloneDefaultSorts();
  elements.pageSize.value = "50";
  state.page = 1;
  renderSortControls();
  applyFilters({ resetPage: false });
}

async function initialize() {
  Object.assign(elements, {
    search: byId("search"),
    statusFilter: byId("status-filter"),
    leagueFilter: byId("league-filter"),
    minimumIv: byId("minimum-iv"),
    pageSize: byId("page-size"),
    reset: byId("reset-filters"),
    addSort: byId("add-sort"),
    sortLevels: byId("sort-levels"),
    sortSummary: byId("sort-summary"),
    resultCount: byId("result-count"),
    body: byId("pokemon-body"),
    previous: byId("previous-page"),
    next: byId("next-page"),
    pageLabel: byId("page-label"),
  });

  loadUrlState();
  renderSortControls();

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

  const filterElements = [elements.search, elements.statusFilter, elements.leagueFilter, elements.minimumIv, elements.pageSize];
  filterElements.forEach((element) => element.addEventListener("input", () => applyFilters()));
  elements.addSort.addEventListener("click", addSort);
  elements.reset.addEventListener("click", resetFilters);

  document.querySelectorAll("[data-sort-key]").forEach((button) => {
    button.addEventListener("click", (event) => {
      const field = button.dataset.sortKey;
      if (event.shiftKey) addOrToggleSort(field);
      else setPrimarySort(field);
    });
  });

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

if (typeof module !== "undefined") {
  module.exports = {
    normalizeSorts,
    parseSortParam,
    serializeSorts,
    sortRecordsByCriteria,
  };
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", initialize);
}
