"use strict";

(function exposeTradeRules(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionTradeRules = api;
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const knownBool = (values, key) => typeof values?.[key] === "boolean" ? values[key] : null;
  const knownNumber = (value) => {
    if (value === undefined || value === null || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };
  const uniqueSorted = (values) => [...new Set(values)].sort();

  function evaluateTrade(mode, pokemon = {}, friend = {}, trainer = {}, registry = {}) {
    const modeRules = registry?.modes?.[mode];
    if (!modeRules) throw new Error(`Unsupported trade mode: ${mode}`);

    const blockers = [];
    const unknowns = [];
    const minimum = modeRules.trainer_min_level;
    if (minimum !== undefined && minimum !== null) {
      const level = knownNumber(trainer?.level);
      if (level === null) unknowns.push("trainer_level");
      else if (level < Number(minimum)) blockers.push("trainer_level_below_minimum");
    }

    if (modeRules.requires_forever_friend) {
      const value = knownBool(friend, "forever_friend");
      if (value === null) unknowns.push("forever_friend");
      else if (!value) blockers.push("not_forever_friends");
    }

    if (modeRules.requires_available_remote_trade) {
      const value = knownBool(friend, "remote_trade_available");
      if (value === null) unknowns.push("remote_trade_available");
      else if (!value) blockers.push("no_remote_trade_available");
    }

    if (mode === "remote") {
      const count = knownNumber(friend?.remote_trades_completed_today);
      if (count === null) unknowns.push("remote_trades_completed_today");
      else if (count >= Number(registry?.friendship?.remote_trade?.completed_per_day_limit ?? 1)) blockers.push("remote_daily_limit_reached");
    }

    for (const key of modeRules.hard_blockers || []) {
      const value = knownBool(pokemon, key);
      if (value === null) unknowns.push(key);
      else if (value) blockers.push(key);
    }

    const normalizedBlockers = uniqueSorted(blockers);
    const normalizedUnknowns = uniqueSorted(unknowns);
    const state = normalizedBlockers.length ? "blocked" : normalizedUnknowns.length ? "unknown" : "eligible";
    const specialTrade = mode === "remote" ? false : (modeRules.special_trade_categories || []).some((key) => knownBool(pokemon, key) === true);

    return {
      state,
      mode,
      blockers: normalizedBlockers,
      unknowns: normalizedUnknowns,
      special_trade: specialTrade,
      lucky: knownBool(friend, "lucky_friend") === true,
      post_trade_stats_guaranteed: false,
      exact_stardust_cost: null,
      requires_game_confirmation: true,
      reviewed_at: registry?.reviewed_at || null,
    };
  }

  function summarizeEligibility(evaluation) {
    if (!evaluation || !evaluation.state) return "Trade eligibility is unavailable.";
    if (evaluation.state === "blocked") return `Blocked: ${evaluation.blockers.join(", ")}.`;
    if (evaluation.state === "unknown") return `Needs confirmation: ${evaluation.unknowns.join(", ")}.`;
    return `Eligible under reviewed ${evaluation.mode === "remote" ? "Remote Trade" : "in-person trade"} rules; confirm final cost and game state in Pokémon GO.`;
  }

  return { evaluateTrade, summarizeEligibility };
});
