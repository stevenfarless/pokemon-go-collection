"use strict";

(function exposeBattleLabs(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionBattleLabs = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const VERSION = "1.0.0";
  const LEAGUES = new Set(["great", "ultra", "little", "master"]);

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function asNumber(value) {
    if (value === null || value === undefined || value === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function recordId(candidate) {
    return String(candidate?.record_id || candidate?.identity?.record_id || "");
  }

  function pvpValue(candidate) {
    const pvp = candidate?.pvp || {};
    return {
      rankPercent: asNumber(pvp.rank_percent),
      rankNumber: asNumber(pvp.rank_number),
      statProduct: asNumber(pvp.stat_product),
      dust: asNumber(pvp.dust_cost),
      candy: asNumber(pvp.candy_cost),
      attackStat: asNumber(pvp.attack_stat),
      evolutionName: pvp.evolution_name || null,
      evolutionForm: pvp.evolution_form || null,
    };
  }

  function comparePvpCandidates(left, right) {
    const a = pvpValue(left);
    const b = pvpValue(right);
    return ((b.rankPercent ?? -1) - (a.rankPercent ?? -1))
      || ((a.rankNumber ?? Number.MAX_SAFE_INTEGER) - (b.rankNumber ?? Number.MAX_SAFE_INTEGER))
      || ((b.statProduct ?? -1) - (a.statProduct ?? -1))
      || ((a.dust ?? Number.MAX_SAFE_INTEGER) - (b.dust ?? Number.MAX_SAFE_INTEGER))
      || ((a.candy ?? Number.MAX_SAFE_INTEGER) - (b.candy ?? Number.MAX_SAFE_INTEGER))
      || ((Number(right?.cp) || 0) - (Number(left?.cp) || 0))
      || recordId(left).localeCompare(recordId(right));
  }

  function cmpComparison(left, right) {
    const leftAttack = pvpValue(left).attackStat;
    const rightAttack = pvpValue(right).attackStat;
    if (leftAttack === null || rightAttack === null) {
      return {
        state: "unavailable",
        winner_record_id: null,
        reason: "Comparable battle Attack is not present. Attack IV alone is not a CMP calculation.",
      };
    }
    if (leftAttack === rightAttack) {
      return { state: "tie", winner_record_id: null, left_attack: leftAttack, right_attack: rightAttack };
    }
    return {
      state: "known",
      winner_record_id: leftAttack > rightAttack ? recordId(left) : recordId(right),
      left_attack: leftAttack,
      right_attack: rightAttack,
    };
  }

  function pairwiseComparison(left, right) {
    const a = pvpValue(left);
    const b = pvpValue(right);
    const delta = (first, second) => first === null || second === null ? null : Number((first - second).toFixed(4));
    return {
      left_record_id: recordId(left),
      right_record_id: recordId(right),
      rank_percent_delta: delta(a.rankPercent, b.rankPercent),
      stat_product_delta: delta(a.statProduct, b.statProduct),
      dust_cost_delta: delta(a.dust, b.dust),
      candy_cost_delta: delta(a.candy, b.candy),
      cmp: cmpComparison(left, right),
    };
  }

  function buildPvpMatrix(candidates, options = {}) {
    const limit = Math.max(2, Math.min(20, Math.floor(Number(options.limit) || 8)));
    const rows = (Array.isArray(candidates) ? [...candidates] : [])
      .filter((candidate) => recordId(candidate))
      .sort(comparePvpCandidates)
      .slice(0, limit);
    const matrix = rows.map((left) => rows.map((right) => recordId(left) === recordId(right)
      ? { left_record_id: recordId(left), right_record_id: recordId(right), state: "same-record" }
      : pairwiseComparison(left, right)));
    return {
      version: VERSION,
      deterministic: true,
      row_count: rows.length,
      rows,
      matrix,
      warning: "PvP IV Rank 1 is not universally best. This matrix compares owned build inputs and does not substitute for matchup simulation.",
    };
  }

  function buildPvpWorkspace(resource, feedPayload, options = {}) {
    const league = LEAGUES.has(options.league) ? options.league : "great";
    const matrix = buildPvpMatrix(feedPayload?.candidates || [], options);
    const current = resource?.current_simulation || { state: "blocked", reason: "Current PvP data is unavailable." };
    return {
      league,
      exact_owned_record_mapping: true,
      matrix,
      matchup_simulation: {
        state: current.state === "fresh-source-available" ? "blocked-model-inputs" : "blocked-current-data",
        reason: current.reason || "Normalized battle simulation inputs are unavailable.",
        evidence: current.evidence || [],
      },
      assumptions: resource?.simulation_defaults || {},
      comparison_contract: resource?.comparison_contract || {},
    };
  }

  function rocketCandidateComparator(left, right) {
    return ((Number(right?.cp) || 0) - (Number(left?.cp) || 0))
      || ((Number(right?.ivs?.total) || -1) - (Number(left?.ivs?.total) || -1))
      || recordId(left).localeCompare(recordId(right));
  }

  function buildRocketParty(candidates, encounter, options = {}) {
    const size = Math.max(1, Math.min(3, Math.floor(Number(options.size) || 3)));
    const orderedDexes = [...new Set((encounter?.counter_species_dexes || []).map(Number).filter(Number.isFinite))];
    if (!orderedDexes.length || encounter?.counter_mapping_state !== "source-backed") {
      return {
        state: "blocked",
        reason: "This fresh encounter does not contain a source-backed counter-species ordering. Owned inventory may be reviewed, but no matchup party is claimed.",
        team: [],
        alternatives: [],
      };
    }
    const pool = (Array.isArray(candidates) ? candidates : []).filter((candidate) => recordId(candidate));
    const byDex = new Map();
    for (const dex of orderedDexes) byDex.set(dex, []);
    for (const candidate of pool) {
      const dex = Number(candidate?.pokemon_number);
      if (byDex.has(dex)) byDex.get(dex).push(candidate);
    }
    for (const list of byDex.values()) list.sort(rocketCandidateComparator);

    const ordered = [];
    for (const dex of orderedDexes) ordered.push(...byDex.get(dex));
    const team = ordered.slice(0, size);
    const alternatives = ordered.slice(size, size + 6);
    if (!team.length) {
      return {
        state: "blocked",
        reason: "No exact owned record matches the source-backed counter species for this encounter.",
        team: [],
        alternatives: [],
      };
    }
    return {
      state: "available",
      team,
      alternatives,
      source_backed_counter_order: orderedDexes,
      exact_owned_record_mapping: true,
      warning: "Party ordering follows source-backed counter species and owned CP/IV tie-breaks. Move timing, shields, and survivability are not silently inferred when battle inputs are absent.",
    };
  }

  function buildRocketWorkspace(resource, feedPayload, encounterId = null) {
    const current = resource?.current_lineups || {};
    const candidates = Array.isArray(feedPayload?.candidates) ? feedPayload.candidates : [];
    if (current.state !== "fresh") {
      return {
        state: "blocked-current-data",
        reason: current.reason || "Current Team GO Rocket lineup data is unavailable.",
        encounters: current.encounters || [],
        readiness_inventory: [...candidates].sort(rocketCandidateComparator).slice(0, 12),
        party: null,
      };
    }
    const encounters = current.encounters || [];
    const encounter = encounters.find((item) => String(item.encounter_id) === String(encounterId)) || encounters[0] || null;
    return {
      state: encounter ? "fresh" : "blocked-current-data",
      reason: encounter ? null : "No supported current encounter is available.",
      encounters,
      encounter,
      readiness_inventory: [...candidates].sort(rocketCandidateComparator).slice(0, 12),
      party: encounter ? buildRocketParty(candidates, encounter) : null,
    };
  }

  async function fetchJson(root, path) {
    const response = await root.fetch(path, { cache: "no-store" });
    if (!response.ok) throw new Error(`Resource request failed (${response.status})`);
    return response.json();
  }

  function formatNumber(value) {
    const number = asNumber(value);
    return number === null ? "Unknown" : number.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }

  function candidateLabel(candidate) {
    const form = candidate?.form ? ` ${candidate.form}` : "";
    return `${candidate?.name || "Unknown"}${form} · CP ${formatNumber(candidate?.cp)}`;
  }

  function pvpRowsHtml(rows) {
    if (!rows.length) return '<p class="battle-note">No exact owned candidates are available for this league.</p>';
    const body = rows.map((candidate) => {
      const pvp = pvpValue(candidate);
      const moves = [candidate?.moves?.fast, candidate?.moves?.charged, candidate?.moves?.charged_second].filter(Boolean).join(" · ") || "Unknown";
      return `<tr><th scope="row">${escapeHtml(candidateLabel(candidate))}<small><code>${escapeHtml(recordId(candidate))}</code></small></th><td>${formatNumber(pvp.rankPercent)}%</td><td>${formatNumber(pvp.rankNumber)}</td><td>${formatNumber(pvp.statProduct)}</td><td>${formatNumber(pvp.dust)} dust · ${formatNumber(pvp.candy)} candy</td><td>${escapeHtml(moves)}</td><td>${pvp.attackStat === null ? "Unavailable" : formatNumber(pvp.attackStat)}</td></tr>`;
    }).join("");
    return `<div class="battle-table-wrap"><table><caption>Exact owned build comparison</caption><thead><tr><th>Owned record</th><th>IV rank %</th><th>Rank #</th><th>Stat product</th><th>Known build cost</th><th>Current scanned moves</th><th>Battle Attack / CMP input</th></tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function pvpMatrixHtml(matrix) {
    const rows = matrix.rows;
    if (rows.length < 2) return "";
    const headers = rows.map((item, index) => `<th scope="col">${index + 1}. ${escapeHtml(item.name || "Owned")}</th>`).join("");
    const body = matrix.matrix.map((line, rowIndex) => {
      const cells = line.map((cell) => {
        if (cell.state === "same-record") return '<td aria-label="Same record">—</td>';
        const rank = cell.rank_percent_delta === null ? "rank ?" : `${cell.rank_percent_delta >= 0 ? "+" : ""}${cell.rank_percent_delta} rank%`;
        const stat = cell.stat_product_delta === null ? "stat ?" : `${cell.stat_product_delta >= 0 ? "+" : ""}${cell.stat_product_delta} stat`;
        const cmp = cell.cmp?.state === "known" ? (cell.cmp.winner_record_id === cell.left_record_id ? "CMP left" : "CMP right") : cell.cmp?.state === "tie" ? "CMP tie" : "CMP unavailable";
        return `<td>${escapeHtml(rank)}<small>${escapeHtml(stat)} · ${escapeHtml(cmp)}</small></td>`;
      }).join("");
      return `<tr><th scope="row">${rowIndex + 1}. ${escapeHtml(rows[rowIndex].name || "Owned")}</th>${cells}</tr>`;
    }).join("");
    return `<details><summary>Expert pairwise matrix</summary><div class="battle-table-wrap"><table><caption>Left record minus column record. CMP appears only with comparable battle Attack.</caption><thead><tr><th>Left vs column</th>${headers}</tr></thead><tbody>${body}</tbody></table></div></details>`;
  }

  function pvpStatusHtml(workspace) {
    const simulation = workspace.matchup_simulation;
    const evidence = (simulation.evidence || []).map((item) => `<li>${escapeHtml(item.provider || "Unknown provider")} · ${escapeHtml(item.dataset_timestamp || "unknown timestamp")} · ${escapeHtml(item.data_category || "PvP")}</li>`).join("");
    return `<section class="battle-status ${simulation.state.startsWith("blocked") ? "is-blocked" : ""}"><h2>Current matchup simulation</h2><p><strong>${escapeHtml(simulation.state)}</strong>: ${escapeHtml(simulation.reason)}</p>${evidence ? `<details><summary>Freshness evidence</summary><ul>${evidence}</ul></details>` : ""}</section>`;
  }

  async function installPvp(root, mount) {
    const resource = await fetchJson(root, "data/pvp-battle-lab.json");
    mount.innerHTML = `<section class="battle-controls"><label>League <select id="pvp-lab-league"><option value="great">Great League</option><option value="ultra">Ultra League</option><option value="little">Little League</option><option value="master">Master League</option></select></label><label>Compare up to <select id="pvp-lab-limit"><option>4</option><option selected>8</option><option>12</option><option>20</option></select></label></section><div id="pvp-lab-output" aria-live="polite"></div>`;
    const league = mount.querySelector("#pvp-lab-league");
    const limit = mount.querySelector("#pvp-lab-limit");
    const output = mount.querySelector("#pvp-lab-output");
    const cache = new Map();
    const render = async () => {
      const selected = LEAGUES.has(league.value) ? league.value : "great";
      const meta = resource.owned_candidate_feeds?.[selected];
      if (!meta?.path) {
        output.innerHTML = '<p class="battle-note">Candidate feed is unavailable.</p>';
        return;
      }
      if (!cache.has(meta.path)) cache.set(meta.path, await fetchJson(root, meta.path));
      const workspace = buildPvpWorkspace(resource, cache.get(meta.path), { league: selected, limit: Number(limit.value) });
      output.innerHTML = `${pvpStatusHtml(workspace)}<section><h2>Owned comparison</h2><p class="battle-note">${escapeHtml(workspace.matrix.warning)}</p>${pvpRowsHtml(workspace.matrix.rows)}${pvpMatrixHtml(workspace.matrix)}</section><details><summary>Expert assumptions</summary><pre>${escapeHtml(JSON.stringify(workspace.assumptions, null, 2))}</pre></details>`;
    };
    league.addEventListener("change", () => render().catch(() => { output.textContent = "PvP Battle Lab could not load the requested owned feed."; }));
    limit.addEventListener("change", () => render().catch(() => { output.textContent = "PvP Battle Lab could not update the comparison."; }));
    await render();
  }

  function rocketEncounterLabel(encounter) {
    return encounter?.phrase || encounter?.grunt_phrase || encounter?.leader || encounter?.boss || encounter?.encounter_id || "Current encounter";
  }

  function readinessHtml(records) {
    if (!records.length) return '<p class="battle-note">No owned Rocket-readiness candidates with known moves are available.</p>';
    const rows = records.map((candidate) => `<tr><th scope="row">${escapeHtml(candidateLabel(candidate))}<small><code>${escapeHtml(recordId(candidate))}</code></small></th><td>${escapeHtml([candidate?.moves?.fast, candidate?.moves?.charged].filter(Boolean).join(" · ") || "Unknown")}</td><td>${escapeHtml((candidate?.knowledge?.types || []).join(" / ") || "Unknown")}</td></tr>`).join("");
    return `<div class="battle-table-wrap"><table><caption>Owned readiness inventory, not a current matchup ranking</caption><thead><tr><th>Owned record</th><th>Scanned moves</th><th>Stable species types</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  function rocketPartyHtml(workspace) {
    if (!workspace.party) return "";
    if (workspace.party.state !== "available") return `<section class="battle-status is-blocked"><h2>Party recommendation blocked</h2><p>${escapeHtml(workspace.party.reason)}</p></section>`;
    const list = workspace.party.team.map((candidate, index) => `<li><strong>${index + 1}. ${escapeHtml(candidateLabel(candidate))}</strong><br><code>${escapeHtml(recordId(candidate))}</code></li>`).join("");
    const alternatives = workspace.party.alternatives.map((candidate) => `<li>${escapeHtml(candidateLabel(candidate))} · <code>${escapeHtml(recordId(candidate))}</code></li>`).join("");
    return `<section><h2>Source-backed owned party</h2><ol>${list}</ol><p class="battle-note">${escapeHtml(workspace.party.warning)}</p>${alternatives ? `<details><summary>Owned alternatives</summary><ul>${alternatives}</ul></details>` : ""}</section>`;
  }

  async function installRocket(root, mount) {
    const [resource, feed] = await Promise.all([
      fetchJson(root, "data/rocket-planner.json"),
      fetchJson(root, "data/candidates/rocket-battle-inputs.json"),
    ]);
    const encounters = resource.current_lineups?.encounters || [];
    const chooser = encounters.length ? `<label>Current encounter <select id="rocket-encounter">${encounters.map((item) => `<option value="${escapeHtml(item.encounter_id)}">${escapeHtml(rocketEncounterLabel(item))}</option>`).join("")}</select></label>` : "";
    mount.innerHTML = `${chooser ? `<section class="battle-controls">${chooser}</section>` : ""}<div id="rocket-output" aria-live="polite"></div>`;
    const select = mount.querySelector("#rocket-encounter");
    const output = mount.querySelector("#rocket-output");
    const render = () => {
      const workspace = buildRocketWorkspace(resource, feed, select?.value || null);
      const statusClass = workspace.state === "fresh" ? "" : " is-blocked";
      const encounter = workspace.encounter;
      const branching = encounter?.slots ? `<details><summary>Branching lineup/source details</summary><pre>${escapeHtml(JSON.stringify(encounter.slots, null, 2))}</pre></details>` : "";
      output.innerHTML = `<section class="battle-status${statusClass}"><h2>Rotation status</h2><p><strong>${escapeHtml(workspace.state)}</strong>${workspace.reason ? `: ${escapeHtml(workspace.reason)}` : ": fresh supported encounter data is available."}</p></section>${branching}${rocketPartyHtml(workspace)}<section><h2>Owned readiness inventory</h2>${readinessHtml(workspace.readiness_inventory)}</section>`;
    };
    select?.addEventListener("change", render);
    render();
  }

  async function install(root) {
    const pvp = root.document.getElementById("pvp-battle-lab-root");
    const rocket = root.document.getElementById("rocket-planner-root");
    const jobs = [];
    if (pvp) jobs.push(installPvp(root, pvp).catch(() => { pvp.textContent = "PvP Battle Lab resources could not be loaded."; }));
    if (rocket) jobs.push(installRocket(root, rocket).catch(() => { rocket.textContent = "Team GO Rocket Planner resources could not be loaded."; }));
    await Promise.all(jobs);
    return jobs.length > 0;
  }

  return {
    VERSION,
    asNumber,
    pvpValue,
    comparePvpCandidates,
    cmpComparison,
    pairwiseComparison,
    buildPvpMatrix,
    buildPvpWorkspace,
    buildRocketParty,
    buildRocketWorkspace,
    install,
  };
});
