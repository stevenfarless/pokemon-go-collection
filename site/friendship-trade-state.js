"use strict";

(function exposeFriendshipTradeState(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionFriendshipTradeState = api;
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const STORAGE_KEY = "pokemon-go-collection:friendship-trade-state:v1";
  const VERSION = 1;
  const MAX_FRIENDS = 500;
  const MAX_LIST_ITEMS = 250;
  const MAX_TEXT = 160;
  const MILESTONES = new Set(["unknown", "good", "great", "ultra", "best", "forever"]);
  const TRI_STATE = new Set(["unknown", "yes", "no"]);

  const cleanText = (value, max = MAX_TEXT) => String(value ?? "").trim().slice(0, max);
  const cleanTriState = (value) => TRI_STATE.has(String(value || "").toLowerCase()) ? String(value).toLowerCase() : "unknown";
  const cleanMilestone = (value) => MILESTONES.has(String(value || "").toLowerCase()) ? String(value).toLowerCase() : "unknown";
  const cleanIso = (value) => {
    const text = cleanText(value, 40);
    if (!text) return "";
    const parsed = Date.parse(text);
    return Number.isFinite(parsed) ? new Date(parsed).toISOString() : "";
  };
  const cleanList = (value) => (Array.isArray(value) ? value : [])
    .map((item) => cleanText(item, MAX_TEXT))
    .filter(Boolean)
    .slice(0, MAX_LIST_ITEMS);

  function blankState() {
    return { version: VERSION, friends: [], updated_at: "" };
  }

  function sanitizeFriend(raw, index = 0) {
    const id = cleanText(raw?.id || `friend-${index + 1}`, 80) || `friend-${index + 1}`;
    return {
      id,
      label: cleanText(raw?.label || raw?.nickname || "Friend"),
      milestone: cleanMilestone(raw?.milestone),
      friendship_points: Number.isFinite(Number(raw?.friendship_points)) && Number(raw.friendship_points) >= 0
        ? Math.floor(Number(raw.friendship_points))
        : null,
      lucky_friend: cleanTriState(raw?.lucky_friend),
      forever_friend: cleanTriState(raw?.forever_friend),
      remote_trade_available: cleanTriState(raw?.remote_trade_available),
      remote_trade_used_today: cleanTriState(raw?.remote_trade_used_today),
      pending_remote_started_at: cleanIso(raw?.pending_remote_started_at),
      last_remote_trade_at: cleanIso(raw?.last_remote_trade_at),
      wishes: cleanList(raw?.wishes),
      offers: cleanList(raw?.offers),
      reservations: cleanList(raw?.reservations),
      notes: cleanText(raw?.notes, 500),
    };
  }

  function sanitizeState(raw) {
    const output = blankState();
    if (!raw || typeof raw !== "object" || Number(raw.version) !== VERSION) return output;
    const seen = new Set();
    for (const [index, friend] of (Array.isArray(raw.friends) ? raw.friends : []).slice(0, MAX_FRIENDS).entries()) {
      const clean = sanitizeFriend(friend, index);
      if (seen.has(clean.id)) continue;
      seen.add(clean.id);
      output.friends.push(clean);
    }
    output.updated_at = cleanIso(raw.updated_at);
    return output;
  }

  function read(storage) {
    if (!storage?.getItem) return blankState();
    try {
      const raw = storage.getItem(STORAGE_KEY);
      return raw ? sanitizeState(JSON.parse(raw)) : blankState();
    } catch {
      return blankState();
    }
  }

  function write(storage, state, now = new Date()) {
    const clean = sanitizeState({ ...state, version: VERSION });
    clean.updated_at = new Date(now).toISOString();
    if (!storage?.setItem) return { ok: false, state: clean, error: "storage-unavailable" };
    try {
      storage.setItem(STORAGE_KEY, JSON.stringify(clean));
      return { ok: true, state: clean, error: "" };
    } catch {
      return { ok: false, state: clean, error: "storage-write-failed" };
    }
  }

  function upsertFriend(state, friend, now = new Date()) {
    const cleanState = sanitizeState({ ...state, version: VERSION });
    const cleanFriend = sanitizeFriend(friend, cleanState.friends.length);
    const existing = cleanState.friends.findIndex((item) => item.id === cleanFriend.id);
    if (existing >= 0) cleanState.friends[existing] = cleanFriend;
    else if (cleanState.friends.length < MAX_FRIENDS) cleanState.friends.push(cleanFriend);
    cleanState.updated_at = new Date(now).toISOString();
    return cleanState;
  }

  function removeFriend(state, id, now = new Date()) {
    const cleanState = sanitizeState({ ...state, version: VERSION });
    cleanState.friends = cleanState.friends.filter((item) => item.id !== String(id));
    cleanState.updated_at = new Date(now).toISOString();
    return cleanState;
  }

  function pendingRemoteStatus(friend, now = new Date()) {
    const started = Date.parse(friend?.pending_remote_started_at || "");
    if (!Number.isFinite(started)) return { state: "none", expires_at: "", remaining_ms: null };
    const expires = started + (48 * 60 * 60 * 1000);
    const remaining = expires - new Date(now).getTime();
    return {
      state: remaining > 0 ? "pending" : "expired",
      expires_at: new Date(expires).toISOString(),
      remaining_ms: Math.max(0, remaining),
    };
  }

  function exportBackup(state) {
    return {
      schema: "pokemon-go-collection.friendship-trade-state",
      version: VERSION,
      payload: sanitizeState({ ...state, version: VERSION }),
    };
  }

  function importBackup(packet) {
    if (!packet || packet.schema !== "pokemon-go-collection.friendship-trade-state" || Number(packet.version) !== VERSION) {
      return { ok: false, state: blankState(), error: "unsupported-backup" };
    }
    return { ok: true, state: sanitizeState(packet.payload), error: "" };
  }

  return {
    STORAGE_KEY,
    VERSION,
    blankState,
    sanitizeFriend,
    sanitizeState,
    read,
    write,
    upsertFriend,
    removeFriend,
    pendingRemoteStatus,
    exportBackup,
    importBackup,
  };
});
