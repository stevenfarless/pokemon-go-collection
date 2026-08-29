"use strict";

(function exposePvpBattleExpert(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.PvpBattleExpert = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const VERSION = "1.0.0";
  const PVP_CATEGORIES = new Set(["pvp", "pvp-meta", "gbl", "cups", "pvp-rankings"]);

  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  function asNumber(value) {
    if (value === null || value === undefined || value === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function recordId(candidate) {
    return String(candidate?.record_id || candidate?.identity?.record_id || "");
  }

  function normalizeResult(value) {
    const result = String(value || "").toLowerCase();
    if (["win", "loss", "tie"].includes(result)) return result;
    const rating = asNumber(value);
    if (rating === null) return null;
    if (rating > 500) return "win";
    if (rating < 500) return "loss";
    return "tie";
  }

  function matchupFromFact(fact, source = {}) {
    if (!fact || typeof fact !== "object") return null;
    const attackerDex = asNumber(fact.attacker_pokemon_number ?? fact.pokemon_number ?? fact.dex ?? fact.attacker_dex);
    const opponent = fact.opponent_id || fact.opponent || fact.defender || fact.target || fact.opponent_name;
    const result = normalizeResult(fact.result ?? fact.outcome ?? fact.battle_rating ?? fact.rating);
    if (attackerDex === null || !opponent || !result) return null;
    return {
      attacker_pokemon_number: attackerDex,
      attacker_form: fact.attacker_form || fact.form || null,
      opponent_id: String(fact.opponent_id || opponent),
      opponent_name: String(fact.opponent_name || opponent),
      result,
      battle_rating: asNumber(fact.battle_rating ?? fact.rating),
      attack_breakpoints: Array.isArray(fact.attack_breakpoints) ? fact.attack_breakpoints : [],
      defense_bulkpoints: Array.isArray(fact.defense_bulkpoints) ? fact.defense_bulkpoints : [],
      role: fact.role || null,
      shields: asNumber(fact.shields),
      starting_energy: asNumber(fact.starting_energy),
      starting_hp_percent: asNumber(fact.starting_hp_percent),
      model_version: fact.model_version || source.model_version || source.version || null,
      source: {
        provider: source.provider || null,
        dataset_timestamp: source.dataset_timestamp || null,
        source_reference: source.source_reference || null,
        authority: source.authority || null,
      },
    };
  }

  function walkFacts(value, source, output = []) {
    if (Array.isArray(value)) {
      for (const item of value) walkFacts(item, source, output);
    } else if (value && typeof value === "object") {
      const normalized = matchupFromFact(value, source);
      if (normalized) output.push(normalized);
      for (const child of Object.values(value)) {
        if (child && typeof child === "object") walkFacts(child, source, output);
      }
    }
    return output;
  }

  function assumptionsMatch(matchup, options = {}) {
    for (const key of ["shields", "starting_energy", "starting_hp_percent"]) {
      const requested = asNumber(options[key]);
      const actual = asNumber(matchup[key]);
      if (requested !== null && actual !== null && requested !== actual) return false;
    }
    return true;
  }

  function buildExpertMatrix(candidates, matchups, options = {}) {
    const owned = (Array.isArray(candidates) ? candidates : []).filter((item) => recordId(item));
    const evidence = Array.isArray(matchups) ? matchups : [];
    const rows = owned.map((candidate) => {
      const dex = Number(candidate.pokemon_number);
      const form = String(candidate.form || "").toLowerCase();
      const applicable = evidence.filter((item) => Number(item.attacker_pokemon_number) === dex
        && (!item.attacker_form || String(item.attacker_form).toLowerCase() === form)
        && assumptionsMatch(item, options));
      const counts = { win: 0, loss: 0, tie: 0 };
      for (const item of applicable) counts[item.result] += 1;
      return {
        record_id: recordId(candidate),
        pokemon_number: dex,
        name: candidate.name || "Unknown",
        form: candidate.form || null,
        outcomes: counts,
        matchup_count: applicable.length,
        win_rate: applicable.length ? Number((counts.win / applicable.length * 100).toFixed(2)) : null,
        matchups: applicable,
      };
    });
    const opponentIds = [...new Set(evidence.map((item) => item.opponent_id))].sort();
    const threats = opponentIds.map((id) => {
      const relevant = rows.flatMap((row) => row.matchups.filter((item) => item.opponent_id === id).map((item) => ({ row, item })));
      const losses = relevant.filter(({ item }) => item.result === "loss");
      const wins = relevant.filter(({ item }) => item.result === "win");
      return {
        opponent_id: id,
        opponent_name: relevant[0]?.item.opponent_name || id,
        owned_losses: losses.map(({ row }) => row.record_id),
        owned_wins: wins.map(({ row }) => row.record_id),
        uncovered: losses.length > 0 && wins.length === 0,
      };
    }).filter((item) => item.owned_losses.length > 0)
      .sort((a, b) => Number(b.uncovered) - Number(a.uncovered) || b.owned_losses.length - a.owned_losses.length || a.opponent_id.localeCompare(b.opponent_id));
    return {
      version: VERSION,
      deterministic: true,
      assumptions: {
        shields: asNumber(options.shields),
        starting_energy: asNumber(options.starting_energy),
        starting_hp_percent: asNumber(options.starting_hp_percent),
      },
      rows,
      threats,
      uncovered_threats: threats.filter((item) => item.uncovered).length,
      matchup_count: rows.reduce((sum, row) => sum + row.matchup_count, 0),
    };
  }

  function meaningfulPoints(matrix) {
    const output = [];
    for (const row of matrix.rows) {
      for (const matchup of row.matchups) {
        for (const point of matchup.attack_breakpoints || []) output.push({ record_id: row.record_id, opponent: matchup.opponent_name, kind: "attack breakpoint", value: point });
        for (const point of matchup.defense_bulkpoints || []) output.push({ record_id: row.record_id, opponent: matchup.opponent_name, kind: "defense bulkpoint", value: point });
      }
    }
    return output;
  }

  function evidenceHtml(matrix) {
    if (!matrix.matchup_count) return '<p class="battle-note">No normalized fresh matchup rows match these owned Pokémon and assumptions. Wins, losses, breakpoints, and team-threat claims remain blocked.</p>';
    const rows = matrix.rows.filter((row) => row.matchup_count).map((row) => `<tr><th scope="row">${esc(row.name)}<small><code>${esc(row.record_id)}</code></small></th><td>${row.outcomes.win}</td><td>${row.outcomes.loss}</td><td>${row.outcomes.tie}</td><td>${row.win_rate === null ? "Unknown" : `${row.win_rate}%`}</td></tr>`).join("");
    const threats = matrix.threats.slice(0, 12).map((item) => `<li><strong>${esc(item.opponent_name)}</strong>: ${item.uncovered ? "uncovered threat" : "covered by at least one compared owned record"} · losses ${item.owned_losses.length} · wins ${item.owned_wins.length}</li>`).join("");
    const points = meaningfulPoints(matrix).slice(0, 20).map((item) => `<li><code>${esc(item.record_id)}</code> vs ${esc(item.opponent)} · ${esc(item.kind)} · ${esc(typeof item.value === "object" ? JSON.stringify(item.value) : item.value)}</li>`).join("");
    return `<div class="battle-table-wrap"><table><caption>Fresh normalized matchup evidence for exact owned records</caption><thead><tr><th>Owned record</th><th>Wins</th><th>Losses</th><th>Ties</th><th>Win rate</th></tr></thead><tbody>${rows}</tbody></table></div>${threats ? `<details open><summary>Team threats</summary><ul>${threats}</ul></details>` : ""}${points ? `<details><summary>Meaningful breakpoints and bulkpoints</summary><ul>${points}</ul></details>` : ""}`;
  }

  async function fetchJson(root, path) {
    const response = await root.fetch(path, { cache: "no-store" });
    if (!response.ok) throw new Error(`Resource request failed (${response.status})`);
    return response.json();
  }

  async function loadFreshMatchups(root) {
    const index = await fetchJson(root, "data/external/index.json");
    const snapshots = (index.snapshots || []).filter((item) => PVP_CATEGORIES.has(String(item.data_category || "").toLowerCase())
      && item.freshness?.state === "fresh" && item.path);
    const output = [];
    for (const item of snapshots) {
      const payload = await fetchJson(root, item.path);
      if (payload.freshness?.state !== "fresh") continue;
      const source = {
        provider: item.provider,
        dataset_timestamp: item.dataset_timestamp,
        source_reference: item.source_reference,
        authority: item.authority,
        model_version: payload.model_version || item.model_version,
        version: payload.version,
      };
      walkFacts(payload.facts || payload.matchups || [], source, output);
    }
    return output;
  }

  async function install(root) {
    const mount = root.document.getElementById("pvp-battle-lab-root");
    if (!mount || root.document.getElementById("pvp-expert-evidence")) return false;
    const section = root.document.createElement("section");
    section.id = "pvp-expert-evidence";
    section.className = "battle-status";
    section.innerHTML = '<h2>Expert matchup evidence</h2><p role="status">Checking fresh normalized matchup evidence…</p>';
    mount.insertAdjacentElement("afterend", section);
    let matchups = [];
    try { matchups = await loadFreshMatchups(root); } catch (_) { matchups = []; }
    const cache = new Map();
    const render = async () => {
      const league = root.document.getElementById("pvp-lab-league")?.value || "great";
      const path = `data/candidates/${league}-league.json`;
      if (!cache.has(path)) cache.set(path, await fetchJson(root, path));
      const feed = cache.get(path);
      const matrix = buildExpertMatrix(feed.candidates || [], matchups, { shields: 1, starting_energy: 0, starting_hp_percent: 100 });
      section.innerHTML = `<h2>Expert matchup evidence</h2><p class="battle-note">Only fresh, normalized source rows with explicit outcomes are used. Rank alone never creates a win, breakpoint, bulkpoint, or role claim.</p>${evidenceHtml(matrix)}<details><summary>Pinned assumptions</summary><pre>${esc(JSON.stringify(matrix.assumptions, null, 2))}</pre></details>`;
    };
    root.document.getElementById("pvp-lab-league")?.addEventListener("change", () => render().catch(() => {}));
    await render();
    return true;
  }

  return { VERSION, asNumber, normalizeResult, matchupFromFact, walkFacts, assumptionsMatch, buildExpertMatrix, meaningfulPoints, install };
});
