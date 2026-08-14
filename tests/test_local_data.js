"use strict";

const assert = require("assert");
const Local = require("../site/local-data.js");

function record(id, dex = 25, name = "Pikachu", original = "2026-08-01") {
  return {
    identity: { record_id: id },
    pokemon_number: dex,
    name,
    form: "",
    gender: "♂",
    dates: { original_scan: original, catch: "2026-08-01" },
    cp: 100,
    ivs: { average_percent: 90 },
  };
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

{
  const a = record("pgc_aaaaaaaaaaaaaaaaaaaa");
  const b = record("pgc_bbbbbbbbbbbbbbbbbbbb");
  let payload = Local.blankEnrichmentPayload();
  payload = Local.setEnrichment(payload, a, { shiny: "yes" }, "2026-08-14T10:00:00Z");
  payload = Local.setEnrichment(payload, b, { shiny: "no" }, "2026-08-14T10:01:00Z");
  assert.equal(payload.records[a.identity.record_id].shiny, "yes");
  assert.equal(payload.records[b.identity.record_id].shiny, "no");
  assert.equal(payload.records[a.identity.record_id].provenance.shiny.source, "user-confirmed");
  assert.deepEqual(Local.filterRecordsByEnrichment([a, b, record("pgc_cccccccccccccccccccc")], payload, "shiny", "no").map((item) => item.identity.record_id), [b.identity.record_id]);
  assert.equal(Local.filterRecordsByEnrichment([a, b, record("pgc_cccccccccccccccccccc")], payload, "shiny", "unknown").length, 1);
}

{
  const current = record("pgc_current0000000000000");
  const old = {
    version: 1,
    records: {
      old: { shiny: "yes", compatibility: Local.compatibility(current) },
    },
    unresolved: [],
  };
  const migrated = Local.migrateEnrichment(old, [current]);
  assert.equal(migrated.records[current.identity.record_id].shiny, "yes");
  assert.equal(migrated.unresolved.length, 0);

  const twin = { ...current, identity: { record_id: "pgc_twin000000000000000" } };
  const ambiguous = Local.migrateEnrichment(old, [current, twin]);
  assert.equal(Object.keys(ambiguous.records).length, 0);
  assert.equal(ambiguous.unresolved[0].reason, "ambiguous-compatibility-match");
  assert.equal(ambiguous.unresolved[0].candidate_record_ids.length, 2);
}

{
  const a = record("pgc_aaaaaaaaaaaaaaaaaaaa");
  let payload = Local.blankEnrichmentPayload();
  payload = Local.setEnrichment(payload, a, { shiny: "yes", costume: "yes", reserved_trade: "yes", legacy_move_review: "yes" });
  const reasons = Local.protectionReasons(payload.records[a.identity.record_id]);
  assert(reasons.includes("user-confirmed shiny"));
  assert(reasons.includes("reserved for trade"));
  const groups = Local.augmentDuplicateGroups([{ records: [{ record_id: a.identity.record_id }] }], payload);
  assert.equal(groups[0].automatic_transfer_safe, false);
  assert(groups[0].records[0].local_protection_reasons.length >= 3);
}

{
  const a = record("pgc_aaaaaaaaaaaaaaaaaaaa");
  let payload = Local.blankEnrichmentPayload();
  payload = Local.setEnrichment(payload, a, { gigantamax: "yes", origin_note: "verified manually" });
  const backup = Local.enrichmentBackup(payload);
  const restored = Local.enrichmentFromBackup(backup, [a]);
  assert.equal(restored.records[a.identity.record_id].gigantamax, "yes");
  assert.equal(restored.records[a.identity.record_id].origin_note, "verified manually");
}

{
  const initial = {};
  initial[Local.STORAGE_KEYS.saved_views] = JSON.stringify({ version: 1, views: [{ name: "PvP", query: "?q=pvp", columns: ["pokemon"] }] });
  initial[Local.STORAGE_KEYS.goals] = JSON.stringify({ version: 1, goals: [{ id: "g1", kind: "hundo", target: 1, threshold: 98, name: "Hundos" }] });
  initial[Local.STORAGE_KEYS.goal_exclusions] = JSON.stringify({ version: 1, by_goal: { g1: ["pikachu"] } });
  initial[Local.STORAGE_KEYS.annotations] = JSON.stringify({ version: 2, records: {}, unresolved: [] });
  initial[Local.STORAGE_KEYS.enrichment] = JSON.stringify({ version: 1, records: {}, unresolved: [] });
  initial[Local.STORAGE_KEYS.columns] = JSON.stringify(["pokemon", "cp"]);
  initial[Local.STORAGE_KEYS.planner_budget] = JSON.stringify({ stardust: 1000 });
  const source = memoryStorage(initial);
  const backup = Local.buildUnifiedBackup(source);
  const target = memoryStorage({});
  const validated = Local.validateUnifiedBackup(backup, target, []);
  assert(validated.preview.added.includes("saved_views"));
  Local.restoreUnifiedBackup(target, backup, []);
  assert.deepEqual(JSON.parse(target.getItem(Local.STORAGE_KEYS.columns)), ["pokemon", "cp"]);
}

{
  const bad = {
    product: Local.UNIFIED_BACKUP_PRODUCT,
    backup_version: 1,
    namespaces: {
      saved_views: {
        storage_key: Local.STORAGE_KEYS.saved_views,
        schema_version: 1,
        present: true,
        data: { version: 1, views: [{ name: "Same", query: "" }, { name: "same", query: "" }] },
      },
    },
  };
  assert.throws(() => Local.validateUnifiedBackup(bad, memoryStorage(), []), /duplicate name/i);
  assert.throws(() => Local.validateUnifiedBackup({ product: Local.UNIFIED_BACKUP_PRODUCT, backup_version: 99, namespaces: {} }, memoryStorage(), []), /newer/);
}

{
  const storage = memoryStorage({ [Local.STORAGE_KEYS.saved_views]: JSON.stringify({ version: 1, views: [] }) }, Local.STORAGE_KEYS.goals);
  const before = storage.getItem(Local.STORAGE_KEYS.saved_views);
  const backup = {
    product: Local.UNIFIED_BACKUP_PRODUCT,
    backup_version: 1,
    namespaces: {
      saved_views: { storage_key: Local.STORAGE_KEYS.saved_views, schema_version: 1, present: true, data: { version: 1, views: [{ name: "New", query: "" }] } },
      goals: { storage_key: Local.STORAGE_KEYS.goals, schema_version: 1, present: true, data: { version: 1, goals: [{ id: "g1", kind: "hundo" }] } },
    },
  };
  assert.throws(() => Local.restoreUnifiedBackup(storage, backup, []), /Restore failed/);
  assert.equal(storage.getItem(Local.STORAGE_KEYS.saved_views), before);
}

{
  const legacy = {
    product: Local.UNIFIED_BACKUP_PRODUCT,
    backup_version: 0,
    stores: {
      [Local.STORAGE_KEYS.columns]: ["pokemon", "iv"],
    },
  };
  const migrated = Local.migrateBackupEnvelope(legacy);
  assert.equal(migrated.backup_version, 1);
  assert.equal(migrated.namespaces.columns.present, true);
}

console.log("local enrichment and unified backup tests passed");
