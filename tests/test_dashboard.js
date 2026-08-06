"use strict";

const assert = require("node:assert/strict");
const AppEngine = require("../site/app.js");
const Dashboard = require("../site/dashboard.js");

const Search = Dashboard.QualifiedSearch;
const Columns = Dashboard.Columns;

(function testMixedQualifiedAndPlainParsing() {
  const parsed = Search.parseQualifiedQuery('name:pikachu move:"wild charge" cp:1200-1500 -status:shadow lucky -unknown:value');
  assert.deepEqual(parsed.qualified, [
    { field: "name", value: "pikachu", negated: false },
    { field: "move", value: "wild charge", negated: false },
    { field: "cp", value: "1200-1500", negated: false },
    { field: "status", value: "shadow", negated: true },
  ]);
  assert.equal(parsed.plainQuery, "lucky -unknown:value");
  assert.deepEqual(parsed.invalid, []);
})();

(function testMalformedKnownFieldsFallBackToPlainText() {
  const parsed = Search.parseQualifiedQuery("cp:abc iv:101 level:60.5-40 rank:zero");
  assert.equal(parsed.qualified.length, 0);
  assert.equal(parsed.plainQuery, "cp:abc iv:101 level:60.5-40 rank:zero");
  assert.deepEqual(parsed.invalid, ["cp:abc", "iv:101", "level:60.5-40", "rank:zero"]);
})();

(function testNumericConstraints() {
  assert.deepEqual(Search.parseNumericConstraint("1500", { minimum: 0, integer: true }), { minimum: 1500, maximum: 1500 });
  assert.deepEqual(Search.parseNumericConstraint("40+", { minimum: 0, maximum: 60 }), { minimum: 40, maximum: null });
  assert.deepEqual(Search.parseNumericConstraint("96-100", { minimum: 0, maximum: 100 }), { minimum: 96, maximum: 100 });
  assert.equal(Search.parseNumericConstraint("100-96", { minimum: 0, maximum: 100 }), null);
})();

const record = {
  name: "Pikachu",
  form: "Rock Star",
  pokemon_number: 25,
  cp: 1498,
  ivs: { average_percent: 98, is_hundo: false, is_nundo: false },
  level: { minimum: 40 },
  moves: { fast: "Thunder Shock", charged: "Wild Charge", charged_second: null },
  status: { shadow_purified: "normal", lucky: true, favorite: false, marked_for_pvp: true },
  pvp: {
    great: { rank_percent: 99.2, rank_number: 32 },
    ultra: { rank_percent: null, rank_number: null },
    little: { rank_percent: 95, rank_number: 205 },
  },
};

(function testQualifiedMatching() {
  assert.equal(Search.matchesQualifiedTerm(record, { field: "name", value: "pika", negated: false }, "great"), true);
  assert.equal(Search.matchesQualifiedTerm(record, { field: "form", value: "rock", negated: false }, "great"), true);
  assert.equal(Search.matchesQualifiedTerm(record, { field: "move", value: "wild charge", negated: false }, "great"), true);
  assert.equal(Search.matchesQualifiedTerm(record, { field: "cp", value: "1400-1500", negated: false }, "great"), true);
  assert.equal(Search.matchesQualifiedTerm(record, { field: "iv", value: "98+", negated: false }, "great"), true);
  assert.equal(Search.matchesQualifiedTerm(record, { field: "level", value: "40", negated: false }, "great"), true);
  assert.equal(Search.matchesQualifiedTerm(record, { field: "status", value: "lucky", negated: false }, "great"), true);
  assert.equal(Search.matchesQualifiedTerm(record, { field: "status", value: "shadow", negated: true }, "great"), true);
  assert.equal(Search.matchesQualifiedTerm(record, { field: "pvp", value: "great", negated: false }, "great"), true);
  assert.equal(Search.matchesQualifiedTerm(record, { field: "pvp", value: "ultra", negated: false }, "great"), false);
  assert.equal(Search.matchesQualifiedTerm(record, { field: "rank", value: "1-50", negated: false }, "great"), true);
  assert.equal(Search.matchesQualifiedTerm(record, { field: "rank", value: "unranked", negated: false }, "ultra"), true);
})();

(function testQualifiedSearchWrapsExistingEngine() {
  const engine = {
    matchesRecord(_record, filters) { return filters.query === "plain"; },
  };
  Search.installQualifiedSearch(engine);
  assert.equal(engine.matchesRecord(record, { query: "name:pikachu plain", league: "great" }), true);
  assert.equal(engine.matchesRecord(record, { query: "name:charizard plain", league: "great" }), false);
})();

(function testColumnPreferenceNormalizationAndStorage() {
  assert.deepEqual(Columns.normalizeColumnPreference(["pvp", "moves", "unknown"]), ["pokemon", "moves", "pvp"]);
  assert.deepEqual(Columns.normalizeColumnPreference([]), [...Columns.DEFAULT_COLUMNS]);
  const values = new Map();
  const storage = {
    getItem(key) { return values.get(key) ?? null; },
    setItem(key, value) { values.set(key, value); },
  };
  assert.equal(Columns.saveColumnPreference(storage, ["pokemon", "cp", "moves"]), true);
  assert.deepEqual(Columns.loadColumnPreference(storage), ["pokemon", "cp", "moves"]);
  values.set(Columns.COLUMN_STORAGE_KEY, "not-json");
  assert.deepEqual(Columns.loadColumnPreference(storage), [...Columns.DEFAULT_COLUMNS]);
})();

(function testExistingPlainSearchRemainsCompatible() {
  const parsed = Search.parseQualifiedQuery('pikachu "wild charge" -shadow');
  assert.equal(parsed.qualified.length, 0);
  assert.deepEqual(AppEngine.parseSearchQuery(parsed.plainQuery), {
    positive: ["pikachu", "wild charge"],
    negative: ["shadow"],
  });
})();

console.log("dashboard feature tests passed");
