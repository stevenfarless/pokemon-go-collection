"use strict";

const assert = require("assert");
const Calendar = require("../site/event-calendar.js");
const Backup = require("../site/event-calendar-backup.js");

function freshSource(overrides = {}) {
  return {
    dataset_timestamp: "2026-08-28T08:00:00Z",
    freshness: { state: "fresh", max_age_hours: 48 },
    validity: { valid_until: "2026-09-10T00:00:00Z" },
    ...overrides,
  };
}

{
  const now = Date.parse("2026-08-28T12:00:00Z");
  assert.equal(Calendar.runtimeFreshSource(freshSource(), now), true);
  assert.equal(Calendar.runtimeFreshSource(freshSource({ freshness: { state: "stale", max_age_hours: 48 } }), now), false);
  assert.equal(Calendar.runtimeFreshSource(freshSource({ dataset_timestamp: "2026-08-20T00:00:00Z" }), now), false);
  assert.equal(Calendar.runtimeFreshSource(freshSource({ validity: { valid_until: "2026-08-28T11:00:00Z" } }), now), false);
}

{
  const now = Date.parse("2026-08-28T12:00:00Z");
  const item = (starts_at, ends_at, source = freshSource()) => ({ starts_at, ends_at, source });
  assert.equal(Calendar.scopeFor(item("2026-08-28T10:00:00Z", "2026-08-28T14:00:00Z"), now, "UTC"), "now");
  assert.equal(Calendar.scopeFor(item("2026-08-28T15:00:00Z", "2026-08-28T17:00:00Z"), now, "UTC"), "today");
  assert.equal(Calendar.scopeFor(item("2026-08-30T15:00:00Z", "2026-08-30T17:00:00Z"), now, "UTC"), "next7");
  assert.equal(Calendar.scopeFor(item("2026-09-12T15:00:00Z", "2026-09-12T17:00:00Z"), now, "UTC"), "later");
  assert.equal(Calendar.scopeFor(item("2026-08-28T15:00:00Z", "2026-08-28T17:00:00Z", freshSource({ freshness: { state: "stale", max_age_hours: 48 } })), now, "UTC"), "history");
  assert.equal(Calendar.runtimeActionable(item("2026-08-28T10:00:00Z", "2026-08-28T14:00:00Z"), now), true);
}

{
  const state = Calendar.normalizeState({
    version: 1,
    selected_scope: "bogus",
    reminders: [
      { id: "good", title: "Evolve", at: "2026-08-28T20:00:00Z", done: false },
      { id: "bad-date", title: "Bad", at: "not-a-date", done: false },
      { id: "good", title: "Duplicate", at: "2026-08-29T20:00:00Z", done: false },
    ],
  });
  assert.equal(state.selected_scope, "now");
  assert.equal(state.reminders.length, 1);
  assert.equal(state.reminders[0].id, "good");
}

{
  const values = new Map([
    ["pokemon-go-collection:goals:v1", JSON.stringify({ version: 1, goals: [
      { id: "nickit", kind: "living", dex: 827, name: "Nickit" },
      { id: "other", kind: "living", dex: 25, name: "Pikachu" },
      { id: "generic", kind: "living" },
    ] })],
  ]);
  const storage = { getItem(key) { return values.get(key) ?? null; } };
  const matches = Calendar.matchingGoals(storage, { featured_dex: [827], featured_species: ["Nickit"] });
  assert.deepEqual(matches.map((item) => item.id), ["nickit"]);
}

{
  const values = new Map([
    [Backup.EVENT_KEY, JSON.stringify({ version: 1, selected_scope: "next7", reminders: [
      { id: "r1", title: "Community Day prep", at: "2026-08-30T18:00:00Z", done: false },
    ] })],
  ]);
  const storage = {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
  };
  const localApi = { STORAGE_KEYS: {} };
  const tradeApi = {};
  const baseApi = {
    NAMESPACES: {},
    buildUnifiedBackupWithStorageSearch() {
      return { product: "pokemon-go-collection-local-data", backup_version: 1, namespaces: {} };
    },
    validateUnifiedBackupWithStorageSearch(_local, _trade, raw) {
      return { envelope: { ...raw, namespaces: { ...(raw.namespaces || {}) } }, preview: { added: [], replaced: [], absent: [], ignored: [] } };
    },
    restoreUnifiedBackupWithStorageSearch() { return { added: [], replaced: [], absent: [], ignored: [] }; },
  };
  const backup = Backup.buildUnifiedBackupWithEvent(baseApi, localApi, tradeApi, storage);
  assert.equal(backup.namespaces.event_calendar.present, true);
  assert.equal(backup.namespaces.event_calendar.data.selected_scope, "next7");
  const validated = Backup.validateUnifiedBackupWithEvent(baseApi, localApi, tradeApi, backup, storage, []);
  assert(validated.preview.replaced.includes("event_calendar"));

  assert.throws(() => Backup.validateEventCalendarState({ version: 1, selected_scope: "now", reminders: [
    { id: "x", title: "Bad", at: "nope", done: false },
  ] }), /timestamps/);
}

console.log("event calendar and backup tests passed");
