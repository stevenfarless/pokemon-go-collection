"use strict";

const assert = require("node:assert/strict");
const { evaluateTrade, summarizeEligibility } = require("../site/trade-rules.js");
const registry = require("../knowledge/trade-rules.v1.json");

const remoteFacts = {
  caught_within_30_days: false, previously_traded: false, shadow: false, mythical: false,
  gym_or_power_spot_defender: false, current_buddy: false, active_mega: false, fused: false,
  crowned_zacian_or_zamazenta: false, pokemon_playground: false,
};

{
  const result = evaluateTrade("remote", remoteFacts, { forever_friend: true, remote_trade_available: true, remote_trades_completed_today: 0, lucky_friend: true }, {}, registry);
  assert.equal(result.state, "eligible");
  assert.equal(result.special_trade, false);
  assert.equal(result.lucky, true);
  assert.equal(result.post_trade_stats_guaranteed, false);
}

{
  const result = evaluateTrade("remote", {}, { forever_friend: true, remote_trade_available: true }, {}, registry);
  assert.equal(result.state, "unknown");
  assert.ok(result.unknowns.includes("remote_trades_completed_today"));
  assert.ok(result.unknowns.includes("previously_traded"));
  assert.match(summarizeEligibility(result), /^Needs confirmation:/);
}

{
  const result = evaluateTrade("remote", { ...remoteFacts, shadow: true }, { forever_friend: true, remote_trade_available: true, remote_trades_completed_today: 0 }, {}, registry);
  assert.equal(result.state, "blocked");
  assert.deepEqual(result.blockers, ["shadow"]);
  assert.match(summarizeEligibility(result), /^Blocked:/);
}

{
  const result = evaluateTrade("in_person", {
    previously_traded: false, mythical_trade_blocked: false, legendary: true,
  }, {}, { level: 50 }, registry);
  assert.equal(result.state, "eligible");
  assert.equal(result.special_trade, true);
}

{
  const result = evaluateTrade("in_person", { previously_traded: false }, {}, { level: 9 }, registry);
  assert.equal(result.state, "blocked");
  assert.ok(result.blockers.includes("trainer_level_below_minimum"));
  assert.ok(result.unknowns.includes("mythical_trade_blocked"));
}

{
  const result = evaluateTrade("in_person", { previously_traded: false, mythical_trade_blocked: false }, {}, { level: "unknown" }, registry);
  assert.equal(result.state, "unknown");
  assert.deepEqual(result.unknowns, ["trainer_level"]);
}

{
  const result = evaluateTrade("remote", remoteFacts, { forever_friend: true, remote_trade_available: true, remote_trades_completed_today: "unknown" }, {}, registry);
  assert.equal(result.state, "unknown");
  assert.deepEqual(result.unknowns, ["remote_trades_completed_today"]);
}

assert.throws(() => evaluateTrade("postal", {}, {}, {}, registry), /Unsupported trade mode/);
console.log("trade rules browser tests passed");
