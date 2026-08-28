"use strict";

(function exposeFilterEngine(root, factory) {
  const engine = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = engine;
  if (root) root.CollectionFilterEngine = engine;
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const DEFAULT_SORTS = Object.freeze([{ field: "cp", direction: "desc" }]);

  const SORT_FIELDS = Object.freeze({
    name: { label: "Pokémon name", defaultDirection: "asc" },
    form: { label: "Form", defaultDirection: "asc" },
    dex: { label: "Pokédex number", defaultDirection: "asc" },
    gender: { label: "Gender", defaultDirection: "asc" },
    cp: { label: "CP", defaultDirection: "desc" },
    hp: { label: "HP", defaultDirection: "desc" },
    iv: { label: "IV %", defaultDirection: "desc" },
    "iv-total": { label: "IV total", defaultDirection: "desc" },
    attack: { label: "Attack IV", defaultDirection: "desc" },
    defense: { label: "Defense IV", defaultDirection: "desc" },
    stamina: { label: "HP IV", defaultDirection: "desc" },
    level: { label: "Minimum level", defaultDirection: "desc" },
    "level-max": { label: "Maximum level", defaultDirection: "desc" },
    weight: { label: "Weight", defaultDirection: "desc" },
    height: { label: "Height", defaultDirection: "desc" },
    dust: { label: "Power-up dust", defaultDirection: "desc" },
    "fast-move": { label: "Fast move", defaultDirection: "asc" },
    "charged-move": { label: "Charged move", defaultDirection: "asc" },
    status: { label: "Shadow status", defaultDirection: "asc" },
    lucky: { label: "Lucky", defaultDirection: "desc" },
    favorite: { label: "Favorite", defaultDirection: "desc" },
    "pvp-marked": { label: "Poke Genie PvP mark", defaultDirection: "desc" },
    pvp: { label: "PvP percentile", defaultDirection: "desc" },
    "pvp-rank": { label: "PvP rank number", defaultDirection: "asc" },
    "pvp-stat": { label: "PvP stat product", defaultDirection: "desc" },
    "pvp-dust": { label: "PvP build dust", defaultDirection: "asc" },
    "pvp-candy": { label: "PvP build candy", defaultDirection: "asc" },
    catch: { label: "Catch date", defaultDirection: "desc" },
    scan: { label: "Scan date", defaultDirection: "desc" },
    "original-scan": { label: "Original scan date", defaultDirection: "desc" },
  });

  const LEGACY_SORTS = Object.freeze({
    "cp-desc": [{ field: "cp", direction: "desc" }, { field: "iv", direction: "desc" }],
    "iv-desc": [{ field: "iv", direction: "desc" }, { field: "cp", direction: "desc" }],
    "name-asc": [{ field: "name", direction: "asc" }, { field: "cp", direction: "desc" }],
    "dex-asc": [{ field: "dex", direction: "asc" }, { field: "name", direction: "asc" }, { field: "cp", direction: "desc" }],
    "recent-scan": [{ field: "scan", direction: "desc" }, { field: "cp", direction: "desc" }],
    "pvp-desc": [{ field: "pvp", direction: "desc" }, { field: "pvp-rank", direction: "asc" }, { field: "cp", direction: "desc" }],
  });

  function cloneDefaultSorts() {
    return DEFAULT_SORTS.map((criterion) => ({ ...criterion }));
  }

  function normalizeSorts(sorts) {
    const normalized = [];
    const used = new Set();
    for (const criterion of Array.isArray(sorts) ? sorts : []) {
      const field = String(criterion?.field || "");
      const direction = criterion?.direction === "asc" ? "asc" : "desc";
      if (!SORT_FIELDS[field] || used.has(field)) continue;
      normalized.push({ field, direction });
      used.add(field);
    }
    return normalized.length ? normalized : cloneDefaultSorts();
  }

  function parseSortParam(value) {
    if (!value) return cloneDefaultSorts();
    if (LEGACY_SORTS[value]) return normalizeSorts(LEGACY_SORTS[value]);
    return normalizeSorts(String(value).split(",").map((part) => {
      const [field, direction] = part.split(":");
      return { field, direction };
    }));
  }

  function serializeSorts(sorts) {
    return normalizeSorts(sorts).map(({ field, direction }) => `${field}:${direction}`).join(",");
  }

  function parseSearchQuery(query) {
    const positive = [];
    const negative = [];
    const expression = /(-?)"([^"]+)"|(-?)(\S+)/g;
    let match;
    while ((match = expression.exec(String(query || ""))) !== null) {
      const excluded = match[1] === "-" || match[3] === "-";
      const term = (match[2] || match[4] || "").trim().toLocaleLowerCase();
      if (!term) continue;
      (excluded ? negative : positive).push(term);
    }
    return { positive, negative };
  }

  function recordSearchText(record) {
    const pvpValues = Object.values(record.pvp || {}).flatMap((league) => [
      league?.evolution_name,
      league?.evolution_form,
      league?.status,
    ]);
    const flags = [
      record.status?.lucky ? "lucky" : null,
      record.status?.favorite ? "favorite" : null,
      record.status?.marked_for_pvp ? "pvp marked" : null,
      record.ivs?.is_hundo ? "hundo 4 star" : null,
      record.ivs?.is_nundo ? "nundo zero iv" : null,
      record.moves?.charged_second ? "second charged move" : null,
    ];
    return [
      record.name,
      record.form,
      record.pokemon_number,
      record.gender,
      record.cp,
      record.hp,
      record.moves?.fast,
      record.moves?.charged,
      record.moves?.charged_second,
      record.status?.shadow_purified,
      record.dates?.catch,
      record.dates?.scan,
      ...pvpValues,
      ...flags,
    ].filter((value) => value !== null && value !== undefined && value !== "")
      .join(" ")
      .toLocaleLowerCase();
  }

  function matchesSearch(record, query) {
    const { positive, negative } = parseSearchQuery(query);
    if (!positive.length && !negative.length) return true;
    const haystack = recordSearchText(record);
    return positive.every((term) => haystack.includes(term)) &&
      negative.every((term) => !haystack.includes(term));
  }

  function isMissing(value) {
    return value === null || value === undefined || value === "";
  }

  function numberOrNull(value) {
    if (value === null || value === undefined || value === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function inRange(value, minimum, maximum) {
    const min = numberOrNull(minimum);
    const max = numberOrNull(maximum);
    if (min === null && max === null) return true;
    const current = numberOrNull(value);
    if (current === null) return false;
    if (min !== null && current < min) return false;
    if (max !== null && current > max) return false;
    return true;
  }

  function triStateMatches(value, state) {
    if (!state || state === "any") return true;
    return state === "yes" ? Boolean(value) : !Boolean(value);
  }

  function textContains(value, query) {
    if (!query) return true;
    return String(value || "").toLocaleLowerCase().includes(String(query).trim().toLocaleLowerCase());
  }

  function textEquals(value, expected) {
    if (!expected) return true;
    return String(value || "").toLocaleLowerCase() === String(expected).trim().toLocaleLowerCase();
  }

  function dateValue(value) {
    if (!value) return null;
    const text = String(value).trim();
    const iso = text.match(/^(\d{4}-\d{2}-\d{2})/);
    if (iso) return iso[1];
    const timestamp = Date.parse(text);
    if (Number.isNaN(timestamp)) return null;
    return new Date(timestamp).toISOString().slice(0, 10);
  }

  function dateInRange(value, from, to) {
    if (!from && !to) return true;
    const current = dateValue(value);
    if (!current) return false;
    if (from && current < from) return false;
    if (to && current > to) return false;
    return true;
  }

  function isComplete(record) {
    return !isMissing(record.ivs?.average_percent) &&
      !isMissing(record.level?.minimum) &&
      !isMissing(record.moves?.fast) &&
      !isMissing(record.moves?.charged);
  }

  function matchesDataQuality(record, quality, league) {
    switch (quality) {
      case "complete": return isComplete(record);
      case "missing-any": return !isComplete(record);
      case "missing-ivs": return isMissing(record.ivs?.average_percent) ||
        isMissing(record.ivs?.attack) || isMissing(record.ivs?.defense) || isMissing(record.ivs?.stamina);
      case "missing-level": return isMissing(record.level?.minimum);
      case "missing-moves": return isMissing(record.moves?.fast) || isMissing(record.moves?.charged);
      case "missing-pvp": return isMissing(record.pvp?.[league]?.rank_percent);
      default: return true;
    }
  }

  function matchesRecord(record, filters = {}) {
    const league = ["great", "ultra", "little"].includes(filters.league) ? filters.league : "great";
    const pvp = record.pvp?.[league] || {};
    const ranges = filters.ranges || {};
    const dates = filters.dates || {};

    if (!matchesSearch(record, filters.query)) return false;
    if (!textEquals(record.name, filters.species)) return false;
    if (!textContains(record.form, filters.form)) return false;
    if (filters.gender && filters.gender !== "any" && record.gender !== filters.gender) return false;
    if (filters.status && filters.status !== "any" && record.status?.shadow_purified !== filters.status) return false;
    if (!triStateMatches(record.status?.lucky, filters.lucky)) return false;
    if (!triStateMatches(record.status?.favorite, filters.favorite)) return false;
    if (!triStateMatches(record.status?.marked_for_pvp, filters.pvpMarked)) return false;
    if (!triStateMatches(record.ivs?.is_hundo, filters.hundo)) return false;
    if (!triStateMatches(record.ivs?.is_nundo, filters.nundo)) return false;
    if (!triStateMatches(Boolean(record.moves?.charged_second), filters.secondMove)) return false;
    if (!matchesDataQuality(record, filters.dataQuality, league)) return false;

    if (!textContains(record.moves?.fast, filters.fastMove)) return false;
    const chargedText = [record.moves?.charged, record.moves?.charged_second].filter(Boolean).join(" ");
    if (!textContains(chargedText, filters.chargedMove)) return false;
    const evolutionText = [pvp.evolution_name, pvp.evolution_form].filter(Boolean).join(" ");
    if (!textContains(evolutionText, filters.evolution)) return false;
    if (filters.pvpStatus && filters.pvpStatus !== "any" && pvp.status !== filters.pvpStatus) return false;

    if (filters.pvpEligibility === "ranked" && isMissing(pvp.rank_percent)) return false;
    if (filters.pvpEligibility === "unranked" && !isMissing(pvp.rank_percent)) return false;

    const numericChecks = [
      [record.pokemon_number, ranges.dex],
      [record.cp, ranges.cp],
      [record.hp, ranges.hp],
      [record.ivs?.average_percent, ranges.iv],
      [record.ivs?.total, ranges.ivTotal],
      [record.ivs?.attack, ranges.attack],
      [record.ivs?.defense, ranges.defense],
      [record.ivs?.stamina, ranges.stamina],
      [record.level?.minimum, ranges.level],
      [record.level?.maximum, ranges.levelMax],
      [record.size?.weight, ranges.weight],
      [record.size?.height, ranges.height],
      [record.dust, ranges.dust],
      [pvp.rank_percent, ranges.pvpPercent],
      [pvp.rank_number, ranges.pvpRank],
      [pvp.stat_product, ranges.pvpStat],
      [pvp.dust_cost, ranges.pvpDust],
      [pvp.candy_cost, ranges.pvpCandy],
    ];
    if (numericChecks.some(([value, bounds]) => bounds && !inRange(value, bounds.min, bounds.max))) return false;

    if (!dateInRange(record.dates?.catch, dates.catch?.from, dates.catch?.to)) return false;
    if (!dateInRange(record.dates?.scan, dates.scan?.from, dates.scan?.to)) return false;
    if (!dateInRange(record.dates?.original_scan, dates.originalScan?.from, dates.originalScan?.to)) return false;

    return true;
  }

  function getSortValue(record, field, league) {
    const pvp = record.pvp?.[league] || {};
    switch (field) {
      case "name": return `${record.name || ""}\u0000${record.form || ""}`;
      case "form": return record.form;
      case "dex": return record.pokemon_number;
      case "gender": return record.gender;
      case "cp": return record.cp;
      case "hp": return record.hp;
      case "iv": return record.ivs?.average_percent;
      case "iv-total": return record.ivs?.total;
      case "attack": return record.ivs?.attack;
      case "defense": return record.ivs?.defense;
      case "stamina": return record.ivs?.stamina;
      case "level": return record.level?.minimum;
      case "level-max": return record.level?.maximum;
      case "weight": return record.size?.weight;
      case "height": return record.size?.height;
      case "dust": return record.dust;
      case "fast-move": return record.moves?.fast;
      case "charged-move": return record.moves?.charged;
      case "status": return record.status?.shadow_purified;
      case "lucky": return record.status?.lucky ? 1 : 0;
      case "favorite": return record.status?.favorite ? 1 : 0;
      case "pvp-marked": return record.status?.marked_for_pvp ? 1 : 0;
      case "pvp": return pvp.rank_percent;
      case "pvp-rank": return pvp.rank_number;
      case "pvp-stat": return pvp.stat_product;
      case "pvp-dust": return pvp.dust_cost;
      case "pvp-candy": return pvp.candy_cost;
      case "catch": return dateValue(record.dates?.catch);
      case "scan": return dateValue(record.dates?.scan);
      case "original-scan": return dateValue(record.dates?.original_scan);
      default: return null;
    }
  }

  function compareValues(a, b, direction) {
    const aMissing = isMissing(a);
    const bMissing = isMissing(b);
    if (aMissing && bMissing) return 0;
    if (aMissing) return 1;
    if (bMissing) return -1;
    let comparison;
    if (typeof a === "number" && typeof b === "number") comparison = a - b;
    else comparison = String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
    return direction === "desc" ? -comparison : comparison;
  }

  function sortRecordsByCriteria(records, sorts, league = "great") {
    const criteria = normalizeSorts(sorts);
    return records.map((record, index) => ({ record, index })).sort((left, right) => {
      for (const criterion of criteria) {
        const comparison = compareValues(
          getSortValue(left.record, criterion.field, league),
          getSortValue(right.record, criterion.field, league),
          criterion.direction,
        );
        if (comparison !== 0) return comparison;
      }
      return left.index - right.index;
    }).map(({ record }) => record);
  }

  return {
    DEFAULT_SORTS,
    SORT_FIELDS,
    cloneDefaultSorts,
    normalizeSorts,
    parseSortParam,
    serializeSorts,
    parseSearchQuery,
    recordSearchText,
    matchesSearch,
    inRange,
    dateValue,
    dateInRange,
    matchesRecord,
    sortRecordsByCriteria,
  };
});

