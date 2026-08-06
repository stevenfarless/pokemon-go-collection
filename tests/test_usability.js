"use strict";

const assert = require("node:assert/strict");
const AppEngine = require("../site/app.js");
const Usability = require("../site/dashboard.js").Usability;

(function testSortDescriptionRecognition() {
  assert.equal(Usability.isDefaultSortDescription("CP ↓"), true);
  assert.equal(Usability.isDefaultSortDescription("  1.   CP   ↓  "), true);
  assert.equal(Usability.isDefaultSortDescription("1. IV % ↓ → 2. CP ↓"), false);
})();

(function testAccessibleFilterRemovalLabel() {
  assert.equal(
    Usability.removeFilterLabel(" IV %: 96–100 "),
    "Remove IV %: 96–100 filter",
  );
})();

(function testSearchTextIsCachedPerRecord() {
  let searchTextBuilds = 0;
  const engine = {
    parseSearchQuery: AppEngine.parseSearchQuery,
    recordSearchText(record) {
      searchTextBuilds += 1;
      return record.searchText;
    },
    matchesRecord() {
      return true;
    },
  };
  const record = { searchText: "pikachu electric lucky" };

  Usability.metrics.searchCacheBuilds = 0;
  Usability.metrics.searchCacheHits = 0;
  Usability.installSearchCache(engine);

  assert.equal(engine.matchesRecord(record, { query: "pikachu" }), true);
  assert.equal(engine.matchesRecord(record, { query: '"electric lucky"' }), true);
  assert.equal(engine.matchesRecord(record, { query: "-shadow pikachu" }), true);
  assert.equal(engine.matchesRecord(record, { query: "charizard" }), false);
  assert.equal(searchTextBuilds, 1);
  assert.equal(Usability.metrics.searchCacheBuilds, 1);
  assert.equal(Usability.metrics.searchCacheHits, 3);
})();

console.log("usability tests passed");
