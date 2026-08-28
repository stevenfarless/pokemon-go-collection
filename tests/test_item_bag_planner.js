"use strict";

const assert = require("assert");
const Bag = require("../site/item-bag-planner.js");

{
  const state = Bag.blankBag();
  state.capacity = 1000;
  state.profile = "balanced";
  state.counts.poke_ball = 200;
  state.counts.great_ball = 200;
  state.counts.ultra_ball = 250;
  state.reserves.ultra_ball = 220;
  state.counts.golden_razz = 500;
  state.counts.nanab_berry = 100;
  state.protected.nanab_berry = true;
  const result = Bag.evaluateBag(state, 50, new Date("2026-08-28T12:00:00Z"));
  assert.equal(result.missing_counts_are_unknown, true);
  assert(result.unknown_categories > 0);
  assert.equal(result.estimated_free_space, null);
  assert(!result.cleanup.some((item) => item.id === "golden_razz"));
  assert(!result.cleanup.some((item) => item.id === "nanab_berry"));
  const ultra = result.rows.find((item) => item.id === "ultra_ball");
  assert.equal(ultra.floor, 220);
  const ultraCleanup = result.cleanup.find((item) => item.id === "ultra_ball");
  assert(!ultraCleanup || ultraCleanup.amount <= 30);
  assert(result.slots_identified <= 50);
}

{
  const category = Bag.CATEGORIES.find((item) => item.id === "poke_ball");
  const balanced = Bag.targetFor(category, "balanced");
  const catching = Bag.targetFor(category, "catching");
  const rural = Bag.targetFor(category, "rural");
  assert(catching.min > balanced.min);
  assert(rural.max > balanced.max);
}

{
  const calendar = { events: [
    { id: "fresh", title: "Community Day", starts_at: "2026-08-28T10:00:00Z", ends_at: "2026-08-28T20:00:00Z", actionable_at_build: true, source: { freshness: { state: "fresh" } }, featured_species: ["Testmon"] },
    { id: "stale", title: "Raid Day", starts_at: "2026-08-28T10:00:00Z", ends_at: "2026-08-28T20:00:00Z", actionable_at_build: true, source: { freshness: { state: "stale" } }, raid_targets: [1] },
    { id: "blocked", title: "Catch event", starts_at: "2026-08-28T10:00:00Z", ends_at: "2026-08-28T20:00:00Z", actionable_at_build: false, source: { freshness: { state: "fresh" } } },
  ] };
  const adjustments = Bag.eventPreparation(calendar, new Date("2026-08-28T12:00:00Z"));
  assert.equal(adjustments.length, 1);
  assert.equal(adjustments[0].event_id, "fresh");
}

{
  const values = new Map();
  const storage = {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
  };
  const api = {
    buildUnifiedBackup() { return { product: "pokemon-go-collection-local-data", backup_version: 1, namespaces: {} }; },
    validateUnifiedBackup(raw) { return { envelope: raw, preview: { added: [], replaced: [], absent: [], ignored: ["item_bag"] } }; },
    restoreUnifiedBackup() { values.set("base-restored", "yes"); return {}; },
  };
  Bag.wrapUnifiedLocalData(api);
  const state = Bag.blankBag();
  state.capacity = 1200;
  state.counts.ultra_ball = 321;
  storage.setItem(Bag.ITEM_BAG_KEY, JSON.stringify(state));
  const backup = api.buildUnifiedBackup(storage);
  assert.equal(backup.namespaces.item_bag.present, true);
  assert.equal(backup.namespaces.item_bag.data.counts.ultra_ball, 321);
  const preview = api.validateUnifiedBackup(backup, storage, []).preview;
  assert(preview.replaced.includes("item_bag"));
  values.delete(Bag.ITEM_BAG_KEY);
  api.restoreUnifiedBackup(storage, backup, []);
  assert.equal(JSON.parse(storage.getItem(Bag.ITEM_BAG_KEY)).capacity, 1200);
}

console.log("item bag planner tests passed");
