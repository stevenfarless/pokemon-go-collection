"use strict";

const assert = require("node:assert/strict");
const Tools = require("../site/final-tools.js");

function record(id, overrides = {}) {
  return {
    identity: { record_id: id }, pokemon_number: 25, name: "Pikachu", form: "Normal", gender: "Male", cp: 500,
    ivs: { average_percent: 80, attack: 10, defense: 10, stamina: 10, is_hundo: false, is_nundo: false },
    level: { minimum: 20, maximum: 20 }, moves: { fast: "Thunder Shock", charged: "Thunder Punch", charged_second: null },
    status: { shadow_purified: "normal", lucky: false, favorite: false },
    dates: { scan: "2026-08-10", original_scan: "2026-08-10", catch: "2026-08-10" },
    pvp: { great: { rank_percent: 90, dust_cost: 10000, candy_cost: 10 }, ultra: {}, little: {} },
    ...overrides,
  };
}

{
  const a = record("a", { ivs: { average_percent: 100, attack: 15, defense: 15, stamina: 15, is_hundo: true, is_nundo: false } });
  const b = record("b", { cp: 700, pvp: { great: { rank_percent: 99, dust_cost: 5000, candy_cost: 5 }, ultra: {}, little: {} } });
  const groups = Tools.duplicateReview([a, b], "2026-08-14T00:00:00Z");
  assert.equal(groups.length, 1);
  assert.equal(groups[0].automatic_transfer_safe, false);
  assert.ok(groups[0].records.find((item) => item.record_id === "a").protection_reasons.includes("hundo"));
  assert.ok(groups[0].records.find((item) => item.record_id === "b").protection_reasons.includes("strong_pvp_candidate"));
  assert.ok(groups[0].records.every((item) => item.action === "review_only"));
}

{
  const normal = record("normal");
  const shadow = record("shadow", { status: { shadow_purified: "shadow", lucky: false, favorite: false } });
  assert.equal(Tools.duplicateReview([normal, shadow], "2026-08-14").length, 0, "supported status boundaries must not merge");
}

{
  const a = record("a");
  const b = record("b");
  let payload = Tools.blankAnnotationPayload();
  payload = Tools.setAnnotation(payload, a, ["Keep", "Trade"], "favorite mouse", "2026-08-14T00:00:00Z");
  assert.deepEqual(payload.records.a.labels, ["Keep", "Trade"]);
  assert.equal(payload.records.a.note, "favorite mouse");
  const restored = Tools.annotationFromBackup(JSON.parse(Tools.annotationBackup(payload)), [a, b]);
  assert.equal(restored.records.a.note, "favorite mouse");
}

{
  const legacy = { version: 1, annotations: [{ labels: ["Keep"], note: "legacy", compatibility: { pokemon_number: 25, name: "Pikachu" } }] };
  const ambiguous = Tools.migrateAnnotations(legacy, [record("a"), record("b")]);
  assert.equal(Object.keys(ambiguous.records).length, 0);
  assert.equal(ambiguous.unresolved[0].state, "ambiguous");
  assert.deepEqual(ambiguous.unresolved[0].candidate_record_ids.sort(), ["a", "b"]);
}

{
  const legacy = { version: 1, annotations: [{ record_id: "missing", labels: ["Rescan"], note: "gone", compatibility: { pokemon_number: 999, name: "Missingno" } }] };
  const orphan = Tools.migrateAnnotations(legacy, [record("a")]);
  assert.equal(orphan.unresolved[0].state, "orphaned");
}

{
  const snapshot = {
    data_category: "events", provider: "Official fixture", source_reference: "fixture", classification: "Official",
    dataset_timestamp: "2026-08-14T00:00:00Z", freshness: { state: "fresh" },
    facts: [{ event_id: "test", title: "Test Event", starts_at: "2026-08-14T00:00:00Z", ends_at: "2026-08-15T00:00:00Z", featured_dex: [25, 150], before: ["Prepare storage"], during: ["Catch featured Pokémon"], exclusive_windows: [{ ends_at: "2026-08-15T01:00:00Z" }] }],
  };
  const plan = Tools.eventPlan(snapshot, [record("a")], { datasetVersion: "fixture" }, new Date("2026-08-14T12:00:00Z"));
  assert.equal(plan.status, "available");
  assert.equal(plan.owned_featured.length, 1);
  assert.deepEqual(plan.missing_featured_dex, [150]);
  assert.equal(plan.source.classification, "Official");
  assert.ok(plan.sections.before.includes("Prepare storage"));
  assert.equal(plan.search.text, "Pikachu");
}

{
  const stale = { data_category: "events", freshness: { state: "stale" }, facts: [{ title: "Old" }] };
  const plan = Tools.eventPlan(stale, [], null, new Date("2026-08-14T12:00:00Z"));
  assert.equal(plan.status, "unavailable");
  assert.match(plan.reason, /stale/i);
}

console.log("final tools tests passed");
