"use strict";

const assert = require("node:assert/strict");
const Engine = require("../site/app.js");

function record(overrides = {}) {
  const base = {
    name: "Bulbasaur",
    form: null,
    pokemon_number: 1,
    gender: "Male",
    cp: 500,
    hp: 60,
    ivs: {
      attack: 10,
      defense: 12,
      stamina: 13,
      average_percent: 77.78,
      total: 35,
      is_hundo: false,
      is_nundo: false,
    },
    level: { minimum: 20, maximum: 20 },
    moves: { fast: "Vine Whip", charged: "Power Whip", charged_second: null },
    dates: { catch: "2026-08-01", scan: "2026-08-05", original_scan: "2026-08-01" },
    size: { weight: 6.9, height: 0.7 },
    status: { lucky: false, favorite: false, marked_for_pvp: false, shadow_purified: "normal" },
    dust: 2500,
    pvp: {
      great: { rank_percent: 98.5, rank_number: 42, stat_product: 1200, dust_cost: 25000, candy_cost: 50, evolution_name: "Venusaur", evolution_form: null, status: "normal" },
      ultra: { rank_percent: null, rank_number: null, stat_product: null, dust_cost: null, candy_cost: null, evolution_name: null, evolution_form: null, status: null },
      little: { rank_percent: 90, rank_number: 400, stat_product: 500, dust_cost: 10000, candy_cost: 25, evolution_name: "Bulbasaur", evolution_form: null, status: "normal" },
    },
  };
  return {
    ...base,
    ...overrides,
    ivs: { ...base.ivs, ...(overrides.ivs || {}) },
    level: { ...base.level, ...(overrides.level || {}) },
    moves: { ...base.moves, ...(overrides.moves || {}) },
    dates: { ...base.dates, ...(overrides.dates || {}) },
    size: { ...base.size, ...(overrides.size || {}) },
    status: { ...base.status, ...(overrides.status || {}) },
    pvp: {
      great: { ...base.pvp.great, ...(overrides.pvp?.great || {}) },
      ultra: { ...base.pvp.ultra, ...(overrides.pvp?.ultra || {}) },
      little: { ...base.pvp.little, ...(overrides.pvp?.little || {}) },
    },
  };
}

(function testSearchSyntax() {
  const shadowMewtwo = record({
    name: "Mewtwo",
    moves: { charged: "Shadow Ball" },
    status: { shadow_purified: "shadow", favorite: true },
  });
  assert.equal(Engine.matchesSearch(shadowMewtwo, 'mewtwo "shadow ball"'), true);
  assert.equal(Engine.matchesSearch(shadowMewtwo, "mewtwo -shadow"), false);
  assert.deepEqual(Engine.parseSearchQuery('pikachu -costume "volt tackle"'), {
    positive: ["pikachu", "volt tackle"],
    negative: ["costume"],
  });
})();

(function testRangeAndStatusFilters() {
  const candidate = record({ status: { lucky: true }, ivs: { average_percent: 96.4 } });
  assert.equal(Engine.matchesRecord(candidate, {
    league: "great",
    lucky: "yes",
    ranges: { cp: { min: 400, max: 600 }, iv: { min: 96, max: 100 } },
  }), true);
  assert.equal(Engine.matchesRecord(candidate, {
    league: "great",
    lucky: "no",
    ranges: { cp: { min: 400, max: 600 } },
  }), false);
  assert.equal(Engine.matchesRecord(candidate, {
    league: "great",
    ranges: { cp: { min: 600, max: 400 } },
  }), false);
})();

(function testPvPFiltersUseSelectedLeague() {
  const candidate = record();
  assert.equal(Engine.matchesRecord(candidate, {
    league: "great",
    pvpEligibility: "ranked",
    ranges: { pvpPercent: { min: 98, max: null }, pvpDust: { min: null, max: 30000 } },
  }), true);
  assert.equal(Engine.matchesRecord(candidate, {
    league: "ultra",
    pvpEligibility: "ranked",
    ranges: {},
  }), false);
})();

(function testDataQualityFilters() {
  const incomplete = record({ moves: { charged: null } });
  assert.equal(Engine.matchesRecord(incomplete, { league: "great", dataQuality: "missing-any", ranges: {} }), true);
  assert.equal(Engine.matchesRecord(incomplete, { league: "great", dataQuality: "complete", ranges: {} }), false);
})();

(function testDateFilters() {
  const candidate = record();
  assert.equal(Engine.matchesRecord(candidate, {
    league: "great",
    ranges: {},
    dates: { catch: { from: "2026-07-30", to: "2026-08-02" } },
  }), true);
  assert.equal(Engine.matchesRecord(candidate, {
    league: "great",
    ranges: {},
    dates: { catch: { from: "2026-08-02", to: null } },
  }), false);
})();

(function testMultiColumnSort() {
  const records = [
    record({ name: "A", cp: 1000, ivs: { average_percent: 90 } }),
    record({ name: "B", cp: 1000, ivs: { average_percent: 98 } }),
    record({ name: "C", cp: 900, ivs: { average_percent: 100 } }),
  ];
  const sorted = Engine.sortRecordsByCriteria(records, [
    { field: "cp", direction: "desc" },
    { field: "iv", direction: "desc" },
  ], "great");
  assert.deepEqual(sorted.map((item) => item.name), ["B", "A", "C"]);
})();

(function testMissingSortValuesStayLast() {
  const records = [
    record({ name: "Missing", pvp: { great: { rank_percent: null } } }),
    record({ name: "Ranked", pvp: { great: { rank_percent: 80 } } }),
  ];
  const sorted = Engine.sortRecordsByCriteria(records, [{ field: "pvp", direction: "desc" }], "great");
  assert.deepEqual(sorted.map((item) => item.name), ["Ranked", "Missing"]);
})();

(function testSortSerializationAndLegacyLinks() {
  assert.equal(Engine.serializeSorts([
    { field: "name", direction: "asc" },
    { field: "iv", direction: "desc" },
  ]), "name:asc,iv:desc");
  assert.deepEqual(Engine.parseSortParam("iv-desc"), [
    { field: "iv", direction: "desc" },
    { field: "cp", direction: "desc" },
  ]);
})();

console.log("Search, filter, range, date, PvP, and multi-sort tests passed.");