const Engine = globalThis.CollectionFilterEngine;

const state = {
  records: [],
  filtered: [],
  summary: null,
  page: 1,
  sorts: Engine.cloneDefaultSorts(),
};

const elements = {};

const SIMPLE_CONTROLS = [
  { id: "search", param: "q", defaultValue: "", label: "Search", kind: "quick" },
  { id: "species-filter", param: "species", defaultValue: "", label: "Species", kind: "advanced" },
  { id: "form-filter", param: "form", defaultValue: "", label: "Form", kind: "advanced" },
  { id: "gender-filter", param: "gender", defaultValue: "any", label: "Gender", kind: "advanced" },
  { id: "status-filter", param: "status", defaultValue: "any", label: "Status", kind: "quick" },
  { id: "lucky-filter", param: "lucky", defaultValue: "any", label: "Lucky", kind: "advanced" },
  { id: "favorite-filter", param: "fav", defaultValue: "any", label: "Favorite", kind: "advanced" },
  { id: "pvp-marked-filter", param: "pvpm", defaultValue: "any", label: "Poke Genie PvP mark", kind: "advanced" },
  { id: "hundo-filter", param: "hundo", defaultValue: "any", label: "Hundo", kind: "advanced" },
  { id: "nundo-filter", param: "nundo", defaultValue: "any", label: "Nundo", kind: "advanced" },
  { id: "second-move-filter", param: "second", defaultValue: "any", label: "Second charged move", kind: "advanced" },
  { id: "data-quality-filter", param: "quality", defaultValue: "any", label: "Data quality", kind: "advanced" },
  { id: "fast-move-filter", param: "fast", defaultValue: "", label: "Fast move", kind: "advanced" },
  { id: "charged-move-filter", param: "charged", defaultValue: "", label: "Charged move", kind: "advanced" },
  { id: "evolution-filter", param: "evo", defaultValue: "", label: "PvP evolution", kind: "advanced" },
  { id: "pvp-status-filter", param: "pvpstatus", defaultValue: "any", label: "PvP form status", kind: "advanced" },
  { id: "league-filter", param: "league", defaultValue: "great", label: "PvP league", kind: "quick" },
  { id: "pvp-eligibility-filter", param: "pvpelig", defaultValue: "any", label: "PvP ranking", kind: "quick" },
  { id: "page-size", param: "size", defaultValue: "50", label: "Rows", kind: "preference", chip: false },
];

