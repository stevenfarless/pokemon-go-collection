"use strict";

const assert = require("node:assert/strict");
const Hardening = require("../site/hardening.js");

const engine = {
  SORT_FIELDS: {
    cp: {}, name: {}, iv: {}, scan: {},
  },
  parseSortParam(value) {
    const legacy = {
      "iv-desc": [{ field: "iv", direction: "desc" }, { field: "cp", direction: "desc" }],
    };
    return legacy[value] || [{ field: "cp", direction: "desc" }];
  },
  serializeSorts(sorts) {
    return sorts.map(({ field, direction }) => `${field}:${direction}`).join(",");
  },
};

(function testMalformedUrlStateIsRemoved() {
  const sanitized = Hardening.sanitizeSearchParams(
    "?page=abc&size=0&league=master&status=banana&sort=nope:sideways&cpmin=x&catchfrom=2026-99-99&unknown=value",
    engine,
  );
  assert.equal(sanitized, "");
})();

(function testValidUrlStateIsCanonicalized() {
  const sanitized = Hardening.sanitizeSearchParams(
    "?page=2&size=100&league=ultra&sort=name:asc,iv:desc&cpmin=10&cpmax=100&catchfrom=2026-08-01&q=%20mewtwo%20",
    engine,
  );
  const params = new URLSearchParams(sanitized);
  assert.equal(params.get("page"), "2");
  assert.equal(params.get("size"), "100");
  assert.equal(params.get("league"), "ultra");
  assert.equal(params.get("sort"), "name:asc,iv:desc");
  assert.equal(params.get("cpmin"), "10");
  assert.equal(params.get("cpmax"), "100");
  assert.equal(params.get("catchfrom"), "2026-08-01");
  assert.equal(params.get("q"), "mewtwo");
})();

(function testInvalidPairsAreRemoved() {
  const params = new URLSearchParams(Hardening.sanitizeSearchParams(
    "?ivmin=99&ivmax=50&catchfrom=2026-08-05&catchto=2026-08-01",
    engine,
  ));
  assert.equal(params.has("ivmin"), false);
  assert.equal(params.has("ivmax"), false);
  assert.equal(params.has("catchfrom"), false);
  assert.equal(params.has("catchto"), false);
})();

(function testLegacyValuesRemainCompatible() {
  const params = new URLSearchParams(Hardening.sanitizeSearchParams(
    "?miniv=96&sort=iv-desc&status=all&league=all",
    engine,
  ));
  assert.equal(params.get("ivmin"), "96");
  assert.equal(params.get("sort"), "iv:desc,cp:desc");
  assert.equal(params.has("status"), false);
  assert.equal(params.has("league"), false);
})();

function record(overrides = {}) {
  const base = {
    ivs: { average_percent: 90, attack: 10, defense: 10, stamina: 10 },
    level: { minimum: 20, maximum: 20 },
    moves: { fast: "Vine Whip", charged: "Power Whip" },
    pvp: { great: { rank_percent: 98 }, ultra: { rank_percent: null } },
  };
  return {
    ...base,
    ...overrides,
    ivs: { ...base.ivs, ...(overrides.ivs || {}) },
    level: { ...base.level, ...(overrides.level || {}) },
    moves: { ...base.moves, ...(overrides.moves || {}) },
    pvp: {
      great: { ...base.pvp.great, ...(overrides.pvp?.great || {}) },
      ultra: { ...base.pvp.ultra, ...(overrides.pvp?.ultra || {}) },
    },
  };
}

(function testCompletenessRequiresEveryCoreScanField() {
  assert.deepEqual(Hardening.missingScanReasons(record()), []);
  assert.deepEqual(Hardening.missingScanReasons(record({ ivs: { attack: null } })), ["attack-iv"]);
  assert.deepEqual(Hardening.missingScanReasons(record({ ivs: { average_percent: null } })), ["iv-average"]);
  assert.deepEqual(Hardening.missingScanReasons(record({ level: { maximum: null } })), ["level-maximum"]);
  assert.deepEqual(Hardening.missingScanReasons(record({ moves: { charged: null } })), ["charged-move"]);
})();

(function testQualityFiltersUseDocumentedPolicy() {
  const incomplete = record({ ivs: { defense: null } });
  assert.equal(Hardening.matchesDataQuality(incomplete, "missing-any", "great"), true);
  assert.equal(Hardening.matchesDataQuality(incomplete, "complete", "great"), false);
  assert.equal(Hardening.matchesDataQuality(incomplete, "missing-ivs", "great"), true);
  assert.equal(Hardening.matchesDataQuality(record(), "missing-pvp", "great"), false);
  assert.equal(Hardening.matchesDataQuality(record(), "missing-pvp", "ultra"), true);
})();

(function testEngineOverridePreservesOtherFilters() {
  const stub = {
    matchesRecord(candidate, filters) {
      return filters.allowed !== false && filters.dataQuality === "any";
    },
  };
  Hardening.installEngineOverrides(stub);
  assert.equal(stub.matchesRecord(record(), { allowed: true, dataQuality: "complete", league: "great" }), true);
  assert.equal(stub.matchesRecord(record({ moves: { fast: null } }), { allowed: true, dataQuality: "complete", league: "great" }), false);
  assert.equal(stub.matchesRecord(record(), { allowed: false, dataQuality: "complete", league: "great" }), false);
})();

console.log("URL-state and scan-quality hardening tests passed.");
