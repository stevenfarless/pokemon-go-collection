"use strict";

const assert = require("node:assert/strict");
const Dashboard = require("../site/dashboard.js");
const Search = require("../site/advanced-search.js");
const LocalData = require("../site/local-data.js");
const Companion = require("../site/companion.js");

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
function fakeDocument(values) {
  return { getElementById(id) { return { value: values[id] ?? "" }; } };
}
function memoryStorage(initial = {}, failKey = null) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) {
      if (key === failKey) throw new Error("simulated storage failure");
      values.set(key, String(value));
    },
    removeItem(key) { values.delete(key); },
    snapshot() { return Object.fromEntries(values.entries()); },
  };
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

(function pokemonGoSearchGenerationIsDeterministicAndBooleanSafe() {
  const statuses = ["any", "normal", "shadow", "purified"];
  const tri = ["any", "yes", "no"];
  const speciesNames = ["Pikachu", "Mr. Mime", "Farfetch'd", "Type: Null", "Nidoran♀"];
  for (let index = 0; index < 300; index += 1) {
    const values = {
      "species-filter": speciesNames[Math.floor(random() * speciesNames.length)],
      "cp-min": random() < 0.5 ? String(Math.floor(random() * 2000)) : "",
      "cp-max": random() < 0.5 ? String(2000 + Math.floor(random() * 3000)) : "",
      "status-filter": statuses[Math.floor(random() * statuses.length)],
      "lucky-filter": tri[Math.floor(random() * tri.length)],
      "favorite-filter": tri[Math.floor(random() * tri.length)],
      "hundo-filter": tri[Math.floor(random() * tri.length)],
      "nundo-filter": tri[Math.floor(random() * tri.length)],
      "fast-move-filter": random() < 0.3 ? "Thunder Shock" : "",
      "charged-move-filter": random() < 0.3 ? "Shadow Ball" : "",
      "gender-filter": "any",
      "pvp-eligibility-filter": "any",
      "data-quality-filter": "any",
      "second-move-filter": "any",
    };
    const first = Companion.generateGoSearch(fakeDocument(values));
    const second = Companion.generateGoSearch(fakeDocument(values));
    assert.deepEqual(first, second);
    assert.equal(typeof first.text, "string");
    assert.ok(!first.text.includes("&&"));
    assert.ok(!first.text.startsWith("&"));
    assert.ok(!first.text.endsWith("&"));
    assert.ok(Array.isArray(first.approximate));
    assert.ok(Array.isArray(first.omitted));
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

(function unifiedRestoreIsAtomicWhenAnyNamespaceWriteFails() {
  for (let index = 0; index < 80; index += 1) {
    const originalViews = JSON.stringify({ version: 1, views: [{ name: `Old ${index}`, query: "" }] });
    const storage = memoryStorage({ [LocalData.STORAGE_KEYS.saved_views]: originalViews }, LocalData.STORAGE_KEYS.goals);
    const backup = {
      product: LocalData.UNIFIED_BACKUP_PRODUCT,
      backup_version: 1,
      namespaces: {
        saved_views: {
          storage_key: LocalData.STORAGE_KEYS.saved_views,
          schema_version: 1,
          present: true,
          data: { version: 1, views: [{ name: `New ${index}`, query: "" }] },
        },
        goals: {
          storage_key: LocalData.STORAGE_KEYS.goals,
          schema_version: 1,
          present: true,
          data: { version: 1, goals: [{ id: `g${index}`, kind: "hundo" }] },
        },
      },
    };
    assert.throws(() => LocalData.restoreUnifiedBackup(storage, backup, []), /Restore failed/);
    assert.equal(storage.getItem(LocalData.STORAGE_KEYS.saved_views), originalViews);
  }
})();

console.log("deterministic JavaScript fuzz properties passed");