const RANGE_CONTROLS = [
  { key: "dex", label: "Pokédex #", minId: "dex-min", maxId: "dex-max", minParam: "dexmin", maxParam: "dexmax", kind: "advanced" },
  { key: "cp", label: "CP", minId: "cp-min", maxId: "cp-max", minParam: "cpmin", maxParam: "cpmax", kind: "advanced" },
  { key: "hp", label: "HP", minId: "hp-min", maxId: "hp-max", minParam: "hpmin", maxParam: "hpmax", kind: "advanced" },
  { key: "iv", label: "IV %", minId: "iv-min", maxId: "iv-max", minParam: "ivmin", maxParam: "ivmax", kind: "advanced" },
  { key: "ivTotal", label: "IV total", minId: "iv-total-min", maxId: "iv-total-max", minParam: "ivtotalmin", maxParam: "ivtotalmax", kind: "advanced" },
  { key: "attack", label: "Attack IV", minId: "attack-min", maxId: "attack-max", minParam: "atkmin", maxParam: "atkmax", kind: "advanced" },
  { key: "defense", label: "Defense IV", minId: "defense-min", maxId: "defense-max", minParam: "defmin", maxParam: "defmax", kind: "advanced" },
  { key: "stamina", label: "HP IV", minId: "stamina-min", maxId: "stamina-max", minParam: "staminamin", maxParam: "staminamax", kind: "advanced" },
  { key: "level", label: "Minimum level", minId: "level-min", maxId: "level-max", minParam: "levelmin", maxParam: "levelmax", kind: "advanced" },
  { key: "levelMax", label: "Maximum level", minId: "level-cap-min", maxId: "level-cap-max", minParam: "levelcapmin", maxParam: "levelcapmax", kind: "advanced" },
  { key: "dust", label: "Power-up dust", minId: "dust-min", maxId: "dust-max", minParam: "dustmin", maxParam: "dustmax", kind: "advanced" },
  { key: "weight", label: "Weight", minId: "weight-min", maxId: "weight-max", minParam: "weightmin", maxParam: "weightmax", kind: "advanced" },
  { key: "height", label: "Height", minId: "height-min", maxId: "height-max", minParam: "heightmin", maxParam: "heightmax", kind: "advanced" },
  { key: "pvpPercent", label: "PvP percentile", minId: "pvp-percent-min", maxId: "pvp-percent-max", minParam: "pvpmin", maxParam: "pvpmax", kind: "advanced" },
  { key: "pvpRank", label: "PvP rank #", minId: "pvp-rank-min", maxId: "pvp-rank-max", minParam: "pvprankmin", maxParam: "pvprankmax", kind: "advanced" },
  { key: "pvpStat", label: "PvP stat product", minId: "pvp-stat-min", maxId: "pvp-stat-max", minParam: "pvpstatmin", maxParam: "pvpstatmax", kind: "advanced" },
  { key: "pvpDust", label: "PvP build dust", minId: "pvp-dust-min", maxId: "pvp-dust-max", minParam: "pvpdustmin", maxParam: "pvpdustmax", kind: "advanced" },
  { key: "pvpCandy", label: "PvP build candy", minId: "pvp-candy-min", maxId: "pvp-candy-max", minParam: "pvpcandymin", maxParam: "pvpcandymax", kind: "advanced" },
];

