"use strict";

const assert = require("node:assert/strict");
const Planning = require("../site/planning.js");

(function testLevel40To50CostMatchesVersionedTable() {
  const normal = Planning.powerUpCost(40, 50, { lucky: false, shadow_purified: "normal" });
  assert.equal(normal.status, "known");
  assert.equal(normal.dust, 250000);
  assert.equal(normal.candy, 0);
  assert.equal(normal.xl, 296);
  assert.equal(normal.steps, 20);

  const lucky = Planning.powerUpCost(40, 50, { lucky: true, shadow_purified: "normal" });
  assert.equal(lucky.dust, 125000);
  assert.equal(lucky.xl, 296);
})();

(function testMissingOrInvalidLevelsStayUnavailable() {
  assert.equal(Planning.powerUpCost(null, 40).status, "unavailable");
  assert.equal(Planning.powerUpCost(40.25, 50).status, "unavailable");
  assert.equal(Planning.powerUpCost(45, 40).status, "unavailable");
})();

(function testCpFormulaUsesExplicitInputs() {
  const lower = Planning.cpAtLevel({ attack: 200, defense: 180, stamina: 190 }, { attack: 15, defense: 15, stamina: 15 }, 0.7);
  const higher = Planning.cpAtLevel({ attack: 200, defense: 180, stamina: 190 }, { attack: 15, defense: 15, stamina: 15 }, 0.8);
  assert.ok(Number.isInteger(lower));
  assert.ok(higher > lower);
  assert.equal(Planning.cpAtLevel({ attack: 200 }, { attack: 15, defense: 15, stamina: 15 }, 0.8), null);
})();

(function testOwnedTeamUsesOnlyCandidatesAndUniquePvpSpecies() {
  const candidates = [
    { record_id: "a", pokemon_number: 1, name: "A", cp: 1490, pvp: { rank_percent: 99, rank_number: 1, dust_cost: 10000, candy_cost: 10 } },
    { record_id: "b", pokemon_number: 1, name: "A", cp: 1495, pvp: { rank_percent: 98, rank_number: 2, dust_cost: 5000, candy_cost: 5 } },
    { record_id: "c", pokemon_number: 2, name: "B", cp: 1480, pvp: { rank_percent: 97, rank_number: 3, dust_cost: 20000, candy_cost: 20 } },
    { record_id: "d", pokemon_number: 3, name: "C", cp: 1470, pvp: { rank_percent: 96, rank_number: 4, dust_cost: 30000, candy_cost: 30 } },
  ];
  const result = Planning.buildOwnedTeam(candidates, "great", []);
  assert.equal(result.status, "available");
  assert.deepEqual(result.team.map((item) => item.record_id), ["a", "c", "d"]);
  assert.equal(new Set(result.team.map((item) => item.pokemon_number)).size, 3);
  assert.ok(result.team.every((item) => candidates.includes(item)));
  assert.equal(result.current_meta_used, false);
})();

(function testBudgetOptimizerNeverTreatsMissingCostAsZero() {
  const investments = [
    { record_id: "a", pokemon_number: 1, name: "A", form: null, derived: { pvp_builds: [{ league: "great", rank_percent: 99, rank_number: 1, stardust_cost: 10000, regular_candy_cost: 10, xl_candy_cost: null }] } },
    { record_id: "b", pokemon_number: 2, name: "B", form: null, derived: { pvp_builds: [{ league: "great", rank_percent: 98, rank_number: 2, stardust_cost: null, regular_candy_cost: 0, xl_candy_cost: null }] } },
    { record_id: "c", pokemon_number: 3, name: "C", form: null, derived: { pvp_builds: [{ league: "great", rank_percent: 97, rank_number: 3, stardust_cost: 20000, regular_candy_cost: 20, xl_candy_cost: null }] } },
  ];
  const result = Planning.optimizeBudget(investments, { league: "great", dustBudget: 15000, candyBudget: 15, objective: "max-builds" });
  assert.deepEqual(result.selected.map((item) => item.record_id), ["a"]);
  assert.deepEqual(result.unknown_cost.map((item) => item.record_id), ["b"]);
  assert.equal(result.remaining.stardust, 5000);
})();

(function testGoalsPersistAndUnsupportedFieldsStayUnsupported() {
  const storage = new Map();
  const local = {
    getItem(key) { return storage.get(key) ?? null; },
    setItem(key, value) { storage.set(key, value); },
  };
  const payload = { version: Planning.GOALS_VERSION, goals: [{ id: "g1", kind: "hundo", target: 2, threshold: 98, name: "Two hundos" }] };
  assert.equal(Planning.saveGoals(local, payload), true);
  assert.deepEqual(Planning.loadGoals(local), payload);

  const records = [
    { pokemon_number: 1, form: null, ivs: { is_hundo: true }, status: {} },
    { pokemon_number: 2, form: null, ivs: { is_hundo: false }, status: {} },
  ];
  const progress = Planning.goalProgress(payload.goals[0], { records, feeds: {} });
  assert.equal(progress.achieved, 1);
  assert.equal(progress.target, 2);
  assert.equal(progress.complete, false);
  assert.equal(Planning.goalProgress({ kind: "shiny", target: 1 }, { records }).status, "unsupported");
})();

(function testTradeReviewProtectsValuableSupportedCopies() {
  const base = {
    pokemon_number: 25,
    name: "Pikachu",
    form: null,
    moves: { fast: "Thunder Shock", charged: "Wild Charge", charged_second: null },
    level: { minimum: 20 },
    pvp: { great: { rank_percent: 50 }, ultra: {}, little: {} },
  };
  const records = [
    { ...base, cp: 500, identity: { record_id: "hundo" }, ivs: { average_percent: 100, is_hundo: true, is_nundo: false }, status: { shadow_purified: "normal", favorite: false, lucky: false } },
    { ...base, cp: 450, identity: { record_id: "ordinary" }, ivs: { average_percent: 70, is_hundo: false, is_nundo: false }, status: { shadow_purified: "normal", favorite: false, lucky: false } },
  ];
  const review = Planning.buildTradeReview(records);
  assert.equal(review.group_count, 1);
  const group = review.groups[0];
  assert.equal(group.keeper_record_id, "hundo");
  const hundo = group.candidates.find((item) => item.record_id === "hundo");
  const ordinary = group.candidates.find((item) => item.record_id === "ordinary");
  assert.equal(hundo.protected, true);
  assert.ok(hundo.protection_reasons.includes("hundo"));
  assert.equal(ordinary.review_state, "trade_review_candidate");
})();

console.log("planning tool tests passed");
