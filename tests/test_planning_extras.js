"use strict";

const assert = require("node:assert/strict");
const Planning = require("../site/planning.js");
const Extras = require("../site/planning-extras.js");

(function testExclusionNormalizationAndPersistenceShape() {
  assert.deepEqual(Extras.normalizeExclusions("25, Pikachu, 25, garchomp:mega"), ["25", "pikachu", "garchomp:mega"]);
  assert.deepEqual(Extras.exclusionPayload({ version: 1, by_goal: { g1: ["25", "Pikachu"] } }), {
    version: 1,
    by_goal: { g1: ["25", "pikachu"] },
  });
})();

(function testGoalDetailAppliesPerGoalExclusionsAndExactDrilldown() {
  const knowledge = Planning.buildKnowledgeIndex({
    dataset_version: "test",
    classification: "Verified community data",
    mechanics: { cp_multiplier_levels: [] },
    entries: [
      { dex: 25, species_id: "pikachu", display_name: "Pikachu", base_name: "Pikachu", form_key: "normal", form_aliases: ["normal"], released: true, transformation: { eligible: false } },
      { dex: 26, species_id: "raichu", display_name: "Raichu", base_name: "Raichu", form_key: "normal", form_aliases: ["normal"], released: true, transformation: { eligible: false } },
    ],
  });
  const records = [
    { identity: { record_id: "pika" }, pokemon_number: 25, name: "Pikachu", form: null, ivs: { is_hundo: true }, status: {}, pvp: {} },
    { identity: { record_id: "rai" }, pokemon_number: 26, name: "Raichu", form: null, ivs: { is_hundo: false }, status: {}, pvp: {} },
  ];
  const detail = Extras.goalDetail(
    { id: "g", kind: "hundo", target: 1, threshold: 98 },
    { Planning, records, knowledge, mega: { candidates: [] } },
    ["26"],
  );
  assert.equal(detail.status, "available");
  assert.equal(detail.achieved, 1);
  assert.equal(detail.missing.length, 0);
  assert.equal(detail.exclusions.length, 1);
  assert.equal(detail.owned[0].record_id, "pika");
})();

(function testGoalDetailReportsUnsupportedInsteadOfMissing() {
  const detail = Extras.goalDetail({ kind: "shiny", target: 1 }, { Planning, records: [] }, []);
  assert.equal(detail.status, "unsupported");
  assert.match(detail.reason, /not a reliable normalized source field/i);
})();

(function testTeamWarningsCoverSecondMoveAndLegacyUncertainty() {
  const warnings = Extras.teamExtraWarnings([
    { name: "Pikachu", moves: { fast: "Thunder Shock", charged: "Wild Charge", charged_second: null } },
  ]);
  assert.ok(warnings.some((warning) => /no second Charged Move/i.test(warning)));
  assert.ok(warnings.some((warning) => /Legacy\/exclusive\/recommended/i.test(warning)));
})();

console.log("planning enhancement tests passed");
