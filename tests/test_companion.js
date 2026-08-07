"use strict";

const assert = require("node:assert/strict");
const Companion = require("../site/companion.js");

class MemoryStorage {
  constructor() { this.values = new Map(); }
  getItem(key) { return this.values.has(key) ? this.values.get(key) : null; }
  setItem(key, value) { this.values.set(key, String(value)); }
}

function fakeDocument(values) {
  return {
    getElementById(id) {
      return { value: values[id] ?? "" };
    },
  };
}

{
  const storage = new MemoryStorage();
  const payload = { version: 1, views: [{ name: "Great PvP", query: "?league=great", columns: ["pokemon", "pvp"] }] };
  assert.equal(Companion.saveSavedViews(storage, payload), true);
  assert.deepEqual(Companion.loadSavedViews(storage), payload);
  assert.equal(Companion.normalizedSavedViews({ version: 99, views: [] }), null);
  assert.equal(Companion.uniqueViewName("Great PvP", payload.views), "Great PvP (2)");
}

{
  const result = Companion.generateGoSearch(fakeDocument({
    "species-filter": "Pikachu",
    "cp-min": "1000",
    "cp-max": "1500",
    "status-filter": "shadow",
    "lucky-filter": "no",
    "favorite-filter": "any",
    "hundo-filter": "yes",
    "nundo-filter": "any",
    "fast-move-filter": "Thunder Shock",
    "charged-move-filter": "",
    "gender-filter": "any",
    "pvp-eligibility-filter": "any",
    "data-quality-filter": "any",
    "second-move-filter": "any",
  }));
  assert.equal(result.text, "Pikachu&cp1000-1500&shadow&!lucky&4*&@1Thunder Shock");
  assert.equal(result.approximate.length, 0);
  assert.equal(result.verified, "2026-08-07");
}

{
  const result = Companion.generateGoSearch(fakeDocument({
    "charged-move-filter": "Shadow Ball",
    "iv-min": "98",
    "gender-filter": "any",
    "pvp-eligibility-filter": "any",
    "data-quality-filter": "any",
    "second-move-filter": "any",
  }));
  assert.equal(result.approximate[0].term, "@Shadow Ball");
  assert.ok(result.omitted.some((item) => item.label === "IV percentage/total range"));
}

{
  const record = {
    pokemon_number: 25,
    name: "Pikachu",
    form: "",
    gender: "Male",
    dates: { catch: "2026-08-01", original_scan: "2026-08-01", scan: "2026-08-02" },
  };
  assert.equal(Companion.stableRecordId(record), Companion.stableRecordId(record));
}

console.log("companion tests passed");
