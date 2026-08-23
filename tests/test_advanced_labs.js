"use strict";

const assert = require("node:assert/strict");
const Labs = require("../site/advanced-labs.js");

function fakeStorage(seed = {}) {
  const values = new Map(Object.entries(seed).map(([key, value]) => [key, typeof value === "string" ? value : JSON.stringify(value)]));
  return {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
    values,
  };
}

{
  const mega = Labs.defaultState("mega_state");
  const max = Labs.defaultState("max_state");
  const hyper = Labs.defaultState("hyper_training");
  const buddy = Labs.defaultState("buddy_queue");
  const raids = Labs.defaultState("raid_assumptions");
  assert.equal(mega.version, 1);
  assert.deepEqual(mega.records, {});
  assert.equal(max.max_particles, null);
  assert.equal(hyper.bottle_caps.silver, null);
  assert.deepEqual(buddy.projects, {});
  assert.deepEqual(raids.by_boss, {});
}

{
  const invalid = Labs.defaultState("mega_state");
  invalid.records.a = { first_mega_unlocked: "yes", mega_level: "max", mega_energy: -1 };
  assert.throws(() => Labs.validateMegaState(invalid), /Mega Energy/);
}

{
  const invalid = Labs.defaultState("max_state");
  invalid.records.a = { dynamax: "yes", gigantamax: "no", max_attack_level: 4 };
  assert.throws(() => Labs.validateMaxState(invalid), /0-3/);
}

{
  assert.deepEqual(
    Labs.maxAttackType({ dynamax: "yes", gigantamax: "no", fast_move_type: "grass" }),
    { state: "dynamax-fast-type", type: "grass" },
  );
  assert.deepEqual(
    Labs.maxAttackType({ dynamax: "yes", gigantamax: "yes", fast_move_type: "grass", gmax_attack_type: "water" }),
    { state: "gmax-explicit", type: "water" },
  );
}

{
  const candidates = [
    { record_id: "a", objectives: [{ kind: "evolution", default_priority: 60 }] },
    { record_id: "b", objectives: [{ kind: "best-buddy-user-goal", default_priority: 20 }] },
    { record_id: "c", objectives: [{ kind: "build-candy", default_priority: 45 }] },
  ];
  const local = { projects: {
    a: { record_id: "a", priority: 50 },
    b: { record_id: "b", priority: 50, pinned: true },
    c: { record_id: "c", priority: 100, skipped: true },
  } };
  const hyper = { records: { a: { active: "yes", training_deadline: "2026-08-23T12:00:00Z" } } };
  const ranked = Labs.rankBuddyProjects(candidates, local, hyper, { records: {} }, Date.parse("2026-08-23T11:00:00Z"));
  assert.equal(ranked.length, 2);
  assert.equal(ranked[0].candidate.record_id, "b");
  assert.ok(ranked.find((item) => item.candidate.record_id === "a").reasons.some((reason) => reason.includes("Hyper Training")));
  assert.ok(!ranked.some((item) => item.candidate.record_id === "c"));
}

{
  const stale = Labs.simulateRaidModel({ freshness: "stale", model_version: "1.0.0", owned_records: [] }, {
    hp: 10000, defense: 180, timer_seconds: 300, group_size: 1,
    weather_multiplier: 1, friendship_multiplier: 1, party_power_multiplier: 1, mega_multiplier: 1, survival_multiplier: 1,
  });
  assert.equal(stale.state, "blocked");
  assert.match(stale.reason, /not fresh/);
}

{
  const data = {
    freshness: "fresh",
    model_version: "1.0.0",
    owned_records: [
      { record_id: "owned-a", name: "A", cp: 2500, moves: { fast: "Fast", charged: "Charge" }, model_inputs: { state: "available", attack: 180, defense: 150, hp: 150, move_completeness: 1, confidence: 1 } },
      { record_id: "owned-b", name: "B", cp: 2200, moves: { fast: "Fast", charged: null }, model_inputs: { state: "available", attack: 160, defense: 140, hp: 140, move_completeness: 0.5, confidence: 0.8 } },
    ],
  };
  const base = {
    hp: 10000, defense: 180, timer_seconds: 300, group_size: 1,
    weather_multiplier: 1, friendship_multiplier: 1, party_power_multiplier: 1, mega_multiplier: 1, survival_multiplier: 1,
  };
  const solo = Labs.simulateRaidModel(data, base);
  const duo = Labs.simulateRaidModel(data, { ...base, group_size: 2 });
  assert.equal(solo.state, "simulated");
  assert.ok(solo.team.every((item) => item.record_id.startsWith("owned-")));
  assert.ok(duo.estimated_ttw_seconds < solo.estimated_ttw_seconds);
  assert.equal(solo.model_version, "1.0.0");
}

{
  const storage = fakeStorage();
  Labs.saveState(storage, "mega_state", { version: 1, records: {}, energy_by_species: { venusaur: 80 } });
  Labs.saveState(storage, "max_state", { version: 1, records: {}, max_particles: 900 });
  const extended = Labs.extendUnifiedBackup({ product: "pokemon-go-collection-local-data", backup_version: 1, namespaces: {} }, storage);
  assert.equal(extended.namespaces.mega_state.storage_key, Labs.STORAGE.mega_state.key);
  assert.equal(extended.namespaces.max_state.data.max_particles, 900);
  assert.deepEqual(extended.extensions.advanced_labs.namespaces.sort(), Object.keys(Labs.STORAGE).sort());
  const checked = Labs.validateAdvancedBackup(extended, fakeStorage());
  assert.ok(checked.preview.added.includes("mega_state"));
  assert.equal(checked.normalized.mega_state.energy_by_species.venusaur, 80);
}

console.log("advanced lab JavaScript tests passed");
