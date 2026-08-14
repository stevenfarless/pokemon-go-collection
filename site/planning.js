"use strict";

(function exposePlanning(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionPlanning = api;
  if (root?.document) {
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", () => api.install(root), { once: true });
    else api.install(root);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const GOALS_KEY = "pokemon-go-collection:goals:v1";
  const BUDGET_KEY = "pokemon-go-collection:planner-budget:v1";
  const GOALS_VERSION = 1;
  const POWER_UP_MODEL_VERSION = "2026-08-14.1";
  const POWER_UP_SOURCE = Object.freeze({
    classification: "Verified community data",
    name: "Pokémon GO Hub power-up cost guide",
    url: "https://pokemongohub.net/post/guide/guide-to-power-up-costs-in-pokemon-go/",
    xl_url: "https://pokemongohub.net/post/guide/xl-candy-guide-how-to-get-power-up-costs-and-mechanics/",
    verified_date: "2026-08-14",
  });

  const PRE40_TIERS = Object.freeze([
    [1, 2.5, 200, 1], [3, 4.5, 400, 1], [5, 6.5, 600, 1], [7, 8.5, 800, 1],
    [9, 10.5, 1000, 1], [11, 12.5, 1300, 2], [13, 14.5, 1600, 2], [15, 16.5, 1900, 2],
    [17, 18.5, 2200, 2], [19, 20.5, 2500, 2], [21, 22.5, 3000, 3], [23, 24.5, 3500, 3],
    [25, 25.5, 4000, 3], [26, 26.5, 4000, 4], [27, 28.5, 4500, 4], [29, 30.5, 5000, 4],
    [31, 32.5, 6000, 6], [33, 34.5, 7000, 8], [35, 36.5, 8000, 10], [37, 38.5, 9000, 12],
    [39, 39.5, 10000, 15],
  ]);
  const POST40_STEPS = new Map([
    [40, [10000, 10]], [40.5, [10000, 10]], [41, [11000, 10]], [41.5, [11000, 10]],
    [42, [11000, 12]], [42.5, [11000, 12]], [43, [12000, 12]], [43.5, [12000, 12]],
    [44, [12000, 15]], [44.5, [12000, 15]], [45, [13000, 15]], [45.5, [13000, 15]],
    [46, [13000, 17]], [46.5, [13000, 17]], [47, [14000, 17]], [47.5, [14000, 17]],
    [48, [14000, 20]], [48.5, [14000, 20]], [49, [15000, 20]], [49.5, [15000, 20]],
  ]);
  const TEAM_FEEDS = Object.freeze({
    great: { feed: "great-league", size: 3, uniqueSpecies: true, label: "Great League" },
    ultra: { feed: "ultra-league", size: 3, uniqueSpecies: true, label: "Ultra League" },
    little: { feed: "little-league", size: 3, uniqueSpecies: true, label: "Little League" },
    master: { feed: "master-league", size: 3, uniqueSpecies: true, label: "Master League" },
    raid: { feed: "raid-attacker-inputs", size: 6, uniqueSpecies: false, label: "Raid inventory" },
    rocket: { feed: "rocket-battle-inputs", size: 3, uniqueSpecies: false, label: "Rocket inventory" },
    mega: { feed: "mega-candidates", size: 1, uniqueSpecies: false, label: "Mega/Primal candidate" },
  });
  const GOAL_TYPES = Object.freeze({
    living: "Living species/form collection",
    hundo: "Hundo species/forms",
    lucky: "Lucky species/forms",
    great: "Great League candidates",
    ultra: "Ultra League candidates",
    little: "Little League candidates",
    mega: "Mega/Primal-capable owned species",
    shiny: "Shiny collection",
    costume: "Costume collection",
  });

  const normalize = (value) => String(value ?? "").trim().toLocaleLowerCase();
  const slug = (value) => normalize(value).replace(/[’']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "normal";
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
  const asNumber = (value) => {
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };
  const recordId = (record) => String(record?.identity?.record_id || record?.record_id || "");
  const speciesKey = (record) => `${Number(record?.pokemon_number || 0)}:${slug(record?.form)}`;
  const money = (value) => Number(value || 0).toLocaleString();

  function isHalfLevel(value) {
    const number = asNumber(value);
    return number !== null && number >= 1 && number <= 50 && Math.abs(number * 2 - Math.round(number * 2)) < 1e-9;
  }

  function basePowerUpStep(level) {
    const current = Number(level);
    if (current < 40) {
      const tier = PRE40_TIERS.find(([from, to]) => current >= from && current <= to);
      return tier ? { dust: tier[2], candy: tier[3], xl: 0 } : null;
    }
    const post = POST40_STEPS.get(current);
    return post ? { dust: post[0], candy: 0, xl: post[1] } : null;
  }

  function costMultipliers(status = {}) {
    let dust = status?.lucky ? 0.5 : 1;
    let candy = 1;
    let xl = 1;
    if (status?.shadow_purified === "shadow") {
      dust *= 1.2;
      candy *= 1.2;
      xl *= 1.2;
    } else if (status?.shadow_purified === "purified") {
      dust *= 0.9;
      candy *= 0.9;
      xl *= 0.9;
    }
    return { dust, candy, xl };
  }

  function modifiedStepCost(base, status) {
    const modifier = costMultipliers(status);
    return {
      dust: Math.round(base.dust * modifier.dust),
      candy: Math.ceil(base.candy * modifier.candy),
      xl: Math.ceil(base.xl * modifier.xl),
    };
  }

  function powerUpCost(fromLevel, toLevel, status = {}) {
    const from = asNumber(fromLevel);
    const to = asNumber(toLevel);
    if (!isHalfLevel(from) || !isHalfLevel(to) || to < from) {
      return { status: "unavailable", reason: "Levels must be known half-level values from 1 through 50.", dust: null, candy: null, xl: null };
    }
    if (to === from) return { status: "known", dust: 0, candy: 0, xl: 0, steps: 0, model_version: POWER_UP_MODEL_VERSION };
    let dust = 0;
    let candy = 0;
    let xl = 0;
    let steps = 0;
    for (let level = from; level < to - 0.001; level += 0.5) {
      const base = basePowerUpStep(Number(level.toFixed(1)));
      if (!base) return { status: "unavailable", reason: `No versioned power-up step is available at level ${level}.`, dust: null, candy: null, xl: null };
      const cost = modifiedStepCost(base, status);
      dust += cost.dust;
      candy += cost.candy;
      xl += cost.xl;
      steps += 1;
    }
    return { status: "known", dust, candy, xl, steps, model_version: POWER_UP_MODEL_VERSION, source: POWER_UP_SOURCE };
  }

  function powerUpCostRange(levelRange, targetLevel, status = {}) {
    const minimum = asNumber(levelRange?.minimum);
    const maximum = asNumber(levelRange?.maximum);
    if (!isHalfLevel(minimum) || !isHalfLevel(maximum)) {
      return { status: "unavailable", reason: "Current level is missing or not exact enough for the power-up model." };
    }
    const lowStart = Math.min(minimum, maximum);
    const highStart = Math.max(minimum, maximum);
    const maximumCost = powerUpCost(lowStart, Math.max(lowStart, targetLevel), status);
    const minimumCost = powerUpCost(highStart, Math.max(highStart, targetLevel), status);
    if (maximumCost.status !== "known" || minimumCost.status !== "known") return maximumCost.status !== "known" ? maximumCost : minimumCost;
    return {
      status: "known",
      exact: lowStart === highStart,
      current_level: { minimum: lowStart, maximum: highStart },
      target_level: targetLevel,
      minimum_cost: minimumCost,
      maximum_cost: maximumCost,
      model_version: POWER_UP_MODEL_VERSION,
    };
  }

  function cpAtLevel(baseStats, ivs, multiplier) {
    const attack = asNumber(baseStats?.attack);
    const defense = asNumber(baseStats?.defense);
    const stamina = asNumber(baseStats?.stamina);
    const atkIv = asNumber(ivs?.attack);
    const defIv = asNumber(ivs?.defense);
    const staIv = asNumber(ivs?.stamina);
    const cpm = asNumber(multiplier);
    if ([attack, defense, stamina, atkIv, defIv, staIv, cpm].some((value) => value === null)) return null;
    return Math.max(10, Math.floor(((attack + atkIv) * Math.sqrt(defense + defIv) * Math.sqrt(stamina + staIv) * cpm * cpm) / 10));
  }

  function buildKnowledgeIndex(payload) {
    const byDex = new Map();
    const byName = new Map();
    const cpms = new Map();
    for (const item of payload?.mechanics?.cp_multiplier_levels || []) cpms.set(Number(item.level), Number(item.multiplier));
    for (const entry of payload?.entries || []) {
      const dex = Number(entry.dex);
      if (!byDex.has(dex)) byDex.set(dex, []);
      byDex.get(dex).push(entry);
      const names = [entry.display_name, entry.base_name, entry.species_id].filter(Boolean);
      for (const name of names) {
        const key = slug(name);
        if (!byName.has(key)) byName.set(key, []);
        byName.get(key).push(entry);
      }
    }
    return { byDex, byName, cpms, datasetVersion: payload?.dataset_version || null, classification: payload?.classification || null };
  }

  function knowledgeForRecord(record, knowledge) {
    const entries = knowledge?.byDex?.get(Number(record?.pokemon_number)) || [];
    if (entries.length <= 1) return entries[0] || null;
    const form = slug(record?.form || "normal");
    const exact = entries.find((entry) => slug(entry.form_key || "normal") === form || (entry.form_aliases || []).some((alias) => slug(alias) === form));
    if (exact) return exact;
    const ordinary = entries.filter((entry) => !entry.transformation?.eligible);
    return ordinary.length === 1 ? ordinary[0] : null;
  }

  function knowledgeForName(name, form, knowledge) {
    const matches = knowledge?.byName?.get(slug(name)) || [];
    if (matches.length <= 1) return matches[0] || null;
    const wantedForm = slug(form || "normal");
    return matches.find((entry) => slug(entry.form_key || "normal") === wantedForm) || matches.find((entry) => !entry.transformation?.eligible) || null;
  }

  function findLeagueTarget(entry, ivs, cap, knowledge, maximumLevel = 50) {
    if (!entry || !knowledge?.cpms?.size) return { status: "unavailable", reason: "Species mechanics are unavailable." };
    if ([ivs?.attack, ivs?.defense, ivs?.stamina].some((value) => asNumber(value) === null)) return { status: "unavailable", reason: "Exact IVs are required to calculate league CP." };
    let best = null;
    for (let level = 1; level <= maximumLevel; level += 0.5) {
      const cpm = knowledge.cpms.get(Number(level.toFixed(1)));
      if (!cpm) continue;
      const cp = cpAtLevel(entry.base_stats, ivs, cpm);
      if (cp !== null && cp <= cap) best = { level, cp };
    }
    return best ? { status: "known", ...best } : { status: "unavailable", reason: `This IV/species combination does not fit under ${cap} CP.` };
  }

  function scenarioForRecord(record, investment, knowledge, scenario) {
    const currentEntry = knowledgeForRecord(record, knowledge);
    const pvp = record?.pvp || {};
    const status = record?.status || {};
    const result = {
      record_id: recordId(record),
      name: record?.name,
      form: record?.form,
      scenario,
      irreversible: false,
      assumptions: [],
      warnings: [],
      source_versions: {
        knowledge_dataset: knowledge?.datasetVersion || null,
        power_up_model: POWER_UP_MODEL_VERSION,
      },
    };

    if (["level40", "level50"].includes(scenario)) {
      const targetLevel = scenario === "level40" ? 40 : 50;
      result.action = `Power current species to level ${targetLevel}`;
      result.target_level = targetLevel;
      result.cost = powerUpCostRange(record?.level, targetLevel, status);
      const cpm = knowledge?.cpms?.get(targetLevel);
      result.resulting_cp = currentEntry && cpm ? cpAtLevel(currentEntry.base_stats, record?.ivs, cpm) : null;
      if (result.resulting_cp === null) result.warnings.push("Resulting CP requires a successful knowledge join and exact IVs.");
      return result;
    }

    if (["great", "ultra", "little"].includes(scenario)) {
      const cap = scenario === "little" ? 500 : scenario === "great" ? 1500 : 2500;
      const league = pvp?.[scenario] || {};
      const targetEntry = league.evolution_name
        ? knowledgeForName(league.evolution_name, league.evolution_form, knowledge)
        : currentEntry;
      const target = findLeagueTarget(targetEntry, record?.ivs, cap, knowledge);
      result.action = `Build toward highest legal ${scenario} league level`;
      result.cap = cap;
      result.target_species = targetEntry?.display_name || league.evolution_name || record?.name;
      result.target = target;
      result.irreversible = Boolean(league.evolution_name && normalize(league.evolution_name) !== normalize(record?.name));
      if (target.status === "known") result.cost = powerUpCostRange(record?.level, target.level, status);
      else result.cost = { status: "unavailable", reason: target.reason };
      const exportedBuild = investment?.derived?.pvp_builds?.find((item) => item.league === scenario);
      result.poke_genie_build_cost = exportedBuild || null;
      if (result.irreversible) result.warnings.push("The Poke Genie league target uses an evolution. Evolution cannot be undone.");
      result.assumptions.push("CP calculation uses the pinned species base stats, exact IVs, and CP multiplier table.");
      return result;
    }

    if (scenario === "second-move") {
      result.action = "Unlock second Charged Move";
      result.irreversible = true;
      result.cost = investment?.derived?.second_charged_move || null;
      if (!result.cost || result.cost.listed_stardust_cost === null || result.cost.listed_regular_candy_cost === null) {
        result.warnings.push("The current versioned source does not provide every second-move currency cost, so missing values remain unknown.");
      }
      return result;
    }

    if (scenario === "evolution") {
      result.action = "Review evolution branches";
      result.irreversible = true;
      result.evolution = investment?.derived?.evolution || null;
      result.warnings.push("Evolution is irreversible. Special requirements and Candy costs remain unknown when the pinned source does not provide them.");
      return result;
    }

    return { ...result, action: "Unavailable scenario", warnings: ["The requested scenario is not implemented by this deterministic model."] };
  }

  function pvpCandidateValue(candidate) {
    const pvp = candidate?.pvp || {};
    return {
      rankPercent: asNumber(pvp.rank_percent) ?? -1,
      rankNumber: asNumber(pvp.rank_number) ?? Number.MAX_SAFE_INTEGER,
      dust: asNumber(pvp.dust_cost),
      candy: asNumber(pvp.candy_cost),
    };
  }

  function compareTeamCandidates(mode, left, right) {
    if (["great", "ultra", "little"].includes(mode)) {
      const a = pvpCandidateValue(left);
      const b = pvpCandidateValue(right);
      return (b.rankPercent - a.rankPercent)
        || (a.rankNumber - b.rankNumber)
        || ((a.dust ?? Number.MAX_SAFE_INTEGER) - (b.dust ?? Number.MAX_SAFE_INTEGER))
        || ((a.candy ?? Number.MAX_SAFE_INTEGER) - (b.candy ?? Number.MAX_SAFE_INTEGER))
        || ((Number(right.cp) || 0) - (Number(left.cp) || 0))
        || String(left.record_id).localeCompare(String(right.record_id));
    }
    if (mode === "master") {
      return ((Number(right.ivs?.total) || -1) - (Number(left.ivs?.total) || -1))
        || ((Number(right.cp) || 0) - (Number(left.cp) || 0))
        || String(left.record_id).localeCompare(String(right.record_id));
    }
    if (mode === "raid") {
      return ((Number(right.knowledge?.base_stats?.attack) || 0) - (Number(left.knowledge?.base_stats?.attack) || 0))
        || ((Number(right.cp) || 0) - (Number(left.cp) || 0))
        || String(left.record_id).localeCompare(String(right.record_id));
    }
    return ((Number(right.cp) || 0) - (Number(left.cp) || 0)) || String(left.record_id).localeCompare(String(right.record_id));
  }

  function buildOwnedTeam(candidates, mode, lockedIds = []) {
    const config = TEAM_FEEDS[mode];
    if (!config) return { status: "unavailable", reason: "Unknown team mode.", team: [], alternatives: [] };
    const pool = Array.isArray(candidates) ? [...candidates] : [];
    const byId = new Map(pool.map((candidate) => [String(candidate.record_id), candidate]));
    const locks = [...new Set(lockedIds.map(String))].map((id) => byId.get(id)).filter(Boolean).slice(0, 2);
    const team = [];
    const usedSpecies = new Set();
    const warnings = [];

    for (const candidate of locks) {
      const key = Number(candidate.pokemon_number);
      if (config.uniqueSpecies && usedSpecies.has(key)) {
        warnings.push(`Locked ${candidate.name} duplicates a species already locked and was skipped.`);
        continue;
      }
      team.push(candidate);
      usedSpecies.add(key);
    }

    pool.sort((left, right) => compareTeamCandidates(mode, left, right));
    for (const candidate of pool) {
      if (team.length >= config.size) break;
      if (team.some((item) => item.record_id === candidate.record_id)) continue;
      const key = Number(candidate.pokemon_number);
      if (config.uniqueSpecies && usedSpecies.has(key)) continue;
      team.push(candidate);
      usedSpecies.add(key);
    }

    const alternatives = pool.filter((candidate) => !team.some((item) => item.record_id === candidate.record_id)).slice(0, config.size * 2);
    if (team.length < config.size) warnings.push(`Only ${team.length} eligible owned records were available for a ${config.size}-member team.`);
    return {
      status: team.length ? "available" : "unavailable",
      mode,
      team_size: config.size,
      team,
      alternatives,
      warnings,
      current_meta_used: false,
      explanation: ["Team members come only from the owned candidate feed.", "Ordering uses collection/Poke Genie inputs and does not claim current matchup or raid-boss optimality."],
    };
  }

  function projectForLeague(investment, league) {
    const build = investment?.derived?.pvp_builds?.find((item) => item.league === league);
    if (!build) return null;
    return {
      record_id: investment.record_id,
      pokemon_number: investment.pokemon_number,
      name: investment.name,
      form: investment.form,
      league,
      rank_percent: asNumber(build.rank_percent),
      rank_number: asNumber(build.rank_number),
      dust: asNumber(build.stardust_cost),
      candy: asNumber(build.regular_candy_cost),
      xl: asNumber(build.xl_candy_cost),
      unknown_xl: build.xl_candy_cost === null || build.xl_candy_cost === undefined,
    };
  }

  function projectComparator(objective) {
    return (left, right) => {
      const aDust = left.dust ?? Number.MAX_SAFE_INTEGER;
      const bDust = right.dust ?? Number.MAX_SAFE_INTEGER;
      const aCandy = left.candy ?? Number.MAX_SAFE_INTEGER;
      const bCandy = right.candy ?? Number.MAX_SAFE_INTEGER;
      const aRank = left.rank_percent ?? -1;
      const bRank = right.rank_percent ?? -1;
      if (objective === "highest-rank") return (bRank - aRank) || (aDust - bDust) || (aCandy - bCandy) || String(left.record_id).localeCompare(String(right.record_id));
      if (objective === "value") {
        const aValue = aRank / (1 + aDust / 1000 + aCandy);
        const bValue = bRank / (1 + bDust / 1000 + bCandy);
        return (bValue - aValue) || (bRank - aRank) || String(left.record_id).localeCompare(String(right.record_id));
      }
      return (aDust - bDust) || (aCandy - bCandy) || (bRank - aRank) || String(left.record_id).localeCompare(String(right.record_id));
    };
  }

  function optimizeBudget(investments, options = {}) {
    const league = ["great", "ultra", "little"].includes(options.league) ? options.league : "great";
    const dustBudget = Math.max(0, Number(options.dustBudget) || 0);
    const candyBudget = Math.max(0, Number(options.candyBudget) || 0);
    const objective = ["max-builds", "highest-rank", "value"].includes(options.objective) ? options.objective : "max-builds";
    const projects = investments.map((item) => projectForLeague(item, league)).filter(Boolean);
    const unknown = projects.filter((item) => item.dust === null || item.candy === null);
    const known = projects.filter((item) => item.dust !== null && item.candy !== null).sort(projectComparator(objective));
    const selected = [];
    const excluded = [];
    let dustUsed = 0;
    let candyUsed = 0;
    for (const project of known) {
      if (dustUsed + project.dust <= dustBudget && candyUsed + project.candy <= candyBudget) {
        selected.push(project);
        dustUsed += project.dust;
        candyUsed += project.candy;
      } else {
        excluded.push({ ...project, exclusion_reason: dustUsed + project.dust > dustBudget ? "stardust_budget" : "candy_budget" });
      }
    }
    return {
      league,
      objective,
      budget: { stardust: dustBudget, candy: candyBudget },
      used: { stardust: dustUsed, candy: candyUsed },
      remaining: { stardust: dustBudget - dustUsed, candy: candyBudget - candyUsed },
      selected,
      excluded,
      unknown_cost: unknown,
      deterministic: true,
      warning: "The optimizer ranks known Poke Genie build costs under the stated objective. XL Candy, team fit, current meta strength, and missing costs are not silently estimated.",
    };
  }

  function normalizeGoal(raw) {
    const kind = String(raw?.kind || "living");
    if (!GOAL_TYPES[kind]) return null;
    const target = Math.max(1, Math.floor(Number(raw?.target) || 1));
    const threshold = Math.min(100, Math.max(0, Number(raw?.threshold) || 98));
    const id = String(raw?.id || `goal-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
    const name = String(raw?.name || GOAL_TYPES[kind]).trim() || GOAL_TYPES[kind];
    return { id, kind, target, threshold, name };
  }

  function normalizeGoalPayload(payload) {
    if (!payload || Number(payload.version) !== GOALS_VERSION || !Array.isArray(payload.goals)) return null;
    const goals = payload.goals.map(normalizeGoal).filter(Boolean);
    if (goals.length !== payload.goals.length) return null;
    return { version: GOALS_VERSION, goals };
  }

  function loadGoals(storage) {
    try {
      const raw = storage?.getItem(GOALS_KEY);
      if (!raw) return { version: GOALS_VERSION, goals: [] };
      return normalizeGoalPayload(JSON.parse(raw)) || { version: GOALS_VERSION, goals: [] };
    } catch {
      return { version: GOALS_VERSION, goals: [] };
    }
  }

  function saveGoals(storage, payload) {
    const normalized = normalizeGoalPayload(payload);
    if (!normalized) return false;
    try {
      storage?.setItem(GOALS_KEY, JSON.stringify(normalized));
      return true;
    } catch {
      return false;
    }
  }

  function uniqueSpeciesForms(records, predicate = () => true) {
    return new Set(records.filter(predicate).map(speciesKey));
  }

  function goalProgress(goal, context) {
    const records = context?.records || [];
    const knowledge = context?.knowledge;
    const feeds = context?.feeds || {};
    const normalized = normalizeGoal(goal);
    if (!normalized) return { status: "unsupported", reason: "Invalid goal definition." };
    if (["shiny", "costume"].includes(normalized.kind)) {
      return { status: "unsupported", goal: normalized, achieved: null, target: normalized.target, reason: `${GOAL_TYPES[normalized.kind]} cannot be measured because that status is not represented reliably in the normalized Poke Genie contract.` };
    }

    let achieved = 0;
    let availableTarget = normalized.target;
    if (normalized.kind === "living") {
      achieved = uniqueSpeciesForms(records).size;
      const released = new Set();
      for (const entries of knowledge?.byDex?.values?.() || []) {
        for (const entry of entries) if (entry.released && !entry.transformation?.eligible) released.add(`${entry.dex}:${slug(entry.form_key)}`);
      }
      if (released.size) availableTarget = Math.min(normalized.target, released.size);
    } else if (normalized.kind === "hundo") achieved = uniqueSpeciesForms(records, (record) => Boolean(record.ivs?.is_hundo)).size;
    else if (normalized.kind === "lucky") achieved = uniqueSpeciesForms(records, (record) => Boolean(record.status?.lucky)).size;
    else if (["great", "ultra", "little"].includes(normalized.kind)) {
      achieved = uniqueSpeciesForms(records, (record) => Number(record.pvp?.[normalized.kind]?.rank_percent || 0) >= normalized.threshold).size;
    } else if (normalized.kind === "mega") {
      achieved = new Set((feeds["mega-candidates"]?.candidates || []).map((item) => Number(item.pokemon_number))).size;
    }
    const target = Math.max(1, availableTarget);
    return {
      status: "available",
      goal: normalized,
      achieved,
      target,
      complete: achieved >= target,
      percent: Math.min(100, (achieved / target) * 100),
    };
  }

  function goalHistoryValue(goal, records) {
    const normalized = normalizeGoal(goal);
    if (!normalized) return null;
    if (normalized.kind === "living") return uniqueSpeciesForms(records).size;
    if (normalized.kind === "hundo") return uniqueSpeciesForms(records, (record) => Boolean(record.ivs?.is_hundo)).size;
    if (normalized.kind === "lucky") return uniqueSpeciesForms(records, (record) => Boolean(record.status?.lucky)).size;
    if (["great", "ultra", "little"].includes(normalized.kind)) return uniqueSpeciesForms(records, (record) => Number(record.pvp?.[normalized.kind]?.rank_percent || 0) >= normalized.threshold).size;
    return null;
  }

  function protectionReasons(record) {
    const reasons = [];
    if (record.ivs?.is_hundo) reasons.push("hundo");
    if (record.ivs?.is_nundo) reasons.push("nundo");
    if (record.status?.favorite) reasons.push("favorite");
    if (record.status?.lucky) reasons.push("lucky");
    if (["shadow", "purified"].includes(record.status?.shadow_purified)) reasons.push(record.status.shadow_purified);
    if (record.moves?.charged_second) reasons.push("second_charged_move");
    const highPvp = ["great", "ultra", "little"].some((league) => Number(record.pvp?.[league]?.rank_percent || 0) >= 98);
    if (highPvp) reasons.push("high_pvp_percentile");
    const incomplete = record.ivs?.average_percent == null || record.level?.minimum == null || !record.moves?.fast || !record.moves?.charged;
    if (incomplete) reasons.push("incomplete_scan");
    return reasons;
  }

  function tradeScore(record) {
    const pvp = Math.max(...["great", "ultra", "little"].map((league) => Number(record.pvp?.[league]?.rank_percent || 0)));
    return [protectionReasons(record).length, pvp, Number(record.ivs?.average_percent || 0), Number(record.cp || 0)];
  }

  function compareTradeKeepers(left, right) {
    const a = tradeScore(left);
    const b = tradeScore(right);
    for (let index = 0; index < a.length; index += 1) if (a[index] !== b[index]) return b[index] - a[index];
    return recordId(left).localeCompare(recordId(right));
  }

  function buildTradeReview(records) {
    const groups = new Map();
    for (const record of records || []) {
      const key = `${speciesKey(record)}:${record.status?.shadow_purified || "normal"}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(record);
    }
    const results = [];
    for (const [key, group] of groups.entries()) {
      if (group.length < 2) continue;
      const sorted = [...group].sort(compareTradeKeepers);
      const keeper = sorted[0];
      const candidates = sorted.map((record) => {
        const protectedBy = protectionReasons(record);
        return {
          record_id: recordId(record),
          pokemon_number: record.pokemon_number,
          name: record.name,
          form: record.form,
          cp: record.cp,
          iv_percent: record.ivs?.average_percent,
          protected: protectedBy.length > 0,
          protection_reasons: protectedBy,
          review_state: recordId(record) === recordId(keeper) ? "likely_keeper" : protectedBy.length ? "protected_review" : "trade_review_candidate",
          reasons: recordId(record) === recordId(keeper) ? ["strongest_supported_keep_factors_in_group"] : ["duplicate_species_form_status"],
        };
      });
      results.push({
        key,
        pokemon_number: keeper.pokemon_number,
        name: keeper.name,
        form: keeper.form,
        status: keeper.status?.shadow_purified || "normal",
        count: group.length,
        keeper_record_id: recordId(keeper),
        candidates,
        search_string: keeper.name,
        search_string_warning: "Species-name search can include additional copies or forms. Pokémon GO cannot address these canonical record IDs exactly.",
      });
    }
    results.sort((a, b) => (b.count - a.count) || a.pokemon_number - b.pokemon_number || a.name.localeCompare(b.name));
    return {
      groups: results,
      group_count: results.length,
      unsupported: ["shiny", "costume", "background", "trade history", "catch distance/location when absent from the export"],
      safety: "Every entry is review-only. Duplicate count never makes a Pokémon automatically safe to trade.",
    };
  }

  async function fetchJson(root, path) {
    const response = await root.fetch(path);
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return response.json();
  }

  function teamMemberMarkup(candidate, mode) {
    const pvp = candidate.pvp || {};
    const detail = ["great", "ultra", "little"].includes(mode)
      ? `${Number(pvp.rank_percent || 0).toFixed(2)}% PvP · Rank #${pvp.rank_number ?? "?"} · ${money(pvp.dust_cost)} dust`
      : mode === "raid"
        ? `CP ${money(candidate.cp)} · base attack ${candidate.knowledge?.base_stats?.attack ?? "unknown"}`
        : `CP ${money(candidate.cp)}`;
    return `<li><strong>${escapeHtml(candidate.name)}${candidate.form ? ` · ${escapeHtml(candidate.form)}` : ""}</strong><span>${escapeHtml(detail)}</span><small>${escapeHtml(candidate.record_id)}</small></li>`;
  }

  function renderTeam(result, mode, external) {
    if (result.status !== "available") return `<p class="planner-warning">${escapeHtml(result.reason || "No eligible team could be built.")}</p>`;
    const freshness = external?.overall_freshness || "unavailable";
    const search = [...new Set(result.team.map((item) => item.name))].join(",");
    return `<div class="planner-result-meta"><strong>Current-data freshness: ${escapeHtml(freshness)}</strong><span>Current meta/boss strength was not used.</span></div>
      <ol class="team-list">${result.team.map((item) => teamMemberMarkup(item, mode)).join("")}</ol>
      ${result.warnings.map((warning) => `<p class="planner-warning">${escapeHtml(warning)}</p>`).join("")}
      <p><strong>Pokémon GO helper search:</strong> <code>${escapeHtml(search)}</code></p>
      <p class="planner-note">The helper search selects species names and may include other owned copies. Exact canonical record IDs are not expressible in Pokémon GO search.</p>`;
  }

  function renderOptimization(result) {
    const selected = result.selected.slice(0, 30).map((item) => `<tr><td>${escapeHtml(item.name)}</td><td>${item.rank_percent == null ? "?" : `${item.rank_percent.toFixed(2)}%`}</td><td>${money(item.dust)}</td><td>${money(item.candy)}</td></tr>`).join("");
    return `<div class="planner-result-meta"><strong>${result.selected.length} projects fit the entered budget</strong><span>${money(result.used.stardust)} dust · ${money(result.used.candy)} Candy used</span></div>
      <table class="planner-table"><thead><tr><th>Project</th><th>PvP</th><th>Dust</th><th>Candy</th></tr></thead><tbody>${selected || '<tr><td colspan="4">No known-cost projects fit the budget.</td></tr>'}</tbody></table>
      <p class="planner-note">${escapeHtml(result.warning)} ${result.unknown_cost.length} projects were excluded because a required cost is unknown.</p>`;
  }

  function costMarkup(cost) {
    if (!cost || cost.status === "unavailable") return `<span>Unavailable${cost?.reason ? `: ${escapeHtml(cost.reason)}` : ""}</span>`;
    if (cost.minimum_cost) {
      const min = cost.minimum_cost;
      const max = cost.maximum_cost;
      const format = (item) => `${money(item.dust)} dust · ${money(item.candy)} Candy · ${money(item.xl)} XL`;
      return `<span>${cost.exact ? format(max) : `${format(min)} to ${format(max)}`}</span>`;
    }
    if (Object.hasOwn(cost, "listed_stardust_cost")) return `<span>${cost.listed_stardust_cost == null ? "?" : money(cost.listed_stardust_cost)} dust · ${cost.listed_regular_candy_cost == null ? "? Candy" : `${money(cost.listed_regular_candy_cost)} Candy`}</span>`;
    return `<span>${money(cost.dust)} dust · ${money(cost.candy)} Candy · ${money(cost.xl)} XL</span>`;
  }

  function renderScenario(result) {
    const target = result.target?.status === "known" ? `<p><strong>Result:</strong> ${escapeHtml(result.target_species || result.name)} at level ${result.target.level}, CP ${money(result.target.cp)}</p>`
      : result.resulting_cp != null ? `<p><strong>Result:</strong> level ${result.target_level}, CP ${money(result.resulting_cp)}</p>` : "";
    return `<div class="planner-result-meta"><strong>${escapeHtml(result.action)}</strong><span>${result.irreversible ? "Includes an irreversible step" : "Reversible until resources are spent"}</span></div>
      ${target}<p><strong>Calculated cost:</strong> ${costMarkup(result.cost)}</p>
      ${result.poke_genie_build_cost ? `<p><strong>Poke Genie exported build cost:</strong> ${result.poke_genie_build_cost.stardust_cost == null ? "?" : money(result.poke_genie_build_cost.stardust_cost)} dust · ${result.poke_genie_build_cost.regular_candy_cost == null ? "?" : money(result.poke_genie_build_cost.regular_candy_cost)} Candy</p>` : ""}
      ${result.warnings.map((warning) => `<p class="planner-warning">${escapeHtml(warning)}</p>`).join("")}
      <p class="planner-note">Power-up model ${POWER_UP_MODEL_VERSION}. Source classification: ${escapeHtml(POWER_UP_SOURCE.classification)}. Missing inputs remain unknown.</p>`;
  }

  function installTeamUi(root, resources) {
    const documentObject = root.document;
    const mode = documentObject.getElementById("team-mode");
    const locks = documentObject.getElementById("team-locks");
    const output = documentObject.getElementById("team-results");
    const status = documentObject.getElementById("team-status");
    const button = documentObject.getElementById("build-team");
    if (!mode || !locks || !output || !button) return;
    const feedCache = new Map();

    const loadFeed = async () => {
      const config = TEAM_FEEDS[mode.value];
      if (!config) return null;
      if (feedCache.has(config.feed)) return feedCache.get(config.feed);
      const meta = resources.candidateIndex.feeds.find((item) => item.name === config.feed);
      if (!meta || meta.status !== "available") return { status: "unavailable", unavailable_reason: meta?.unavailable_reason || "Candidate feed is unavailable.", candidates: [] };
      const payload = await fetchJson(root, meta.path);
      feedCache.set(config.feed, payload);
      resources.feeds[config.feed] = payload;
      return payload;
    };

    const populateLocks = async () => {
      status.textContent = "Loading owned candidates…";
      const feed = await loadFeed();
      locks.innerHTML = "";
      for (const candidate of feed?.candidates || []) {
        const option = documentObject.createElement("option");
        option.value = candidate.record_id;
        option.textContent = `${candidate.name}${candidate.form ? ` · ${candidate.form}` : ""} · CP ${candidate.cp ?? "?"}`;
        locks.append(option);
      }
      status.textContent = feed?.status === "unavailable" ? feed.unavailable_reason : `${(feed?.candidates || []).length.toLocaleString()} owned candidates available. Select up to two locks if desired.`;
    };

    mode.addEventListener("change", populateLocks);
    button.addEventListener("click", async () => {
      const feed = await loadFeed();
      if (!feed || feed.status === "unavailable") {
        output.innerHTML = `<p class="planner-warning">${escapeHtml(feed?.unavailable_reason || "Candidate feed unavailable.")}</p>`;
        return;
      }
      const selected = [...locks.selectedOptions].map((option) => option.value).slice(0, 2);
      output.innerHTML = renderTeam(buildOwnedTeam(feed.candidates || [], mode.value, selected), mode.value, resources.external);
    });
    populateLocks();
  }

  function installOptimizerUi(root, resources) {
    const documentObject = root.document;
    const league = documentObject.getElementById("optimizer-league");
    const dust = documentObject.getElementById("budget-dust");
    const candy = documentObject.getElementById("budget-candy");
    const objective = documentObject.getElementById("optimizer-objective");
    const run = documentObject.getElementById("run-optimizer");
    const output = documentObject.getElementById("optimizer-results");
    const recordSelect = documentObject.getElementById("scenario-record");
    const scenarioSelect = documentObject.getElementById("scenario-type");
    const simulate = documentObject.getElementById("run-scenario");
    const scenarioOutput = documentObject.getElementById("scenario-results");
    if (!run || !output || !recordSelect || !simulate || !scenarioOutput) return;

    try {
      const saved = JSON.parse(root.localStorage?.getItem(BUDGET_KEY) || "null");
      if (saved) {
        if (saved.dust != null) dust.value = saved.dust;
        if (saved.candy != null) candy.value = saved.candy;
      }
    } catch { /* Ignore malformed browser-local budget state. */ }

    const records = [...resources.records].sort((a, b) => a.name.localeCompare(b.name) || Number(b.cp || 0) - Number(a.cp || 0));
    for (const record of records) {
      const option = documentObject.createElement("option");
      option.value = recordId(record);
      option.textContent = `${record.name}${record.form ? ` · ${record.form}` : ""} · CP ${record.cp ?? "?"}`;
      recordSelect.append(option);
    }

    run.addEventListener("click", () => {
      root.localStorage?.setItem(BUDGET_KEY, JSON.stringify({ dust: Number(dust.value) || 0, candy: Number(candy.value) || 0 }));
      const result = optimizeBudget(resources.investments, {
        league: league.value,
        dustBudget: dust.value,
        candyBudget: candy.value,
        objective: objective.value,
      });
      output.innerHTML = renderOptimization(result);
    });

    simulate.addEventListener("click", () => {
      const record = resources.recordById.get(recordSelect.value);
      const investment = resources.investmentById.get(recordSelect.value);
      if (!record || !investment) {
        scenarioOutput.innerHTML = '<p class="planner-warning">Select an owned record with investment data.</p>';
        return;
      }
      scenarioOutput.innerHTML = renderScenario(scenarioForRecord(record, investment, resources.knowledge, scenarioSelect.value));
    });
  }

  async function loadPreviousSnapshot(root, resources) {
    const snapshots = resources.history?.snapshots || [];
    if (snapshots.length < 2) return null;
    try {
      return await fetchJson(root, snapshots[snapshots.length - 2].path);
    } catch {
      return null;
    }
  }

  function installGoalsUi(root, resources) {
    const documentObject = root.document;
    const kind = documentObject.getElementById("goal-kind");
    const target = documentObject.getElementById("goal-target");
    const threshold = documentObject.getElementById("goal-threshold");
    const add = documentObject.getElementById("add-goal");
    const list = documentObject.getElementById("goal-list");
    const exportButton = documentObject.getElementById("export-goals");
    const importInput = documentObject.getElementById("import-goals");
    const clear = documentObject.getElementById("clear-goals");
    if (!kind || !target || !add || !list) return;
    let payload = loadGoals(root.localStorage);
    let previousSnapshot = null;
    loadPreviousSnapshot(root, resources).then((value) => { previousSnapshot = value; render(); });

    function render() {
      if (!payload.goals.length) {
        list.innerHTML = '<p class="planner-note">No local goals yet. Add one above.</p>';
        return;
      }
      list.innerHTML = payload.goals.map((goal) => {
        const progress = goalProgress(goal, resources);
        if (progress.status === "unsupported") {
          return `<article class="goal-card"><header><strong>${escapeHtml(goal.name)}</strong><button type="button" data-remove-goal="${escapeHtml(goal.id)}">Remove</button></header><p class="planner-warning">${escapeHtml(progress.reason)}</p></article>`;
        }
        const previous = previousSnapshot ? goalHistoryValue(goal, previousSnapshot.records || []) : null;
        const delta = previous === null ? "" : `<small>Previous retained snapshot: ${previous.toLocaleString()} (${progress.achieved - previous >= 0 ? "+" : ""}${(progress.achieved - previous).toLocaleString()})</small>`;
        return `<article class="goal-card"><header><strong>${escapeHtml(goal.name)}</strong><button type="button" data-remove-goal="${escapeHtml(goal.id)}">Remove</button></header><div class="goal-progress" role="progressbar" aria-valuemin="0" aria-valuemax="${progress.target}" aria-valuenow="${progress.achieved}"><span style="width:${progress.percent.toFixed(2)}%"></span></div><p>${progress.achieved.toLocaleString()} / ${progress.target.toLocaleString()} · ${progress.percent.toFixed(1)}%</p>${delta}</article>`;
      }).join("");
    }

    add.addEventListener("click", () => {
      const goal = normalizeGoal({ kind: kind.value, target: target.value, threshold: threshold.value });
      if (!goal) return;
      payload.goals.push(goal);
      saveGoals(root.localStorage, payload);
      render();
    });
    list.addEventListener("click", (event) => {
      const button = event.target.closest?.("[data-remove-goal]");
      if (!button) return;
      payload.goals = payload.goals.filter((goal) => goal.id !== button.dataset.removeGoal);
      saveGoals(root.localStorage, payload);
      render();
    });
    exportButton?.addEventListener("click", () => {
      const blob = new root.Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
      const anchor = documentObject.createElement("a");
      anchor.href = root.URL.createObjectURL(blob);
      anchor.download = "pokemon-go-collection-goals.json";
      anchor.click();
      root.URL.revokeObjectURL(anchor.href);
    });
    importInput?.addEventListener("change", async () => {
      const file = importInput.files?.[0];
      if (!file) return;
      try {
        const parsed = normalizeGoalPayload(JSON.parse(await file.text()));
        if (!parsed) throw new Error("Invalid goals backup");
        payload = parsed;
        saveGoals(root.localStorage, payload);
        render();
      } catch {
        root.alert?.("That goals backup is invalid or from an unsupported schema version.");
      } finally {
        importInput.value = "";
      }
    });
    clear?.addEventListener("click", () => {
      payload = { version: GOALS_VERSION, goals: [] };
      saveGoals(root.localStorage, payload);
      render();
    });
    render();
  }

  function installTradeUi(root, resources) {
    const output = root.document.getElementById("trade-results");
    const filter = root.document.getElementById("trade-filter");
    if (!output) return;
    const review = buildTradeReview(resources.records);
    const render = () => {
      const mode = filter?.value || "all";
      const groups = review.groups.filter((group) => mode === "all" || group.candidates.some((candidate) => candidate.review_state === mode));
      output.innerHTML = `<p class="planner-note">${escapeHtml(review.safety)} Unsupported or unreliable trade-value facts: ${escapeHtml(review.unsupported.join(", "))}.</p>${groups.slice(0, 80).map((group) => {
        const candidates = group.candidates.map((candidate) => `<li data-state="${escapeHtml(candidate.review_state)}"><strong>${escapeHtml(candidate.name)} · CP ${money(candidate.cp)}</strong><span>${escapeHtml(candidate.review_state.replaceAll("_", " "))}</span><small>${candidate.protection_reasons.length ? `Protected: ${escapeHtml(candidate.protection_reasons.join(", "))}` : "No supported protection flag triggered"} · ${escapeHtml(candidate.record_id)}</small></li>`).join("");
        return `<details class="trade-group"><summary><strong>#${group.pokemon_number} ${escapeHtml(group.name)}${group.form ? ` · ${escapeHtml(group.form)}` : ""}</strong><span>${group.count} copies · ${escapeHtml(group.status)}</span></summary><ul>${candidates}</ul><p>Pokémon GO helper search: <code>${escapeHtml(group.search_string)}</code></p><p class="planner-note">${escapeHtml(group.search_string_warning)}</p></details>`;
      }).join("")}`;
    };
    filter?.addEventListener("change", render);
    render();
  }

  async function loadResources(root) {
    const [pokemon, investments, candidateIndex, knowledgePayload, external, history] = await Promise.all([
      fetchJson(root, "data/pokemon.json"),
      fetchJson(root, "data/investments/records.json"),
      fetchJson(root, "data/candidates/index.json"),
      fetchJson(root, "data/knowledge/pokemon-go.json"),
      fetchJson(root, "data/external/index.json").catch(() => ({ overall_freshness: "unavailable" })),
      fetchJson(root, "data/history-index.json").catch(() => ({ snapshots: [] })),
    ]);
    const records = pokemon.records || [];
    const investmentRecords = investments.records || [];
    return {
      records,
      investments: investmentRecords,
      recordById: new Map(records.map((record) => [recordId(record), record])),
      investmentById: new Map(investmentRecords.map((item) => [String(item.record_id), item])),
      candidateIndex,
      feeds: {},
      knowledge: buildKnowledgeIndex(knowledgePayload),
      external,
      history,
    };
  }

  function renderLoadError(documentObject, error) {
    const status = documentObject.getElementById("planner-load-status");
    if (status) status.innerHTML = `<strong>Planning tools could not load.</strong> ${escapeHtml(error instanceof Error ? error.message : String(error))}`;
  }

  async function install(root) {
    if (!root.document.getElementById("planning-app")) return null;
    const status = root.document.getElementById("planner-load-status");
    try {
      const resources = await loadResources(root);
      if (status) status.textContent = `Loaded ${resources.records.length.toLocaleString()} canonical owned records. Current-game freshness: ${resources.external?.overall_freshness || "unavailable"}.`;
      installTeamUi(root, resources);
      installOptimizerUi(root, resources);
      installGoalsUi(root, resources);
      installTradeUi(root, resources);
      if ("serviceWorker" in root.navigator) root.navigator.serviceWorker.register("sw.js").catch(() => {});
      return resources;
    } catch (error) {
      renderLoadError(root.document, error);
      return null;
    }
  }

  return {
    GOALS_KEY,
    GOALS_VERSION,
    POWER_UP_MODEL_VERSION,
    POWER_UP_SOURCE,
    TEAM_FEEDS,
    GOAL_TYPES,
    basePowerUpStep,
    costMultipliers,
    powerUpCost,
    powerUpCostRange,
    cpAtLevel,
    buildKnowledgeIndex,
    knowledgeForRecord,
    knowledgeForName,
    findLeagueTarget,
    scenarioForRecord,
    buildOwnedTeam,
    optimizeBudget,
    normalizeGoal,
    normalizeGoalPayload,
    loadGoals,
    saveGoals,
    goalProgress,
    goalHistoryValue,
    protectionReasons,
    buildTradeReview,
    install,
  };
});