const DATE_CONTROLS = [
  { key: "catch", label: "Catch date", fromId: "catch-from", toId: "catch-to", fromParam: "catchfrom", toParam: "catchto", kind: "advanced" },
  { key: "scan", label: "Scan date", fromId: "scan-from", toId: "scan-to", fromParam: "scanfrom", toParam: "scanto", kind: "advanced" },
  { key: "originalScan", label: "Original scan", fromId: "original-scan-from", toId: "original-scan-to", fromParam: "originalscanfrom", toParam: "originalscanto", kind: "advanced" },
];

const VALUE_LABELS = {
  any: "Any",
  yes: "Yes",
  no: "No",
  normal: "Normal",
  shadow: "Shadow",
  purified: "Purified",
  great: "Great League",
  ultra: "Ultra League",
  little: "Little League",
  ranked: "Ranked",
  unranked: "Unranked",
  complete: "Complete scan",
  "missing-any": "Needs rescan",
  "missing-ivs": "Missing IVs",
  "missing-level": "Missing level",
  "missing-moves": "Missing moves",
  "missing-pvp": "Missing selected-league PvP data",
};

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
    : Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatPercent(value) {
  return value === null || value === undefined ? "—" : `${Number(value).toFixed(2)}%`;
}

function selectedLeague() {
  return elements.leagueFilter.value;
}

function directionLabel(direction) {
  return direction === "asc" ? "ascending" : "descending";
}

function directionArrow(direction) {
  return direction === "asc" ? "↑" : "↓";
}

function sortDescription(criterion) {
  return `${Engine.SORT_FIELDS[criterion.field].label} ${directionArrow(criterion.direction)}`;
}

function numericValue(id) {
  const value = byId(id).value;
  return value === "" ? null : Number(value);
}

