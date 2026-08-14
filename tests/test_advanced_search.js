"use strict";

const assert = require("node:assert/strict");
const Dashboard = require("../site/dashboard.js");
const Search = require("../site/advanced-search.js");

const BaseSearch = Dashboard.QualifiedSearch;

(function testNaturalLanguageCompilesIntoExplicitTerms() {
  const compiled = Search.compileNaturalLanguage("shadow dragons under 1500 cp", new Set());
  assert.ok(compiled.terms.includes("status:shadow"));
  assert.ok(compiled.terms.includes("type:dragon"));
  assert.ok(compiled.terms.includes("cp:0-1499"));
  assert.equal(compiled.plain, "");
})();

(function testOrdinaryPhraseRemainsOrdinarySearch() {
  const compiled = Search.compileNaturalLanguage("shadow ball", new Set());
  assert.deepEqual(compiled.terms, []);
  assert.equal(compiled.plain, "shadow ball");
})();

(function testFuzzyTypoMatchingIsBounded() {
  assert.equal(Search.fuzzyTokenMatch("pikchu", ["pikachu"]), true);
  assert.equal(Search.fuzzyTokenMatch("mewto", ["mewtwo"]), true);
  assert.equal(Search.fuzzyTokenMatch("cat", ["garchomp"]), false);
})();

const knowledge = Search.buildKnowledgeIndex({
  dataset_version: "test-1",
  entries: [
    { dex: 25, species_id: "pikachu", display_name: "Pikachu", form_key: "normal", family_id: "pikachu", types: ["electric"], transformation_kind: null },
    { dex: 445, species_id: "garchomp", display_name: "Garchomp", form_key: "normal", family_id: "gible", types: ["dragon", "ground"], transformation_kind: null },
    { dex: 445, species_id: "garchomp_mega", display_name: "Garchomp (Mega)", form_key: "mega", family_id: "gible", types: ["dragon", "ground"], transformation_kind: "mega" },
  ],
});

const garchomp = { pokemon_number: 445, form: null, name: "Garchomp", ivs: { attack: 15, defense: 14, stamina: 13 }, hp: 180 };

(function testKnowledgeBackedExtendedFields() {
  assert.equal(Search.matchesExtendedTerm(garchomp, { field: "type", value: "dragon", negated: false }, BaseSearch, knowledge), true);
  assert.equal(Search.matchesExtendedTerm(garchomp, { field: "family", value: "gible", negated: false }, BaseSearch, knowledge), true);
  assert.equal(Search.matchesExtendedTerm(garchomp, { field: "mega", value: "yes", negated: false }, BaseSearch, knowledge), true);
  assert.equal(Search.matchesExtendedTerm(garchomp, { field: "attack", value: "15", negated: false }, BaseSearch, knowledge), true);
  assert.equal(Search.matchesExtendedTerm(garchomp, { field: "stamina", value: "14+", negated: false }, BaseSearch, knowledge), false);
})();

(function testExtendedAndExistingGrammarRemainSeparated() {
  const compiled = Search.compileQuery("type:dragon name:garchomp cp:1000+", BaseSearch, knowledge.speciesNames);
  assert.deepEqual(compiled.extendedTerms, [{ field: "type", value: "dragon", negated: false }]);
  assert.deepEqual(compiled.baseTerms, [
    { field: "name", value: "garchomp", negated: false },
    { field: "cp", value: "1000+", negated: false },
  ]);
  assert.equal(compiled.plainQuery, "");
  assert.equal(compiled.requiresKnowledge, true);
})();

(function testUnsupportedSourceConceptsAreExplicit() {
  const compiled = Search.compileNaturalLanguage("shiny dragons under 1500 cp", new Set());
  assert.ok(compiled.unsupported.includes("shiny"));
  assert.ok(compiled.terms.includes("type:dragon"));
})();

console.log("advanced search tests passed");
