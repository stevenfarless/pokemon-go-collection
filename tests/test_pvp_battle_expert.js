"use strict";

const assert = require("node:assert/strict");
const Expert = require("../site/pvp-battle-expert.js");

function owned(id, dex, name, form = null) {
  return { record_id: id, pokemon_number: dex, name, form };
}

(function testNormalizedFactRequiresExplicitOwnedJoinInputsAndOutcome() {
  assert.equal(Expert.matchupFromFact({ opponent: "X", result: "win" }), null);
  assert.equal(Expert.matchupFromFact({ pokemon_number: 1, result: "win" }), null);
  const row = Expert.matchupFromFact({
    pokemon_number: 1,
    opponent_id: "meta-a",
    opponent_name: "Meta A",
    result: "win",
    battle_rating: 612,
    attack_breakpoints: ["Atk 121.5"],
  }, { provider: "fixture", dataset_timestamp: "2026-08-29T00:00:00Z", model_version: "fixture-1" });
  assert.equal(row.attacker_pokemon_number, 1);
  assert.equal(row.result, "win");
  assert.equal(row.source.provider, "fixture");
  assert.equal(row.model_version, "fixture-1");
})();

(function testRatingNormalizationIsConservative() {
  assert.equal(Expert.normalizeResult(501), "win");
  assert.equal(Expert.normalizeResult(500), "tie");
  assert.equal(Expert.normalizeResult(499), "loss");
  assert.equal(Expert.normalizeResult("unknown"), null);
})();

(function testMatrixMapsEvidenceToExactOwnedRecordsDeterministically() {
  const candidates = [owned("a-1", 1, "Alpha"), owned("a-2", 1, "Alpha"), owned("b-1", 2, "Beta")];
  const matchups = [
    { attacker_pokemon_number: 1, attacker_form: null, opponent_id: "x", opponent_name: "X", result: "win", shields: 1, starting_energy: 0, starting_hp_percent: 100 },
    { attacker_pokemon_number: 1, attacker_form: null, opponent_id: "y", opponent_name: "Y", result: "loss", shields: 1, starting_energy: 0, starting_hp_percent: 100 },
    { attacker_pokemon_number: 2, attacker_form: null, opponent_id: "y", opponent_name: "Y", result: "win", shields: 1, starting_energy: 0, starting_hp_percent: 100 },
  ];
  const result = Expert.buildExpertMatrix(candidates, matchups, { shields: 1, starting_energy: 0, starting_hp_percent: 100 });
  assert.equal(result.deterministic, true);
  assert.deepEqual(result.rows.map((row) => row.record_id), ["a-1", "a-2", "b-1"]);
  assert.deepEqual(result.rows[0].outcomes, { win: 1, loss: 1, tie: 0 });
  assert.equal(result.rows[0].win_rate, 50);
  assert.equal(result.threats.find((item) => item.opponent_id === "y").uncovered, false);
  assert.equal(result.uncovered_threats, 0);
})();

(function testUncoveredThreatsRemainVisible() {
  const result = Expert.buildExpertMatrix([owned("a", 1, "Alpha")], [
    { attacker_pokemon_number: 1, opponent_id: "wall", opponent_name: "Wall", result: "loss" },
  ]);
  assert.equal(result.uncovered_threats, 1);
  assert.deepEqual(result.threats[0].owned_losses, ["a"]);
  assert.deepEqual(result.threats[0].owned_wins, []);
})();

(function testAssumptionMismatchDoesNotCreateOutcomeClaim() {
  const result = Expert.buildExpertMatrix([owned("a", 1, "Alpha")], [
    { attacker_pokemon_number: 1, opponent_id: "x", opponent_name: "X", result: "win", shields: 0 },
  ], { shields: 1 });
  assert.equal(result.matchup_count, 0);
  assert.equal(result.rows[0].win_rate, null);
})();

(function testBreakpointsAndBulkpointsPreserveSourceValues() {
  const matrix = Expert.buildExpertMatrix([owned("a", 1, "Alpha")], [
    {
      attacker_pokemon_number: 1,
      opponent_id: "x",
      opponent_name: "X",
      result: "win",
      attack_breakpoints: [{ attack: 121.5, effect: "+1 fast damage" }],
      defense_bulkpoints: [{ defense: 130.2, effect: "-1 fast damage" }],
    },
  ]);
  const points = Expert.meaningfulPoints(matrix);
  assert.equal(points.length, 2);
  assert.equal(points[0].kind, "attack breakpoint");
  assert.equal(points[1].kind, "defense bulkpoint");
})();

(function testWalkFactsFindsSupportedRowsWithoutInventingUnsupportedOnes() {
  const rows = Expert.walkFacts({ nested: [{ pokemon_number: 25, opponent: "Ground threat", outcome: "loss" }, { note: "not a matchup" }] }, { provider: "fixture" });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].attacker_pokemon_number, 25);
  assert.equal(rows[0].result, "loss");
})();

console.log("expert pvp battle tests passed");