function collectFilters() {
  const ranges = {};
  for (const config of RANGE_CONTROLS) {
    ranges[config.key] = { min: numericValue(config.minId), max: numericValue(config.maxId) };
  }
  const dates = {};
  for (const config of DATE_CONTROLS) {
    dates[config.key] = { from: byId(config.fromId).value || null, to: byId(config.toId).value || null };
  }
  return {
    query: elements.search.value.trim(),
    species: elements.speciesFilter.value.trim(),
    form: elements.formFilter.value.trim(),
    gender: elements.genderFilter.value,
    status: elements.statusFilter.value,
    lucky: elements.luckyFilter.value,
    favorite: elements.favoriteFilter.value,
    pvpMarked: elements.pvpMarkedFilter.value,
    hundo: elements.hundoFilter.value,
    nundo: elements.nundoFilter.value,
    secondMove: elements.secondMoveFilter.value,
    dataQuality: elements.dataQualityFilter.value,
    fastMove: elements.fastMoveFilter.value.trim(),
    chargedMove: elements.chargedMoveFilter.value.trim(),
    evolution: elements.evolutionFilter.value.trim(),
    pvpStatus: elements.pvpStatusFilter.value,
    league: selectedLeague(),
    pvpEligibility: elements.pvpEligibilityFilter.value,
    ranges,
    dates,
  };
}

function invalidRanges() {
  const invalid = [];
  document.querySelectorAll("[aria-invalid='true']").forEach((input) => input.removeAttribute("aria-invalid"));
  for (const config of RANGE_CONTROLS) {
    const minimum = numericValue(config.minId);
    const maximum = numericValue(config.maxId);
    if (minimum !== null && maximum !== null && minimum > maximum) {
      invalid.push(config.label);
      byId(config.minId).setAttribute("aria-invalid", "true");
      byId(config.maxId).setAttribute("aria-invalid", "true");
    }
  }
  for (const config of DATE_CONTROLS) {
    const from = byId(config.fromId).value;
    const to = byId(config.toId).value;
    if (from && to && from > to) {
      invalid.push(config.label);
      byId(config.fromId).setAttribute("aria-invalid", "true");
      byId(config.toId).setAttribute("aria-invalid", "true");
    }
  }
  return invalid;
}

function updateUrl() {
  const params = new URLSearchParams();
  for (const config of SIMPLE_CONTROLS) {
    const value = byId(config.id).value;
    if (value !== config.defaultValue) params.set(config.param, value);
  }
  for (const config of RANGE_CONTROLS) {
    const minimum = byId(config.minId).value;
    const maximum = byId(config.maxId).value;
    if (minimum !== "") params.set(config.minParam, minimum);
    if (maximum !== "") params.set(config.maxParam, maximum);
  }
  for (const config of DATE_CONTROLS) {
    const from = byId(config.fromId).value;
    const to = byId(config.toId).value;
    if (from) params.set(config.fromParam, from);
    if (to) params.set(config.toParam, to);
  }
  if (Engine.serializeSorts(state.sorts) !== Engine.serializeSorts(Engine.DEFAULT_SORTS)) {
    params.set("sort", Engine.serializeSorts(state.sorts));
  }
  if (state.page > 1) params.set("page", String(state.page));
  const query = params.toString();
  history.replaceState(null, "", query ? `?${query}` : location.pathname);
}

function applyFilters({ resetPage = true } = {}) {
  if (resetPage) state.page = 1;
  const filters = collectFilters();
  const invalid = invalidRanges();
  elements.filterWarning.textContent = invalid.length
    ? `Minimum exceeds maximum for: ${invalid.join(", ")}.`
    : "";

  state.filtered = Engine.sortRecordsByCriteria(
    state.records.filter((record) => Engine.matchesRecord(record, filters)),
    state.sorts,
    selectedLeague(),
  );
  const totalPages = Math.max(1, Math.ceil(state.filtered.length / Number(elements.pageSize.value)));
  state.page = Math.min(Math.max(1, state.page), totalPages);
  renderActiveFilters();
  renderTable();
  updateUrl();
}

function activeFilterEntries() {
  const entries = [];
  for (const config of SIMPLE_CONTROLS) {
    if (config.chip === false) continue;
    const value = byId(config.id).value;
    if (value === config.defaultValue) continue;
    const shown = VALUE_LABELS[value] || value;
    entries.push({ kind: "simple", key: config.id, label: `${config.label}: ${shown}`, advanced: config.kind === "advanced" });
  }
  for (const config of RANGE_CONTROLS) {
    const minimum = byId(config.minId).value;
    const maximum = byId(config.maxId).value;
    if (!minimum && !maximum) continue;
    const bounds = minimum && maximum ? `${minimum}–${maximum}` : minimum ? `≥ ${minimum}` : `≤ ${maximum}`;
    entries.push({ kind: "range", key: config.key, label: `${config.label}: ${bounds}`, advanced: true });
  }
  for (const config of DATE_CONTROLS) {
    const from = byId(config.fromId).value;
    const to = byId(config.toId).value;
    if (!from && !to) continue;
    const bounds = from && to ? `${from} to ${to}` : from ? `from ${from}` : `through ${to}`;
    entries.push({ kind: "date", key: config.key, label: `${config.label}: ${bounds}`, advanced: true });
  }
  return entries;
}

function renderActiveFilters() {
  const entries = activeFilterEntries();
  elements.activeFilters.innerHTML = entries.length
    ? entries.map((entry) => `<button type="button" class="filter-chip" data-clear-kind="${entry.kind}" data-clear-key="${escapeHtml(entry.key)}"><span>${escapeHtml(entry.label)}</span><span aria-hidden="true">×</span></button>`).join("")
    : '<span class="muted">No filters applied</span>';
  const advancedCount = entries.filter((entry) => entry.advanced).length;
  elements.advancedCount.textContent = advancedCount ? String(advancedCount) : "";
  elements.advancedCount.hidden = advancedCount === 0;
}

