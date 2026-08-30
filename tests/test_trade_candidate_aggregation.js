"use strict";

const assert = require("assert");
const Filters = require("../site/trade-matcher-filters.js");

const rules = {
  evaluateTrade(_mode, facts) {
    return { state: facts.shiny === true || facts.mythical_trade_blocked === false ? "eligible" : "unknown", blockers: [], unknowns: [] };
  },
};
const pair = {
  a_gives: { candidates: [{ record_id: "eligible" }, { record_id: "unknown" }] },
  b_gives: { candidates: [{ guest_id: "guest" }] },
};
const normal = (id) => ({ identity: { record_id: id }, pokemon_number: 25, status: { shadow_purified: "normal" } });
const result = Filters.evaluatePair(pair, {
  rules,
  mode: "in_person",
  player_a: new Map([["eligible", normal("eligible")], ["unknown", normal("unknown")]]),
  player_b: new Map([["guest", { pokemon_number: 808, status: { shadow_purified: "normal" } }]]),
  enrichment: { records: { eligible: { shiny: "yes" } } },
});

assert.equal(result.a[0].evaluation.state, "eligible");
assert.equal(result.a[1].evaluation.state, "unknown");
assert.equal(result.b[0].evaluation.state, "eligible");
assert.equal(result.state, "eligible");
console.log("trade candidate aggregation tests passed");
