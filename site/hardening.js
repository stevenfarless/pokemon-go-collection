"use strict";

(function exposeHardening(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionHardening = api;
  if (root?.document && root?.location) api.install(root);
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const SELECT_VALUES = Object.freeze({
    gender: new Set(["any", "Male", "Female", "Genderless", "Unknown"]),
    status: new Set(["any", "normal", "shadow", "purified"]),
    lucky: new Set(["any", "yes", "no"]),
    fav: new Set(["any", "yes", "no"]),
    pvpm: new Set(["any", "yes", "no"]),
    hundo: new Set(["any", "yes", "no"]),
    nundo: new Set(["any", "yes", "no"]),
    second: new Set(["any", "yes", "no"]),
    quality: new Set(["any", "complete", "missing-any", "missing-ivs", "missing-level", "missing-moves", "missing-pvp"]),
    pvpstatus: new Set(["any", "normal", "shadow", "purified"]),
    league: new Set(["great", "ultra", "little"]),
    pvpelig: new Set(["any", "ranked", "unranked"]),
    size: new Set(["25", "50", "100", "250"]),
  });

  const TEXT_LIMITS = Object.freeze({
    q: 500,
    species: 120,
    form: 120,
    fast: 120,
    charged: 120,
    evo: 120,
  });

  const NUMBER_RULES = Object.freeze({
    dexmin: [1, null], dexmax: [1, null],
    cpmin: [0, null], cpmax: [0, null],
    hpmin: [0, null], hpmax: [0, null],
    ivmin: [0, 100], ivmax: [0, 100],
    ivtotalmin: [0, 45], ivtotalmax: [0, 45],
    atkmin: [0, 15], atkmax: [0, 15],
    defmin: [0, 15], defmax: [0, 15],
    staminamin: [0, 15], staminamax: [0, 15],
    levelmin: [1, 60], levelmax: [1, 60],
    levelcapmin: [1, 60], levelcapmax: [1, 60],
    dustmin: [0, null], dustmax: [0, null],
    weightmin: [0, null], weightmax: [0, null],
    heightmin: [0, null], heightmax: [0, null],
    pvpmin: [0, 100], pvpmax: [0, 100],
    pvprankmin: [1, null], pvprankmax: [1, null],
    pvpstatmin: [0, null], pvpstatmax: [0, null],
    pvpdustmin: [0, null], pvpdustmax: [0, null],
    pvpcandymin: [0, null], pvpcandymax: [0, null],
  });

  const RANGE_PAIRS = Object.freeze([
    ["dexmin", "dexmax"], ["cpmin", "cpmax"], ["hpmin", "hpmax"],
    ["ivmin", "ivmax"], ["ivtotalmin", "ivtotalmax"],
    ["atkmin", "atkmax"], ["defmin", "defmax"], ["staminamin", "staminamax"],
    ["levelmin", "levelmax"], ["levelcapmin", "levelcapmax"],
    ["dustmin", "dustmax"], ["weightmin", "weightmax"], ["heightmin", "heightmax"],
    ["pvpmin", "pvpmax"], ["pvprankmin", "pvprankmax"],
    ["pvpstatmin", "pvpstatmax"], ["pvpdustmin", "pvpdustmax"],
    ["pvpcandymin", "pvpcandymax"],
  ]);

  const DATE_PAIRS = Object.freeze([
    ["catchfrom", "catchto"],
    ["scanfrom", "scanto"],
    ["originalscanfrom", "originalscanto"],
  ]);

  const LEGACY_SORTS = new Set(["cp-desc", "iv-desc", "name-asc", "dex-asc", "recent-scan", "pvp-desc"]);

  const REASON_LABELS = Object.freeze({
    "iv-average": "overall IV percentage",
    "attack-iv": "Attack IV",
    "defense-iv": "Defense IV",
    "stamina-iv": "HP IV",
    "level-minimum": "minimum level",
    "level-maximum": "maximum level",
    "fast-move": "fast move",
    "charged-move": "first charged move",
  });

  function isMissing(value) {
    return value === null || value === undefined || value === "";
  }

  function validIsoDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return false;
    const date = new Date(`${value}T00:00:00Z`);
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }

  function validSort(value, engine) {
    if (!value) return null;
    if (LEGACY_SORTS.has(value)) return engine?.serializeSorts?.(engine.parseSortParam(value)) || value;
    const used = new Set();
    const criteria = [];
    for (const part of String(value).split(",")) {
      const [field, direction, extra] = part.split(":");
      if (extra !== undefined || !engine?.SORT_FIELDS?.[field] || !["asc", "desc"].includes(direction) || used.has(field)) continue;
      used.add(field);
      criteria.push({ field, direction });
    }
    return criteria.length ? engine.serializeSorts(criteria) : null;
  }

  function sanitizeSearchParams(search, engine) {
    const source = new URLSearchParams(String(search || "").replace(/^\?/, ""));
    const clean = new URLSearchParams();

    if (!source.has("ivmin") && source.has("miniv")) source.set("ivmin", source.get("miniv"));

    for (const [key, allowed] of Object.entries(SELECT_VALUES)) {
      let value = source.get(key);
      if (key === "status" && value === "all") value = "any";
      if (key === "league" && value === "all") value = "great";
      if (value !== null && allowed.has(value)) {
        const defaultValues = new Set(["any", "great", "50"]);
        if (!defaultValues.has(value) || (key === "league" && value !== "great") || (key === "size" && value !== "50")) clean.set(key, value);
      }
    }

    for (const [key, limit] of Object.entries(TEXT_LIMITS)) {
      const value = (source.get(key) || "").trim();
      if (value) clean.set(key, value.slice(0, limit));
    }

    for (const [key, [minimum, maximum]] of Object.entries(NUMBER_RULES)) {
      const raw = source.get(key);
      if (raw === null || raw.trim() === "") continue;
      const value = Number(raw);
      if (!Number.isFinite(value) || value < minimum || (maximum !== null && value > maximum)) continue;
      clean.set(key, String(value));
    }

    for (const [minimumKey, maximumKey] of RANGE_PAIRS) {
      if (!clean.has(minimumKey) || !clean.has(maximumKey)) continue;
      if (Number(clean.get(minimumKey)) > Number(clean.get(maximumKey))) {
        clean.delete(minimumKey);
        clean.delete(maximumKey);
      }
    }

    for (const [fromKey, toKey] of DATE_PAIRS) {
      const from = source.get(fromKey);
      const to = source.get(toKey);
      if (from && validIsoDate(from)) clean.set(fromKey, from);
      if (to && validIsoDate(to)) clean.set(toKey, to);
      if (clean.has(fromKey) && clean.has(toKey) && clean.get(fromKey) > clean.get(toKey)) {
        clean.delete(fromKey);
        clean.delete(toKey);
      }
    }

    const page = Number(source.get("page"));
    if (Number.isFinite(page) && Number.isInteger(page) && page > 1) clean.set("page", String(page));

    const sort = validSort(source.get("sort"), engine);
    if (sort && sort !== "cp:desc") clean.set("sort", sort);

    return clean.toString();
  }

  function missingScanReasons(record) {
    const reasons = [];
    if (isMissing(record?.ivs?.average_percent)) reasons.push("iv-average");
    if (isMissing(record?.ivs?.attack)) reasons.push("attack-iv");
    if (isMissing(record?.ivs?.defense)) reasons.push("defense-iv");
    if (isMissing(record?.ivs?.stamina)) reasons.push("stamina-iv");
    if (isMissing(record?.level?.minimum)) reasons.push("level-minimum");
    if (isMissing(record?.level?.maximum)) reasons.push("level-maximum");
    if (isMissing(record?.moves?.fast)) reasons.push("fast-move");
    if (isMissing(record?.moves?.charged)) reasons.push("charged-move");
    return reasons;
  }

  function matchesDataQuality(record, quality, league = "great") {
    const reasons = missingScanReasons(record);
    switch (quality) {
      case "complete": return reasons.length === 0;
      case "missing-any": return reasons.length > 0;
      case "missing-ivs": return reasons.some((reason) => reason.includes("iv"));
      case "missing-level": return reasons.some((reason) => reason.startsWith("level-"));
      case "missing-moves": return reasons.some((reason) => reason.endsWith("move"));
      case "missing-pvp": return isMissing(record?.pvp?.[league]?.rank_percent);
      default: return true;
    }
  }

  function installEngineOverrides(engine) {
    if (!engine || engine.__hardeningInstalled) return engine;
    const originalMatchesRecord = engine.matchesRecord.bind(engine);
    engine.matchesRecord = (record, filters = {}) => {
      const quality = filters.dataQuality || "any";
      const baseFilters = quality === "any" ? filters : { ...filters, dataQuality: "any" };
      if (!originalMatchesRecord(record, baseFilters)) return false;
      return matchesDataQuality(record, quality, filters.league || "great");
    };
    engine.missingScanReasons = missingScanReasons;
    engine.matchesDataQuality = matchesDataQuality;
    Object.defineProperty(engine, "__hardeningInstalled", { value: true });
    return engine;
  }

  function installPolicyNote(documentObject) {
    const select = documentObject.getElementById("data-quality-filter");
    const warning = documentObject.getElementById("filter-warning");
    if (!select || !warning || documentObject.getElementById("scan-quality-policy")) return;

    const note = documentObject.createElement("p");
    note.id = "scan-quality-policy";
    note.className = "scan-policy-note";
    note.hidden = true;
    warning.insertAdjacentElement("afterend", note);

    const update = () => {
      const quality = select.value;
      if (!["complete", "missing-any", "missing-ivs", "missing-level", "missing-moves"].includes(quality)) {
        note.hidden = true;
        note.textContent = "";
        return;
      }
      let labels = Object.values(REASON_LABELS);
      if (quality === "missing-ivs") labels = labels.filter((label) => label.includes("IV"));
      if (quality === "missing-level") labels = labels.filter((label) => label.includes("level"));
      if (quality === "missing-moves") labels = labels.filter((label) => label.includes("move"));
      note.textContent = quality === "complete"
        ? `Complete scans contain ${labels.join(", ")}.`
        : `Rescan reason: missing ${labels.join(", ")}.`;
      note.hidden = false;
    };

    select.addEventListener("input", update);
    select.addEventListener("change", update);
    update();
  }

  function install(root) {
    const engine = installEngineOverrides(root.CollectionFilterEngine);
    const canonical = sanitizeSearchParams(root.location.search, engine);
    const current = String(root.location.search || "").replace(/^\?/, "");
    if (canonical !== current) {
      root.history.replaceState(null, "", canonical ? `${root.location.pathname}?${canonical}${root.location.hash || ""}` : `${root.location.pathname}${root.location.hash || ""}`);
    }
    root.document.addEventListener("DOMContentLoaded", () => installPolicyNote(root.document), { once: true });
  }

  return {
    REASON_LABELS,
    validIsoDate,
    sanitizeSearchParams,
    missingScanReasons,
    matchesDataQuality,
    installEngineOverrides,
    installPolicyNote,
    install,
  };
});
