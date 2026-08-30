"use strict";

const assert = require("node:assert/strict");
const stateApi = require("../site/friendship-trade-state.js");
const workspace = require("../site/friendship-trade-workspace.js");

{
  assert.deepEqual(workspace.splitList("Mewtwo, Rayquaza\nPikachu, "), ["Mewtwo", "Rayquaza", "Pikachu"]);
}

{
  const friend = workspace.friendFromValues({
    id: " friend-1 ",
    label: " Trade partner ",
    milestone: "forever",
    friendship_points: "180",
    lucky_friend: "yes",
    remote_trade_available: "yes",
    remote_trade_used_today: "no",
    wishes: "Mewtwo, Rayquaza",
    offers: "Pikachu\nEevee",
  });
  assert.equal(friend.id, "friend-1");
  assert.equal(friend.label, "Trade partner");
  assert.equal(friend.friendship_points, 180);
  assert.deepEqual(friend.wishes, ["Mewtwo", "Rayquaza"]);
  assert.deepEqual(friend.offers, ["Pikachu", "Eevee"]);
}

{
  const summary = workspace.statusSummary({
    remote_trade_available: "yes",
    remote_trade_used_today: "no",
    pending_remote_started_at: "2026-08-29T12:00:00Z",
  }, stateApi, new Date("2026-08-30T12:00:00Z"));
  assert.equal(summary.remote, "Remote Trade available");
  assert.equal(summary.pending_state, "pending");
  assert(summary.pending.includes("2026-08-31T12:00:00.000Z"));
}

{
  const source = stateApi.upsertFriend(stateApi.blankState(), { id: "f1", label: "Friend", wishes: ["Mewtwo"] }, new Date("2026-08-29T20:00:00Z"));
  const parsed = JSON.parse(workspace.backupText(stateApi, source));
  assert.equal(parsed.schema, "pokemon-go-collection.friendship-trade-state");
  assert.equal(parsed.version, 1);
  assert.equal(parsed.payload.friends[0].wishes[0], "Mewtwo");
}

console.log("friendship trade workspace tests passed");
