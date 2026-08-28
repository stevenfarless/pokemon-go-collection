"use strict";

const assert = require("node:assert/strict");
const Battle = require("../site/battle-labs.js");

function candidate(id, dex, name, cp, rankPercent, rankNumber, statProduct, extra = {}) {
  return {
    record_id: id,
    pokemon_number: dex,
    name,
    form: null,
    cp,
    ivs: { total: extra.ivTotal ?? 40, attack: extra.attackIv ?? 10, defense: 15, stamina: 15 },
    moves: { fast: "Fast Move", charged: "Charged Move", charged_second: null },
    knowledge: { types: extra.types || ["normal"] },
    pvp: {
      rank_percent: rankPercent,
      rank_number: rankNumber,
      stat_product: statProduct,
      dust_cost: extra.dust ?? 10000,
      candy_cost: extra.candy ?? 10,
      ...(extra.attackStat === undefined ? {} : { attack_stat: extra.attackStat }),
    },
  };
}

(function testOwnedPvpMatrixIsDeterministicAndExact() {
  const owned = [
    candidate("owned-b", 2, "Beta", 1492, 98.5, 12, 1840, { dust: 5000 }),
    candidate("owned-a", 1, "Alpha", 1498, 99.7, 3, 1820, { dust: 30000 }),
    candidate("owned-c", 3, "Gamma", 1487, 97.1, 44, 1810),
  ];
  const result = Battle.buildPvpMatrix(owned, { limit: 3 });
  assert.equal(result.deterministic, true);
  assert.deepEqual(result.rows.map((item) => item.record_id), ["owned-a", "owned-b", "owned-c"]);
  assert.equal(result.matrix.length, 3);
  assert.equal(result.matrix[0][0].state, "same-record");
  assert.equal(result.matrix[0][1].left_record_id, "owned-a");
  assert.equal(result.matrix[0][1].right_record_id, "owned-b");
  assert.match(result.warning, /not universally best/i);
})();

(function testCmpNeverUsesAttackIvAsBattleAttack() {
  const left = candidate("left", 10, "Left", 1490, 99, 1, 1800, { attackIv: 15 });
  const right = candidate("right", 11, "Right", 1490, 98, 2, 1790, { attackIv: 0 });
  const unavailable = Battle.cmpComparison(left, right);
  assert.equal(unavailable.state, "unavailable");
  assert.match(unavailable.reason, /Attack IV alone/i);

  left.pvp.attack_stat = 121.25;
  right.pvp.attack_stat = 120.8;
  const known = Battle.cmpComparison(left, right);
  assert.equal(known.state, "known");
  assert.equal(known.winner_record_id, "left");
})();

(function testPvpWorkspaceBlocksCurrentClaimsWithoutFreshData() {
  const feed = { candidates: [candidate("a", 1, "A", 1490, 99, 1, 1800)] };
  const resource = {
    current_simulation: { state: "blocked", reason: "No fresh current PvP snapshot." },
    simulation_defaults: { shields: 1 },
  };
  const workspace = Battle.buildPvpWorkspace(resource, feed, { league: "great" });
  assert.equal(workspace.matchup_simulation.state, "blocked-current-data");
  assert.equal(workspace.exact_owned_record_mapping, true);
  assert.equal(workspace.assumptions.shields, 1);
})();

(function testRocketWorkspaceBlocksStaleRotationButStillShowsInventory() {
  const feed = {
    candidates: [
      candidate("low", 1, "Low", 1000, null, null, null),
      candidate("high", 2, "High", 2000, null, null, null),
    ],
  };
  const resource = { current_lineups: { state: "blocked", reason: "Rotation is stale.", encounters: [] } };
  const workspace = Battle.buildRocketWorkspace(resource, feed);
  assert.equal(workspace.state, "blocked-current-data");
  assert.match(workspace.reason, /stale/i);
  assert.deepEqual(workspace.readiness_inventory.map((item) => item.record_id), ["high", "low"]);
  assert.equal(workspace.party, null);
})();

(function testRocketPartyUsesOnlySourceBackedDexesAndExactOwnedRecords() {
  const owned = [
    candidate("machamp-1", 68, "Machamp", 2900, null, null, null, { ivTotal: 43 }),
    candidate("machamp-2", 68, "Machamp", 2700, null, null, null, { ivTotal: 45 }),
    candidate("mewtwo", 150, "Mewtwo", 4100, null, null, null),
    candidate("other", 25, "Pikachu", 900, null, null, null),
  ];
  const encounter = {
    encounter_id: "leader-example",
    counter_species_dexes: [68, 150],
    counter_mapping_state: "source-backed",
  };
  const result = Battle.buildRocketParty(owned, encounter, { size: 3 });
  assert.equal(result.state, "available");
  assert.deepEqual(result.team.map((item) => item.record_id), ["machamp-1", "machamp-2", "mewtwo"]);
  assert.ok(result.team.every((item) => [68, 150].includes(item.pokemon_number)));
  assert.ok(result.team.every((item) => owned.includes(item)));
  assert.equal(result.exact_owned_record_mapping, true);

  const blocked = Battle.buildRocketParty(owned, { counter_species_dexes: [], counter_mapping_state: "unavailable" });
  assert.equal(blocked.state, "blocked");
  assert.equal(blocked.team.length, 0);
})();

console.log("battle lab tests passed");
