"use strict";

const assert = require("node:assert/strict");
const api = require("../site/friendship-trade-state.js");

function storageDouble(seed = {}) {
  const data = new Map(Object.entries(seed));
  return {
    getItem(key) { return data.has(key) ? data.get(key) : null; },
    setItem(key, value) { data.set(key, String(value)); },
    snapshot() { return Object.fromEntries(data.entries()); },
  };
}

{
  const state = api.upsertFriend(api.blankState(), {
    id: "ashley",
    label: "Ashley",
    milestone: "forever",
    lucky_friend: "yes",
    forever_friend: "yes",
    remote_trade_available: "yes",
    wishes: ["Mewtwo", " Rayquaza ", ""],
    offers: ["Pikachu"],
    notes: "local-only planning state",
  }, new Date("2026-08-29T20:00:00Z"));
  assert.equal(state.friends.length, 1);
  assert.equal(state.friends[0].milestone, "forever");
  assert.deepEqual(state.friends[0].wishes, ["Mewtwo", "Rayquaza"]);
  assert.equal(state.updated_at, "2026-08-29T20:00:00.000Z");
}

{
  const storage = storageDouble();
  const saved = api.write(storage, {
    version: 1,
    friends: [{ id: "f1", label: "Friend 1", lucky_friend: "maybe", milestone: "invalid" }],
  }, new Date("2026-08-29T21:00:00Z"));
  assert.equal(saved.ok, true);
  const loaded = api.read(storage);
  assert.equal(loaded.friends[0].lucky_friend, "unknown");
  assert.equal(loaded.friends[0].milestone, "unknown");
  assert.equal(loaded.updated_at, "2026-08-29T21:00:00.000Z");
}

{
  const pending = api.pendingRemoteStatus({ pending_remote_started_at: "2026-08-29T12:00:00Z" }, new Date("2026-08-30T12:00:00Z"));
  assert.equal(pending.state, "pending");
  assert.equal(pending.expires_at, "2026-08-31T12:00:00.000Z");
  const expired = api.pendingRemoteStatus({ pending_remote_started_at: "2026-08-27T12:00:00Z" }, new Date("2026-08-30T12:00:01Z"));
  assert.equal(expired.state, "expired");
  assert.equal(expired.remaining_ms, 0);
}

{
  const source = api.upsertFriend(api.blankState(), {
    id: "f2",
    label: "Trade partner",
    remote_trade_used_today: "no",
    reservations: ["record-123"],
  });
  const packet = api.exportBackup(source);
  const imported = api.importBackup(packet);
  assert.equal(imported.ok, true);
  assert.equal(imported.state.friends[0].reservations[0], "record-123");
  const rejected = api.importBackup({ schema: packet.schema, version: 2, payload: source });
  assert.equal(rejected.ok, false);
}

{
  const malformedStorage = storageDouble({ [api.STORAGE_KEY]: "{bad json" });
  assert.deepEqual(api.read(malformedStorage), api.blankState());
}

console.log("friendship trade state tests passed");
