"use strict";

const assert = require("node:assert/strict");
const Labs = require("../site/opportunity-special-labs.js");

(function testOpportunityStateNormalizesAndDeduplicates() {
  const value = Labs.normalizeOpportunityState({
    objective: "roster-gaps",
    hidden_opportunity_ids: ["a", "a", "b"],
    hidden_species_ids: ["bulbasaur", "bulbasaur"],
    show_hidden: true,
  });
  assert.equal(value.version, 1);
  assert.equal(value.objective, "roster-gaps");
  assert.deepEqual(value.hidden_opportunity_ids, ["a", "b"]);
  assert.deepEqual(value.hidden_species_ids, ["bulbasaur"]);
  assert.equal(value.show_hidden, true);
})();

(function testOpportunityObjectivesOnlyReorderInspectableDimensions() {
  const items = [
    { id: "owned", dex: 2, group: "right_now", owned_count: 5, personalization: { missing_species: false, missing_form: false, weak_roster_types: [] } },
    { id: "missing", dex: 1, group: "right_now", owned_count: 0, personalization: { missing_species: true, missing_form: true, weak_roster_types: [] } },
    { id: "roster", dex: 3, group: "right_now", owned_count: 2, personalization: { missing_species: false, missing_form: false, weak_roster_types: ["ice", "rock"] } },
  ];
  assert.equal(Labs.sortOpportunities(items, "missing-first")[0].id, "missing");
  assert.equal(Labs.sortOpportunities(items, "roster-gaps")[0].id, "roster");
  assert.equal(Labs.sortOpportunities(items, "owned-count")[0].id, "missing");
  assert.equal(items[0].id, "owned");
})();

(function testAdventureEffectScenarioUsesReviewedIncrementCost() {
  const effect = {
    duration_increment_minutes: 6,
    cost_per_increment: { stardust: 5000, candy: 5 },
  };
  assert.deepEqual(Labs.adventureEffectScenario(effect, 3), {
    status: "known",
    increments: 3,
    duration_minutes: 18,
    stardust: 15000,
    candy: 15,
  });
  assert.equal(Labs.adventureEffectScenario({}, 2).status, "unavailable");
})();

(function testSpecialStateKeepsUnknownDistinctFromNo() {
  const value = Labs.normalizeSpecialState({
    records: {
      a: { fused: "unknown" },
      b: { fused: "no" },
      c: { fused: "invalid" },
    },
    resources: { solar: 1000, bad: -1, unknown: null },
  });
  assert.equal(value.records.a.fused, "unknown");
  assert.equal(value.records.b.fused, "no");
  assert.equal(value.records.c.fused, "unknown");
  assert.equal(value.resources.solar, 1000);
  assert.equal(value.resources.unknown, null);
  assert.equal(Object.hasOwn(value.resources, "bad"), false);
})();

(function testBackupRoundTripCoversBothLocalNamespaces() {
  const backup = Labs.buildBackup(
    { objective: "owned-count", hidden_opportunity_ids: ["x"], hidden_species_ids: [] },
    { records: { r1: { fused: "yes", note: "confirmed" } }, resources: { lunar: 500 } },
  );
  const restored = Labs.validateBackup(backup);
  assert.equal(restored.opportunity.objective, "owned-count");
  assert.deepEqual(restored.opportunity.hidden_opportunity_ids, ["x"]);
  assert.equal(restored.special.records.r1.fused, "yes");
  assert.equal(restored.special.resources.lunar, 500);
})();

console.log("opportunity/special labs tests passed");
