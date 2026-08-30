"use strict";

(function exposeFriendshipTradeWorkspace(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionFriendshipTradeWorkspace = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  function splitList(value) {
    return String(value ?? "").split(/[,\n]/).map((item) => item.trim()).filter(Boolean);
  }

  function friendFromValues(values = {}) {
    return {
      id: String(values.id || `friend-${Date.now()}`).trim(),
      label: String(values.label || "Friend").trim(),
      milestone: String(values.milestone || "unknown"),
      friendship_points: values.friendship_points === "" || values.friendship_points == null ? null : Number(values.friendship_points),
      lucky_friend: String(values.lucky_friend || "unknown"),
      forever_friend: String(values.forever_friend || "unknown"),
      remote_trade_available: String(values.remote_trade_available || "unknown"),
      remote_trade_used_today: String(values.remote_trade_used_today || "unknown"),
      pending_remote_started_at: String(values.pending_remote_started_at || ""),
      last_remote_trade_at: String(values.last_remote_trade_at || ""),
      wishes: splitList(values.wishes),
      offers: splitList(values.offers),
      reservations: splitList(values.reservations),
      notes: String(values.notes || "").trim(),
    };
  }

  function statusSummary(friend, stateApi, now = new Date()) {
    const pending = stateApi?.pendingRemoteStatus ? stateApi.pendingRemoteStatus(friend, now) : { state: "none", expires_at: "" };
    const remote = friend?.remote_trade_available === "yes"
      ? (friend?.remote_trade_used_today === "yes" ? "Remote Trade used today" : "Remote Trade available")
      : friend?.remote_trade_available === "no" ? "No Remote Trade available" : "Remote Trade status unknown";
    const pendingText = pending.state === "pending" ? `Pending step expires ${pending.expires_at}` : pending.state === "expired" ? "Pending Remote Trade step expired" : "No pending Remote Trade step";
    return { remote, pending: pendingText, pending_state: pending.state };
  }

  function backupText(stateApi, state) {
    if (!stateApi?.exportBackup) throw new Error("Friendship state backup engine is unavailable.");
    return JSON.stringify(stateApi.exportBackup(state), null, 2) + "\n";
  }

  function render(root, state, stateApi, now = new Date()) {
    const target = root.document.getElementById("friendship-list");
    if (!target) return;
    if (!state.friends.length) {
      target.innerHTML = '<p class="friend-empty">No local friends are saved yet.</p>';
      return;
    }
    target.innerHTML = state.friends.map((friend) => {
      const summary = statusSummary(friend, stateApi, now);
      const wishes = friend.wishes.length ? friend.wishes.join(", ") : "none";
      const offers = friend.offers.length ? friend.offers.join(", ") : "none";
      return `<article class="friend-card" data-friend-id="${escapeHtml(friend.id)}">
        <div><h2>${escapeHtml(friend.label)}</h2><p>${escapeHtml(friend.milestone)} · ${escapeHtml(friend.friendship_points ?? "points unknown")} · Lucky ${escapeHtml(friend.lucky_friend)}</p></div>
        <p><strong>${escapeHtml(summary.remote)}</strong><br>${escapeHtml(summary.pending)}</p>
        <p><strong>Wants:</strong> ${escapeHtml(wishes)}<br><strong>Offers:</strong> ${escapeHtml(offers)}</p>
        ${friend.notes ? `<p>${escapeHtml(friend.notes)}</p>` : ""}
        <button type="button" data-remove-friend="${escapeHtml(friend.id)}">Remove local friend</button>
      </article>`;
    }).join("");
  }

  function install(root) {
    const stateApi = root.CollectionFriendshipTradeState;
    const form = root.document.getElementById("friendship-form");
    if (!stateApi || !form) return;
    const status = root.document.getElementById("friendship-status");
    let state = stateApi.read(root.localStorage);
    render(root, state, stateApi);

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new root.FormData(form).entries());
      state = stateApi.upsertFriend(state, friendFromValues(data));
      const result = stateApi.write(root.localStorage, state);
      state = result.state;
      render(root, state, stateApi);
      if (status) status.textContent = result.ok ? "Friendship planning state saved locally." : `Save failed: ${result.error}.`;
      if (result.ok) form.reset();
    });

    root.document.getElementById("friendship-list")?.addEventListener("click", (event) => {
      const id = event.target?.dataset?.removeFriend;
      if (!id) return;
      state = stateApi.removeFriend(state, id);
      const result = stateApi.write(root.localStorage, state);
      state = result.state;
      render(root, state, stateApi);
      if (status) status.textContent = result.ok ? "Local friend removed." : `Remove failed: ${result.error}.`;
    });

    root.document.getElementById("friendship-export")?.addEventListener("click", () => {
      try {
        const blob = new root.Blob([backupText(stateApi, state)], { type: "application/json" });
        const url = root.URL.createObjectURL(blob);
        const anchor = root.document.createElement("a");
        anchor.href = url; anchor.download = "pokemon-go-friendship-trade-state.json"; anchor.click(); root.URL.revokeObjectURL(url);
        if (status) status.textContent = "Friendship planning backup exported.";
      } catch (error) { if (status) status.textContent = `Export failed: ${error.message || error}`; }
    });

    root.document.getElementById("friendship-import")?.addEventListener("change", async (event) => {
      try {
        const file = event.target.files?.[0]; if (!file) return;
        const imported = stateApi.importBackup(JSON.parse(await file.text()));
        if (!imported.ok) throw new Error(imported.error || "unsupported backup");
        const saved = stateApi.write(root.localStorage, imported.state);
        if (!saved.ok) throw new Error(saved.error);
        state = saved.state;
        render(root, state, stateApi);
        if (status) status.textContent = "Friendship planning backup restored locally.";
      } catch (error) { if (status) status.textContent = `Import failed: ${error.message || error}`; }
    });
  }

  return { splitList, friendFromValues, statusSummary, backupText, render, install };
});