function clearFilterChip(kind, key) {
  if (kind === "simple") {
    const config = SIMPLE_CONTROLS.find((item) => item.id === key);
    if (config) byId(config.id).value = config.defaultValue;
  } else if (kind === "range") {
    const config = RANGE_CONTROLS.find((item) => item.key === key);
    if (config) {
      byId(config.minId).value = "";
      byId(config.maxId).value = "";
    }
  } else if (kind === "date") {
    const config = DATE_CONTROLS.find((item) => item.key === key);
    if (config) {
      byId(config.fromId).value = "";
      byId(config.toId).value = "";
    }
  }
  applyFilters();
}

function renderSortControls() {
  const used = new Set(state.sorts.map(({ field }) => field));
  elements.sortLevels.innerHTML = state.sorts.map((criterion, index) => {
    const options = Object.entries(Engine.SORT_FIELDS).map(([field, config]) => {
      const selected = field === criterion.field ? " selected" : "";
      const disabled = used.has(field) && field !== criterion.field ? " disabled" : "";
      return `<option value="${field}"${selected}${disabled}>${escapeHtml(config.label)}</option>`;
    }).join("");
    return `<div class="sort-level" data-sort-index="${index}">
      <span class="sort-priority" aria-label="Sort priority ${index + 1}">${index + 1}</span>
      <label><span class="visually-hidden">Column for sort priority ${index + 1}</span><select data-sort-field="${index}">${options}</select></label>
      <label><span class="visually-hidden">Direction for sort priority ${index + 1}</span><select data-sort-direction="${index}">
        <option value="desc"${criterion.direction === "desc" ? " selected" : ""}>Descending</option>
        <option value="asc"${criterion.direction === "asc" ? " selected" : ""}>Ascending</option>
      </select></label>
      <div class="sort-actions">
        <button type="button" data-sort-up="${index}" aria-label="Move sort priority ${index + 1} earlier"${index === 0 ? " disabled" : ""}>↑</button>
        <button type="button" data-sort-down="${index}" aria-label="Move sort priority ${index + 1} later"${index === state.sorts.length - 1 ? " disabled" : ""}>↓</button>
        <button type="button" data-sort-remove="${index}" aria-label="Remove sort priority ${index + 1}"${state.sorts.length === 1 ? " disabled" : ""}>Remove</button>
      </div>
    </div>`;
  }).join("");

  const description = state.sorts.map((criterion, index) => `${index + 1}. ${sortDescription(criterion)}`).join(" → ");
  elements.sortSummary.textContent = `Active order: ${description}`;
  elements.sortCompact.textContent = description;
  elements.addSort.disabled = state.sorts.length >= Object.keys(Engine.SORT_FIELDS).length;

  elements.sortLevels.querySelectorAll("[data-sort-field]").forEach((select) => {
    select.addEventListener("change", () => {
      const index = Number(select.dataset.sortField);
      state.sorts[index] = { field: select.value, direction: state.sorts[index].direction };
      state.sorts = Engine.normalizeSorts(state.sorts);
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
  elements.sortLevels.querySelectorAll("[data-sort-up]").forEach((button) => button.addEventListener("click", () => moveSort(Number(button.dataset.sortUp), -1)));
  elements.sortLevels.querySelectorAll("[data-sort-down]").forEach((button) => button.addEventListener("click", () => moveSort(Number(button.dataset.sortDown), 1)));
  elements.sortLevels.querySelectorAll("[data-sort-remove]").forEach((button) => button.addEventListener("click", () => removeSort(Number(button.dataset.sortRemove))));
  renderSortIndicators();
}

function addSort() {
  const used = new Set(state.sorts.map(({ field }) => field));
  const field = Object.keys(Engine.SORT_FIELDS).find((candidate) => !used.has(candidate));
  if (!field) return;
  state.sorts.push({ field, direction: Engine.SORT_FIELDS[field].defaultDirection });
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
  state.sorts = Engine.normalizeSorts(state.sorts);
  renderSortControls();
  applyFilters();
}

function setPrimarySort(field) {
  const current = state.sorts[0];
  if (current?.field === field) current.direction = current.direction === "asc" ? "desc" : "asc";
  else state.sorts = [{ field, direction: Engine.SORT_FIELDS[field].defaultDirection }];
  renderSortControls();
  applyFilters();
}

function addOrToggleSort(field) {
  const index = state.sorts.findIndex((criterion) => criterion.field === field);
  if (index >= 0) state.sorts[index].direction = state.sorts[index].direction === "asc" ? "desc" : "asc";
  else state.sorts.push({ field, direction: Engine.SORT_FIELDS[field].defaultDirection });
  renderSortControls();
  applyFilters();
}

function renderSortIndicators() {
  document.querySelectorAll("[data-sort-key]").forEach((button) => {
    const field = button.dataset.sortKey;
    const index = state.sorts.findIndex((criterion) => criterion.field === field);
    const indicator = button.querySelector(".sort-indicator");
    const header = button.closest("th");
    const baseLabel = Engine.SORT_FIELDS[field]?.label || button.textContent.trim();
    if (index >= 0) {
      const criterion = state.sorts[index];
      indicator.textContent = `${index + 1}${directionArrow(criterion.direction)}`;
      button.setAttribute("aria-label", `${baseLabel}, sort priority ${index + 1}, ${directionLabel(criterion.direction)}. Click to make primary; Shift-click to add or toggle.`);
      header.setAttribute("aria-sort", index === 0 ? directionLabel(criterion.direction) : "other");
    } else {
      indicator.textContent = "";
      button.setAttribute("aria-label", `${baseLabel}, unsorted. Click to make primary; Shift-click to add.`);
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
  const data = record.pvp[selectedLeague()];
  if (data.rank_percent === null) return '<span class="muted">No ranking</span>';
  const target = data.evolution_name && data.evolution_name !== record.name
    ? `<small>as ${escapeHtml(data.evolution_name)}</small>`
    : "";
  const cost = data.dust_cost !== null || data.candy_cost !== null
    ? `<small>${formatNumber(data.dust_cost)} dust · ${formatNumber(data.candy_cost)} candy</small>`
    : "";
  return `<strong>${formatPercent(data.rank_percent)}</strong><small>Rank #${formatNumber(data.rank_number)} · stat ${formatNumber(data.stat_product)}</small>${target}${cost}`;
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
    const size = record.size.weight !== null || record.size.height !== null
      ? `<small>${formatNumber(record.size.weight)} weight · ${formatNumber(record.size.height)} height</small>`
      : "";
    return `<tr>
      <td><strong>#${String(record.pokemon_number).padStart(4, "0")} ${escapeHtml(record.name)}${gender}</strong>${form}</td>
      <td><strong>${formatNumber(record.cp)}</strong><small>${formatNumber(record.hp)} HP</small></td>
      <td><strong>${formatPercent(record.ivs.average_percent)}</strong><small>${formatNumber(record.ivs.attack)}/${formatNumber(record.ivs.defense)}/${formatNumber(record.ivs.stamina)} · ${formatNumber(record.ivs.total)}/45</small></td>
      <td><strong>${formatNumber(record.level.minimum)}</strong>${record.level.maximum !== record.level.minimum ? `<small>max ${formatNumber(record.level.maximum)}</small>` : ""}<small>${formatNumber(record.dust)} dust</small></td>
      <td><strong>${escapeHtml(record.moves.fast || "Unknown")}</strong><small>${chargedMoves || "No charged move scanned"}</small></td>
      <td><div class="badges">${statusBadges(record)}</div>${size}</td>
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

function populateDatalist(id, values) {
  const list = byId(id);
  list.innerHTML = [...new Set(values.filter(Boolean).map(String))]
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" }))
    .map((value) => `<option value="${escapeHtml(value)}"></option>`)
    .join("");
}

function populateDynamicOptions() {
  populateDatalist("species-options", state.records.map((record) => record.name));
  populateDatalist("form-options", state.records.map((record) => record.form));
  populateDatalist("fast-move-options", state.records.map((record) => record.moves.fast));
  populateDatalist("charged-move-options", state.records.flatMap((record) => [record.moves.charged, record.moves.charged_second]));
  populateDatalist("evolution-options", state.records.flatMap((record) => Object.values(record.pvp).map((league) => league.evolution_name)));
  const genders = [...new Set(state.records.map((record) => record.gender).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b));
  elements.genderFilter.innerHTML = '<option value="any">Any gender</option>' + genders.map((gender) => `<option value="${escapeHtml(gender)}">${escapeHtml(gender)}</option>`).join("");
}

function loadUrlState() {
  const params = new URLSearchParams(location.search);
  for (const config of SIMPLE_CONTROLS) byId(config.id).value = params.get(config.param) ?? config.defaultValue;
  if (elements.statusFilter.value === "all") elements.statusFilter.value = "any";
  const rawLeague = params.get("league");
  if (!["great", "ultra", "little"].includes(elements.leagueFilter.value)) elements.leagueFilter.value = "great";
  if (rawLeague && rawLeague !== "all" && !params.has("pvpelig")) elements.pvpEligibilityFilter.value = "ranked";
  for (const config of RANGE_CONTROLS) {
    byId(config.minId).value = params.get(config.minParam) || "";
    byId(config.maxId).value = params.get(config.maxParam) || "";
  }
  if (!params.has("ivmin") && params.has("miniv")) byId("iv-min").value = params.get("miniv");
  for (const config of DATE_CONTROLS) {
    byId(config.fromId).value = params.get(config.fromParam) || "";
    byId(config.toId).value = params.get(config.toParam) || "";
  }
  state.sorts = Engine.parseSortParam(params.get("sort"));
  state.page = Math.max(1, Number(params.get("page") || 1));
  const hasAdvanced = activeFilterEntries().some((entry) => entry.advanced);
  elements.advancedFilters.open = hasAdvanced;
}

function resetFilterControls({ keepPageSize = false } = {}) {
  const pageSize = elements.pageSize.value;
  for (const config of SIMPLE_CONTROLS) byId(config.id).value = config.defaultValue;
  if (keepPageSize) elements.pageSize.value = pageSize;
  for (const config of RANGE_CONTROLS) {
    byId(config.minId).value = "";
    byId(config.maxId).value = "";
  }
  for (const config of DATE_CONTROLS) {
    byId(config.fromId).value = "";
    byId(config.toId).value = "";
  }
}

function resetAll() {
  resetFilterControls();
  state.sorts = Engine.cloneDefaultSorts();
  state.page = 1;
  elements.presetSelect.value = "";
  renderSortControls();
  applyFilters({ resetPage: false });
}

function dateDaysAgo(days) {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

function applyPreset() {
  const preset = elements.presetSelect.value;
  if (!preset) return;
  resetFilterControls({ keepPageSize: true });
  state.sorts = Engine.cloneDefaultSorts();
  switch (preset) {
    case "high-iv":
      byId("iv-min").value = "96";
      state.sorts = [{ field: "iv", direction: "desc" }, { field: "cp", direction: "desc" }];
      break;
    case "hundos":
      elements.hundoFilter.value = "yes";
      break;
    case "nundos":
      elements.nundoFilter.value = "yes";
      state.sorts = [{ field: "name", direction: "asc" }, { field: "cp", direction: "desc" }];
      break;
    case "great-pvp":
    case "ultra-pvp":
    case "little-pvp":
      elements.leagueFilter.value = preset.split("-")[0];
      elements.pvpEligibilityFilter.value = "ranked";
      byId("pvp-percent-min").value = "98";
      state.sorts = [{ field: "pvp", direction: "desc" }, { field: "pvp-rank", direction: "asc" }, { field: "cp", direction: "desc" }];
      break;
    case "cheap-pvp":
      elements.pvpEligibilityFilter.value = "ranked";
      byId("pvp-percent-min").value = "95";
      byId("pvp-dust-max").value = "50000";
      state.sorts = [{ field: "pvp-dust", direction: "asc" }, { field: "pvp", direction: "desc" }];
      break;
    case "shadows":
      elements.statusFilter.value = "shadow";
      state.sorts = [{ field: "iv", direction: "desc" }, { field: "cp", direction: "desc" }];
      break;
    case "lucky":
      elements.luckyFilter.value = "yes";
      state.sorts = [{ field: "cp", direction: "desc" }, { field: "iv", direction: "desc" }];
      break;
    case "needs-rescan":
      elements.dataQualityFilter.value = "missing-any";
      state.sorts = [{ field: "scan", direction: "asc" }, { field: "name", direction: "asc" }];
      break;
    case "recent-catches":
      byId("catch-from").value = dateDaysAgo(30);
      state.sorts = [{ field: "catch", direction: "desc" }, { field: "cp", direction: "desc" }];
      break;
    default:
      break;
  }
  elements.advancedFilters.open = activeFilterEntries().some((entry) => entry.advanced);
  renderSortControls();
  applyFilters();
}

async function copyCurrentLink() {
  updateUrl();
  const url = location.href;
  try {
    await navigator.clipboard.writeText(url);
    elements.copyLink.textContent = "Link copied";
  } catch {
    const input = document.createElement("input");
    input.value = url;
    document.body.append(input);
    input.select();
    document.execCommand("copy");
    input.remove();
    elements.copyLink.textContent = "Link copied";
  }
  setTimeout(() => { elements.copyLink.textContent = "Copy search link"; }, 1600);
}

function bindEvents() {
  const filterIds = [
    ...SIMPLE_CONTROLS.map((config) => config.id),
    ...RANGE_CONTROLS.flatMap((config) => [config.minId, config.maxId]),
    ...DATE_CONTROLS.flatMap((config) => [config.fromId, config.toId]),
  ];
  for (const id of filterIds) byId(id).addEventListener("input", () => applyFilters());
  elements.activeFilters.addEventListener("click", (event) => {
    const button = event.target.closest("[data-clear-kind]");
    if (button) clearFilterChip(button.dataset.clearKind, button.dataset.clearKey);
  });
  elements.addSort.addEventListener("click", addSort);
  elements.reset.addEventListener("click", resetAll);
  elements.applyPreset.addEventListener("click", applyPreset);
  elements.copyLink.addEventListener("click", copyCurrentLink);
  document.querySelectorAll("[data-sort-key]").forEach((button) => {
    button.addEventListener("click", (event) => {
      if (event.shiftKey) addOrToggleSort(button.dataset.sortKey);
      else setPrimarySort(button.dataset.sortKey);
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

async function initialize() {
  Object.assign(elements, {
    search: byId("search"),
    speciesFilter: byId("species-filter"),
    formFilter: byId("form-filter"),
    genderFilter: byId("gender-filter"),
    statusFilter: byId("status-filter"),
    luckyFilter: byId("lucky-filter"),
    favoriteFilter: byId("favorite-filter"),
    pvpMarkedFilter: byId("pvp-marked-filter"),
    hundoFilter: byId("hundo-filter"),
    nundoFilter: byId("nundo-filter"),
    secondMoveFilter: byId("second-move-filter"),
    dataQualityFilter: byId("data-quality-filter"),
    fastMoveFilter: byId("fast-move-filter"),
    chargedMoveFilter: byId("charged-move-filter"),
    evolutionFilter: byId("evolution-filter"),
    pvpStatusFilter: byId("pvp-status-filter"),
    leagueFilter: byId("league-filter"),
    pvpEligibilityFilter: byId("pvp-eligibility-filter"),
    pageSize: byId("page-size"),
    presetSelect: byId("preset-select"),
    applyPreset: byId("apply-preset"),
    copyLink: byId("copy-link"),
    reset: byId("reset-filters"),
    advancedFilters: byId("advanced-filters"),
    advancedCount: byId("advanced-count"),
    activeFilters: byId("active-filters"),
    filterWarning: byId("filter-warning"),
    addSort: byId("add-sort"),
    sortLevels: byId("sort-levels"),
    sortSummary: byId("sort-summary"),
    sortCompact: byId("sort-compact"),
    resultCount: byId("result-count"),
    body: byId("pokemon-body"),
    previous: byId("previous-page"),
    next: byId("next-page"),
    pageLabel: byId("page-label"),
  });

  try {
    const [collectionResponse, summaryResponse] = await Promise.all([
      fetch("data/pokemon.json"),
      fetch("data/collection-summary.json"),
    ]);
    if (!collectionResponse.ok || !summaryResponse.ok) throw new Error("Collection data could not be loaded");
    const collection = await collectionResponse.json();
    state.records = collection.records;
    state.summary = await summaryResponse.json();
    populateDynamicOptions();
    loadUrlState();
    renderSummary();
    renderSortControls();
    bindEvents();
    applyFilters({ resetPage: false });
  } catch (error) {
    elements.resultCount.textContent = "Collection data could not be loaded";
    elements.body.innerHTML = '<tr><td colspan="8">The dashboard data failed to load. Use the CSV or JSON download links above.</td></tr>';
  }
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", initialize);
}
