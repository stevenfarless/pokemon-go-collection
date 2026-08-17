"use strict";

const assert = require("node:assert/strict");
const Dashboard = require("../site/dashboard.js");
const Search = require("../site/advanced-search.js");
const LocalData = require("../site/local-data.js");

let state = 0x504f4b45;
function random() {
  state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
  return state / 0x100000000;
}
function token(length) {
  const alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:-_ !@#$%^&*()[]{}'\"";
  let output = "";
  for (let index = 0; index < length; index += 1) output += alphabet[Math.floor(random() * alphabet.length)];
  return output;
}

(function searchParserIsDeterministicAndTotal() {
  const base = Dashboard.QualifiedSearch;
  for (let index = 0; index < 500; index += 1) {
    const query = token(Math.floor(random() * 80));
    const first = Search.compileQuery(query, base, new Set(["pikachu", "mewtwo", "mr. mime"]));
    const second = Search.compileQuery(query, base, new Set(["pikachu", "mewtwo", "mr. mime"]));
    assert.deepEqual(first, second);
    assert.ok(Array.isArray(first.baseTerms));
    assert.ok(Array.isArray(first.extendedTerms));
    assert.equal(typeof first.plainQuery, "string");
  }
})();

(function naturalLanguageCompilerIsDeterministicAndBounded() {
  for (let index = 0; index < 300; index += 1) {
    const query = token(Math.floor(random() * 100));
    const first = Search.compileNaturalLanguage(query, new Set(["pikachu", "mewtwo"]));
    const second = Search.compileNaturalLanguage(query, new Set(["pikachu", "mewtwo"]));
    assert.deepEqual(first, second);
    assert.ok(first.terms.length <= 64, `unexpected term explosion for ${JSON.stringify(query)}`);
  }
})();

(function enrichmentSanitizerNeverInventsProtectedYesState() {
  for (let index = 0; index < 400; index += 1) {
    const raw = {};
    for (const field of LocalData.TRI_FIELDS) raw[field] = token(Math.floor(random() * 30));
    const clean = LocalData.sanitizeEnrichment(raw);
    for (const field of LocalData.TRI_FIELDS) {
      assert.ok(LocalData.TRI_STATES.includes(clean[field]));
      if (!LocalData.TRI_STATES.includes(String(raw[field]))) assert.equal(clean[field], "unknown");
    }
  }
})();

(function malformedBackupShapesAreRejectedWithoutPartialState() {
  for (let index = 0; index < 200; index += 1) {
    const malformed = random() < 0.5 ? token(20) : { version: token(5), records: token(15) };
    const migrated = LocalData.migrateEnrichment(malformed, []);
    assert.equal(migrated, null);
  }
})();

console.log("deterministic JavaScript fuzz properties passed");
