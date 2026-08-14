"use strict";

(function exposePlanningExtras(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionPlanningExtras = api;
  if (root?.document) {
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", () => api.install(root), { once: true });
    else api.install(root);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const GOAL_EXCLUSIONS_KEY = "pokemon-go-collection:goal-exclusions:v1";
  const EXCLUSION_VERSION = 1;
  const normalize = (value) => String(value ?? "").trim().toLocaleLowerCase();
  const slug = (value) => normalize(value).replace(/[’']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "normal";
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
  const recordId = (record) => String(record?.identity?.record_id || record?.record_id || "");
  const speciesKey = (record) => `${Number(record?.pokemon_number || 0)}:${slug(record?.form)}`;
  const money = (value) => Number(value || 0).toLocaleString();

  async function fetchJson(root, path) {
    const response = await root.fetch(path);
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return response.json();
  }

  function normalizeExclusions(value) {
    return [...new Set(String(value || "").split(",").map((item) => normalize(item)).filter(Boolean))];
  }

  function exclusionPayload(raw) {
    if (!raw || Number(raw.version) !== EXCLUSION_VERSION || typeof raw.by_goal !== "object" || Array.isArray(raw.by_goal)) {
      return { version: EXCLUSION_VERSION, by_goal: {} };
    }
    const byGoal = {};
    for (const [goalId, values] of Object.entries(raw.by_goal)) byGoal[String(goalId)] = normalizeExclusions(Array.isArray(values) ? values.join(",") : values);
    return { version: EXCLUSION_VERSION, by_goal: byGoal };
  }

  function loadExclusions(storage) {
    try {
      const raw = storage?.getItem(GOAL_EXCLUSIONS_KEY);
      return raw ? exclusionPayload(JSON.parse(raw)) : { version: EXCLUSION_VERSION, by_goal: {} };
    } catch {
      return { version: EXCLUSION_VERSION, by_goal: {} };
    }
  }

  function saveExclusions(storage, payload) {
    const normalized = exclusionPayload(payload);
    try {
      storage?.setItem(GOAL_EXCLUSIONS_KEY, JSON.stringify(normalized));
      return true;
    } catch {
      return false;
    }
  }

  function isExcluded(species, exclusions) {
    const dex = String(species?.dex ?? species?.pokemon_number ?? "");
    const name = normalize(species?.name ?? species?.display_name ?? "");
    const form = slug(species?.form ?? species?.form_key ?? "normal");
    const keys = new Set([dex, name, slug(name), `${dex}:${form}`, `${slug(name)}:${form}`]);
    return exclusions.some((item) => keys.has(normalize(item)) || keys.has(slug(item)));
  }

  function releasedSpecies(knowledge) {
    const items = new Map();
    for (const entries of knowledge?.byDex?.values?.() || []) {
      for (const entry of entries) {
        if (!entry.released || entry.transformation?.eligible) continue;
        const item = { dex: entry.dex, name: entry.base_name || entry.display_name, form: entry.form_key || "normal", display_name: entry.display_name };
        items.set(`${entry.dex}:${slug(entry.form_key)}`, item);
      }
    }
    return [...items.values()];
  }

  function goalDetail(goal, resources, exclusions = []) {
    const records = resources.records || [];
    const Planning = resources.Planning;
    if (["shiny", "costume"].includes(goal.kind)) {
      return { status: "unsupported", reason: `${goal.kind} is not a reliable normalized source field.` };
    }
    const allowedRecords = records.filter((record) => !isExcluded(record, exclusions));
    let qualifying = [];
    if (goal.kind === "living") qualifying = allowedRecords;
    else if (goal.kind === "hundo") qualifying = allowedRecords.filter((record) => record.ivs?.is_hundo);
    else if (goal.kind === "lucky") qualifying = allowedRecords.filter((record) => record.status?.lucky);
    else if (["great", "ultra", "little"].includes(goal.kind)) qualifying = allowedRecords.filter((record) => Number(record.pvp?.[goal.kind]?.rank_percent || 0) >= Number(goal.threshold || 98));
    else if (goal.kind === "mega") {
      const ids = new Set((resources.mega?.candidates || []).map((item) => String(item.record_id)));
      qualifying = allowedRecords.filter((record) => ids.has(recordId(record)));
    }

    const qualifyingKeys = new Set(qualifying.map(speciesKey));
    const owned = [];
    for (const record of qualifying) {
      if (owned.some((item) => item.key === speciesKey(record))) continue;
      owned.push({ key: speciesKey(record), record_id: recordId(record), dex: record.pokemon_number, name: record.name, form: record.form });
    }

    const universe = releasedSpecies(resources.knowledge).filter((item) => !isExcluded(item, exclusions));
    const exactMissingSupported = ["living", "hundo", "lucky"].includes(goal.kind);
    const missing = exactMissingSupported
      ? universe.filter((item) => !qualifyingKeys.has(`${Number(item.dex)}:${slug(item.form)}`))
      : [];
    const ambiguous = allowedRecords.filter((record) => !Planning.knowledgeForRecord(record, resources.knowledge)).map((record) => ({
      record_id: recordId(record), dex: record.pokemon_number, name: record.name, form: record.form,
    }));
    const achieved = owned.length;
    const target = Math.max(1, Number(goal.target) || 1);
    return {
      status: "available",
      achieved,
      target,
      owned,
      missing,
      ambiguous,
      exclusions,
      exact_missing_supported: exactMissingSupported,
      unresolved_count: Math.max(0, target - achieved),
    };
  }

  function goalSearchHref(goal) {
    if (goal.kind === "hundo") return "index.html?hundo=yes";
    if (goal.kind === "lucky") return "index.html?lucky=yes";
    if (["great", "ultra", "little"].includes(goal.kind)) return `index.html?league=${encodeURIComponent(goal.kind)}&pvpMin=${encodeURIComponent(goal.threshold || 98)}`;
    return "index.html";
  }

  function detailList(items, kind, limit = 80) {
    const shown = items.slice(0, limit);
    const rows = shown.map((item) => {
      const form = item.form && slug(item.form) !== "normal" ? ` · ${escapeHtml(item.form)}` : "";
      const record = item.record_id ? `<small>${escapeHtml(item.record_id)}</small>` : "";
      return `<li><span>#${escapeHtml(item.dex)} ${escapeHtml(item.name || item.display_name)}${form}</span>${record}</li>`;
    }).join("");
    const more = items.length > shown.length ? `<li>…and ${(items.length - shown.length).toLocaleString()} more ${escapeHtml(kind)}</li>` : "";
    return rows + more;
  }

  function renderGoalDetails(root, resources) {
    const list = root.document.getElementById("goal-list");
    if (!list) return;
    const goals = resources.Planning.loadGoals(root.localStorage).goals;
    const exclusions = loadExclusions(root.localStorage);
    const cards = [...list.querySelectorAll(".goal-card")];
    for (let index = 0; index < goals.length; index += 1) {
      const goal = goals[index];
      const card = cards[index];
      if (!card) continue;
      card.querySelector("[data-goal-detail]")?.remove();
      const detail = goalDetail(goal, resources, exclusions.by_goal[goal.id] || []);
      const wrapper = root.document.createElement("div");
      wrapper.dataset.goalDetail = "true";
      if (detail.status === "unsupported") {
        wrapper.innerHTML = `<p class="planner-warning">State: unsupported. ${escapeHtml(detail.reason)}</p>`;
      } else {
        const progressParagraph = card.querySelector(".goal-progress + p");
        if (progressParagraph) progressParagraph.textContent = `${detail.achieved.toLocaleString()} / ${detail.target.toLocaleString()} after exclusions · ${Math.min(100, detail.achieved / detail.target * 100).toFixed(1)}%`;
        const missingSummary = detail.exact_missing_supported
          ? `${detail.missing.length.toLocaleString()} exact released species/forms missing for this predicate`
          : `${detail.unresolved_count.toLocaleString()} target slots remain; exact missing species are ambiguous for this predicate`;
        wrapper.innerHTML = `<p class="planner-note"><strong>States:</strong> ${detail.owned.length.toLocaleString()} owned · ${missingSummary} · ${detail.ambiguous.length.toLocaleString()} records with ambiguous knowledge joins · ${detail.exclusions.length.toLocaleString()} exclusions.</p>
          <p><a href="${escapeHtml(goalSearchHref(goal))}">Open matching owned records in Collection</a></p>
          <details><summary>Owned drill-down (${detail.owned.length.toLocaleString()})</summary><ul class="goal-detail-list">${detailList(detail.owned, "owned records") || "<li>None</li>"}</ul></details>
          ${detail.exact_missing_supported ? `<details><summary>Missing drill-down (${detail.missing.length.toLocaleString()})</summary><ul class="goal-detail-list">${detailList(detail.missing, "missing species/forms") || "<li>None</li>"}</ul></details>` : ""}
          ${detail.ambiguous.length ? `<details><summary>Ambiguous joins (${detail.ambiguous.length.toLocaleString()})</summary><ul class="goal-detail-list">${detailList(detail.ambiguous, "ambiguous records", 40)}</ul></details>` : ""}
          ${detail.exclusions.length ? `<p class="planner-note">Excluded from this goal: ${escapeHtml(detail.exclusions.join(", "))}</p>` : ""}`;
      }
      card.append(wrapper);
    }
  }

  function installGoalExclusions(root, resources) {
    const kind = root.document.getElementById("goal-kind");
    const add = root.document.getElementById("add-goal");
    const list = root.document.getElementById("goal-list");
    if (!kind || !add || !list || root.document.getElementById("goal-exclusions")) return;
    const label = root.document.createElement("label");
    label.innerHTML = 'Exclusions <input id="goal-exclusions" type="text" placeholder="e.g. 201, unown:question"><small>Comma-separated dex numbers, species names, or dex:name/form keys. Stored per goal.</small>';
    add.insertAdjacentElement("beforebegin", label);
    const input = label.querySelector("input");

    add.addEventListener("click", () => {
      root.setTimeout(() => {
        const values = normalizeExclusions(input.value);
        const goals = resources.Planning.loadGoals(root.localStorage).goals;
        const goal = goals[goals.length - 1];
        if (goal && values.length) {
          const payload = loadExclusions(root.localStorage);
          payload.by_goal[goal.id] = values;
          saveExclusions(root.localStorage, payload);
        }
        input.value = "";
        renderGoalDetails(root, resources);
      }, 0);
    });

    list.addEventListener("click", () => root.setTimeout(() => {
      const goals = resources.Planning.loadGoals(root.localStorage).goals;
      const active = new Set(goals.map((goal) => goal.id));
      const payload = loadExclusions(root.localStorage);
      for (const goalId of Object.keys(payload.by_goal)) if (!active.has(goalId)) delete payload.by_goal[goalId];
      saveExclusions(root.localStorage, payload);
      renderGoalDetails(root, resources);
    }, 0));

    const observer = new root.MutationObserver(() => {
      root.setTimeout(() => renderGoalDetails(root, resources), 0);
    });
    observer.observe(list, { childList: true });
    renderGoalDetails(root, resources);
  }

  function teamExtraWarnings(team) {
    const warnings = [];
    for (const candidate of team || []) {
      if (!candidate.moves?.charged_second) warnings.push(`${candidate.name} has no second Charged Move recorded in the current scan.`);
      if (!candidate.moves?.fast || !candidate.moves?.charged) warnings.push(`${candidate.name} has incomplete recorded moves and should be rescanned before team investment.`);
    }
    warnings.push("Legacy/exclusive/recommended move requirements are not asserted without freshness-checked current move guidance.");
    return [...new Set(warnings)];
  }

  function candidateCost(candidate, mode) {
    if (!["great", "ultra", "little"].includes(mode)) return "Build cost depends on the selected PvE target and is not inferred here.";
    const dust = candidate.pvp?.dust_cost;
    const candy = candidate.pvp?.candy_cost;
    return `${dust == null ? "?" : money(dust)} dust · ${candy == null ? "?" : money(candy)} Candy`;
  }

  async function installTeamEnhancements(root, resources) {
    const button = root.document.getElementById("build-team");
    const output = root.document.getElementById("team-results");
    const mode = root.document.getElementById("team-mode");
    const locks = root.document.getElementById("team-locks");
    if (!button || !output || !mode || !locks) return;
    const feedCache = new Map();
    const feedForMode = async () => {
      const config = resources.Planning.TEAM_FEEDS[mode.value];
      if (!config) return null;
      if (feedCache.has(config.feed)) return feedCache.get(config.feed);
      const meta = resources.candidateIndex.feeds.find((item) => item.name === config.feed);
      if (!meta || meta.status !== "available") return null;
      const payload = await fetchJson(root, meta.path);
      feedCache.set(config.feed, payload);
      return payload;
    };

    button.addEventListener("click", async () => {
      const feed = await feedForMode();
      if (!feed) return;
      root.setTimeout(() => {
        const selected = [...locks.selectedOptions].map((option) => option.value).slice(0, 2);
        const result = resources.Planning.buildOwnedTeam(feed.candidates || [], mode.value, selected);
        output.querySelector("[data-team-extras]")?.remove();
        const extra = root.document.createElement("section");
        extra.dataset.teamExtras = "true";
        const warnings = teamExtraWarnings(result.team).map((warning) => `<li>${escapeHtml(warning)}</li>`).join("");
        const alternatives = result.alternatives.slice(0, 6).map((candidate) => `<li><strong>${escapeHtml(candidate.name)}${candidate.form ? ` · ${escapeHtml(candidate.form)}` : ""}</strong><span>CP ${money(candidate.cp)} · ${escapeHtml(candidateCost(candidate, mode.value))}</span><small>${escapeHtml(candidate.record_id)}</small></li>`).join("");
        extra.innerHTML = `<details open><summary>Build warnings</summary><ul>${warnings}</ul></details>
          <details><summary>Alternatives (${Math.min(6, result.alternatives.length).toLocaleString()} shown)</summary><ul class="team-list">${alternatives || "<li>No additional owned candidates in this feed.</li>"}</ul></details>`;
        output.append(extra);
      }, 0);
    });
  }

  function renderExcluded(result) {
    const excluded = result.excluded.slice(0, 30).map((item) => `<tr><td>${escapeHtml(item.name)}</td><td>${item.rank_percent == null ? "?" : `${item.rank_percent.toFixed(2)}%`}</td><td>${money(item.dust)}</td><td>${money(item.candy)}</td><td>${escapeHtml(item.exclusion_reason)}</td></tr>`).join("");
    const unknown = result.unknown_cost.slice(0, 30).map((item) => `<li>${escapeHtml(item.name)} · ${item.dust == null ? "Stardust unknown" : ""}${item.dust == null && item.candy == null ? " + " : ""}${item.candy == null ? "Candy unknown" : ""}</li>`).join("");
    return `<details data-optimizer-exclusions><summary>Why projects were excluded</summary>
      <table class="planner-table"><thead><tr><th>Project</th><th>PvP</th><th>Dust</th><th>Candy</th><th>Reason</th></tr></thead><tbody>${excluded || '<tr><td colspan="5">No known-cost project exceeded the entered budget.</td></tr>'}</tbody></table>
      <h4>Unknown-cost projects</h4><ul>${unknown || "<li>None</li>"}</ul></details>`;
  }

  function formatCostRange(cost) {
    if (!cost || cost.status !== "known") return escapeHtml(cost?.reason || "unavailable");
    const item = cost.maximum_cost || cost;
    return `${money(item.dust)} dust · ${money(item.candy)} Candy · ${money(item.xl)} XL`;
  }

  function installOptimizerEnhancements(root, resources) {
    const run = root.document.getElementById("run-optimizer");
    const optimizerOutput = root.document.getElementById("optimizer-results");
    const league = root.document.getElementById("optimizer-league");
    const dust = root.document.getElementById("budget-dust");
    const candy = root.document.getElementById("budget-candy");
    const objective = root.document.getElementById("optimizer-objective");
    const simulate = root.document.getElementById("run-scenario");
    const scenarioOutput = root.document.getElementById("scenario-results");
    const recordSelect = root.document.getElementById("scenario-record");
    const scenarioSelect = root.document.getElementById("scenario-type");
    if (!run || !optimizerOutput || !simulate || !scenarioOutput || !recordSelect || !scenarioSelect) return;

    run.addEventListener("click", () => root.setTimeout(() => {
      const result = resources.Planning.optimizeBudget(resources.investments, {
        league: league.value,
        dustBudget: dust.value,
        candyBudget: candy.value,
        objective: objective.value,
      });
      optimizerOutput.querySelector("[data-optimizer-exclusions]")?.remove();
      optimizerOutput.insertAdjacentHTML("beforeend", renderExcluded(result));
    }, 0));

    if (![...scenarioSelect.options].some((option) => option.value === "shadow-purified")) {
      const comparison = root.document.createElement("option");
      comparison.value = "shadow-purified";
      comparison.textContent = "Compare Shadow vs Purified power-up cost to level 50";
      scenarioSelect.append(comparison);
      const moves = root.document.createElement("option");
      moves.value = "move-review";
      moves.textContent = "Review versioned move-pool acquisition limits";
      scenarioSelect.append(moves);
    }

    let history = root.document.getElementById("scenario-comparisons");
    if (!history) {
      history = root.document.createElement("section");
      history.id = "scenario-comparisons";
      history.innerHTML = '<header><h4>Scenario comparison</h4><button id="clear-scenario-comparisons" type="button">Clear comparison</button></header><div class="scenario-comparison-grid"></div>';
      scenarioOutput.insertAdjacentElement("afterend", history);
      history.querySelector("#clear-scenario-comparisons").addEventListener("click", () => { history.querySelector(".scenario-comparison-grid").innerHTML = ""; });
    }

    simulate.addEventListener("click", () => root.setTimeout(() => {
      const record = resources.recordById.get(recordSelect.value);
      if (!record) return;
      const selectedScenario = scenarioSelect.value;
      if (selectedScenario === "shadow-purified") {
        const shadow = resources.Planning.powerUpCostRange(record.level, 50, { ...record.status, lucky: false, shadow_purified: "shadow" });
        const purified = resources.Planning.powerUpCostRange(record.level, 50, { ...record.status, lucky: false, shadow_purified: "purified" });
        scenarioOutput.innerHTML = `<div class="planner-result-meta"><strong>Hypothetical Shadow vs Purified cost</strong><span>No purification recommendation is made.</span></div>
          <p><strong>Shadow to level 50:</strong> ${formatCostRange(shadow)}</p>
          <p><strong>Purified to level 50:</strong> ${formatCostRange(purified)}</p>
          <p class="planner-warning">Purification is irreversible and also changes battle behavior/IVs. This comparison isolates the versioned power-up cost modifier and does not recommend purification.</p>`;
      } else if (selectedScenario === "move-review") {
        const entry = resources.Planning.knowledgeForRecord(record, resources.knowledge);
        scenarioOutput.innerHTML = `<div class="planner-result-meta"><strong>Versioned move-pool review</strong><span>${escapeHtml(resources.knowledge.classification || "Unknown classification")}</span></div>
          <p><strong>Fast:</strong> ${escapeHtml((entry?.moves?.fast || []).join(", ") || "unknown")}</p>
          <p><strong>Charged:</strong> ${escapeHtml((entry?.moves?.charged || []).join(", ") || "unknown")}</p>
          <p><strong>Elite/exclusive in pinned snapshot:</strong> ${escapeHtml((entry?.moves?.elite_or_exclusive || []).join(", ") || "none recorded")}</p>
          <p class="planner-warning">The pinned species snapshot does not prove current TM, event, or Elite-TM acquisition availability. No move change is automatically selected.</p>`;
      }
      const grid = history.querySelector(".scenario-comparison-grid");
      const card = root.document.createElement("article");
      card.className = "scenario-comparison-card";
      card.innerHTML = `<header><strong>${escapeHtml(record.name)}${record.form ? ` · ${escapeHtml(record.form)}` : ""}</strong><small>${escapeHtml(selectedScenario)} · ${escapeHtml(recordId(record))}</small></header>${scenarioOutput.innerHTML}`;
      grid.append(card);
    }, 0));
  }

  async function loadResources(root) {
    const Planning = root.CollectionPlanning;
    const [pokemon, investments, candidateIndex, knowledgePayload] = await Promise.all([
      fetchJson(root, "data/pokemon.json"),
      fetchJson(root, "data/investments/records.json"),
      fetchJson(root, "data/candidates/index.json"),
      fetchJson(root, "data/knowledge/pokemon-go.json"),
    ]);
    const records = pokemon.records || [];
    const investmentRecords = investments.records || [];
    const knowledge = Planning.buildKnowledgeIndex(knowledgePayload);
    const megaMeta = candidateIndex.feeds.find((item) => item.name === "mega-candidates" && item.status === "available");
    const mega = megaMeta ? await fetchJson(root, megaMeta.path) : { candidates: [] };
    return {
      Planning,
      records,
      investments: investmentRecords,
      candidateIndex,
      knowledge,
      mega,
      recordById: new Map(records.map((record) => [recordId(record), record])),
    };
  }

  function waitForBasePlanning(root) {
    return new Promise((resolve, reject) => {
      const status = root.document.getElementById("planner-load-status");
      if (!status) return reject(new Error("Planning status element is missing"));
      const ready = () => /canonical owned records/i.test(status.textContent || "");
      if (ready()) return resolve();
      const observer = new root.MutationObserver(() => {
        if (ready()) {
          observer.disconnect();
          resolve();
        } else if (/could not load/i.test(status.textContent || "")) {
          observer.disconnect();
          reject(new Error(status.textContent));
        }
      });
      observer.observe(status, { childList: true, characterData: true, subtree: true });
    });
  }

  async function install(root) {
    if (!root.document.getElementById("planning-app") || !root.CollectionPlanning) return null;
    try {
      await waitForBasePlanning(root);
      const resources = await loadResources(root);
      installTeamEnhancements(root, resources);
      installOptimizerEnhancements(root, resources);
      installGoalExclusions(root, resources);
      return resources;
    } catch (error) {
      const status = root.document.getElementById("planner-load-status");
      if (status) status.insertAdjacentHTML("afterend", `<p class="planner-warning">Optional planning details could not load: ${escapeHtml(error instanceof Error ? error.message : String(error))}</p>`);
      return null;
    }
  }

  return {
    GOAL_EXCLUSIONS_KEY,
    EXCLUSION_VERSION,
    normalizeExclusions,
    exclusionPayload,
    loadExclusions,
    saveExclusions,
    isExcluded,
    goalDetail,
    teamExtraWarnings,
    install,
  };
});
