"use strict";

(function exposeEventCalendar(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionEventCalendar = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const STATE_KEY = "pokemon-go-collection:event-calendar:v1";
  const STATE_VERSION = 1;
  const GOALS_KEY = "pokemon-go-collection:goals:v1";
  const SCOPES = Object.freeze(["now", "today", "next7", "later", "history"]);

  const normalize = (value) => String(value ?? "").trim().toLocaleLowerCase();
  const element = (documentObject, tag, className, text) => {
    const node = documentObject.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  };

  function safeJson(text, fallback = null) {
    try { return JSON.parse(String(text || "")); } catch { return fallback; }
  }

  function normalizeState(raw) {
    if (!raw || Number(raw.version) !== STATE_VERSION) return { version: STATE_VERSION, selected_scope: "now", reminders: [] };
    const selected = SCOPES.includes(String(raw.selected_scope)) ? String(raw.selected_scope) : "now";
    const reminders = [];
    const ids = new Set();
    for (const item of Array.isArray(raw.reminders) ? raw.reminders : []) {
      const id = String(item?.id || "").trim();
      const title = String(item?.title || "").trim().slice(0, 120);
      const at = String(item?.at || "").trim();
      if (!id || !title || !Number.isFinite(Date.parse(at)) || ids.has(id)) continue;
      ids.add(id);
      reminders.push({ id, title, at: new Date(at).toISOString(), done: Boolean(item?.done) });
    }
    reminders.sort((a, b) => Date.parse(a.at) - Date.parse(b.at) || a.id.localeCompare(b.id));
    return { version: STATE_VERSION, selected_scope: selected, reminders };
  }

  function loadState(storage) {
    try { return normalizeState(safeJson(storage?.getItem(STATE_KEY), null)); }
    catch { return normalizeState(null); }
  }

  function saveState(storage, state) {
    const value = normalizeState(state);
    try { storage?.setItem(STATE_KEY, JSON.stringify(value)); return true; }
    catch { return false; }
  }

  function runtimeFreshSource(source, now = Date.now()) {
    if (!source || source.freshness?.state !== "fresh") return false;
    const dataset = Date.parse(source.dataset_timestamp || "");
    const maxAgeHours = Number(source.freshness?.max_age_hours);
    if (!Number.isFinite(dataset) || !Number.isFinite(maxAgeHours) || maxAgeHours <= 0) return false;
    if ((now - dataset) / 3600000 > maxAgeHours) return false;
    const validUntil = Date.parse(source.validity?.valid_until || "");
    if (source.validity?.valid_until && (!Number.isFinite(validUntil) || now > validUntil)) return false;
    return true;
  }

  function validWindow(item) {
    const start = Date.parse(item?.starts_at || "");
    const end = Date.parse(item?.ends_at || "");
    return Number.isFinite(start) && Number.isFinite(end) && end > start ? { start, end } : null;
  }

  function runtimeActionable(item, now = Date.now()) {
    const window = validWindow(item);
    return Boolean(window && runtimeFreshSource(item?.source, now) && window.end >= now);
  }

  function localDateKey(value, timeZone) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "invalid";
    try {
      const parts = new Intl.DateTimeFormat("en-CA", {
        timeZone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).formatToParts(date);
      const map = Object.fromEntries(parts.filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
      return `${map.year}-${map.month}-${map.day}`;
    } catch {
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    }
  }

  function scopeFor(item, now = Date.now(), timeZone = "UTC") {
    const window = validWindow(item);
    if (!window || !runtimeFreshSource(item?.source, now) || window.end < now) return "history";
    if (window.start <= now && now <= window.end) return "now";
    if (localDateKey(window.start, timeZone) === localDateKey(now, timeZone)) return "today";
    if (window.start > now && window.start <= now + 7 * 86400000) return "next7";
    return "later";
  }

  function formatDateTime(value, timeZone) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Unknown time";
    try {
      return new Intl.DateTimeFormat(undefined, {
        timeZone,
        dateStyle: "medium",
        timeStyle: "short",
        timeZoneName: "short",
      }).format(date);
    } catch {
      return date.toLocaleString();
    }
  }

  function exactGoalTargets(goal) {
    const dex = new Set();
    const names = new Set();
    for (const key of ["dex", "target_dex", "pokemon_number"]) {
      const value = Number(goal?.[key]);
      if (Number.isInteger(value) && value > 0) dex.add(value);
    }
    for (const key of ["name", "species", "target_name", "pokemon"]) {
      const value = normalize(goal?.[key]);
      if (value) names.add(value);
    }
    return { dex, names };
  }

  function matchingGoals(storage, event) {
    let payload = null;
    try { payload = safeJson(storage?.getItem(GOALS_KEY), null); } catch { payload = null; }
    if (!payload || Number(payload.version) !== 1 || !Array.isArray(payload.goals)) return [];
    const dexes = new Set((event.featured_dex || []).map(Number));
    const names = new Set((event.featured_species || []).map(normalize));
    return payload.goals.filter((goal) => {
      const targets = exactGoalTargets(goal);
      return [...targets.dex].some((dex) => dexes.has(dex)) || [...targets.names].some((name) => names.has(name));
    }).map((goal) => ({ id: String(goal.id || ""), kind: String(goal.kind || "goal"), label: String(goal.name || goal.label || goal.kind || "Goal") }));
  }

  function addLink(documentObject, parent, label, href) {
    if (!href) return;
    const link = element(documentObject, "a", "", label);
    link.href = href;
    parent.append(link);
  }

  function renderEvidence(documentObject, item) {
    const details = element(documentObject, "details", "event-calendar-evidence");
    details.append(element(documentObject, "summary", "", "Source and freshness"));
    const source = item.source || {};
    const list = element(documentObject, "dl", "event-calendar-kv");
    const rows = [
      ["Authority", source.authority || "Unknown"],
      ["Provider", source.provider || "Unknown"],
      ["Dataset time", source.dataset_timestamp || "Unknown"],
      ["Freshness", source.freshness?.state || "Unknown"],
      ["Snapshot valid until", source.validity?.valid_until || "Unknown"],
    ];
    for (const [label, value] of rows) {
      list.append(element(documentObject, "dt", "", label), element(documentObject, "dd", "", value));
    }
    details.append(list);
    if (/^https?:\/\//i.test(source.source_reference || "")) {
      const link = element(documentObject, "a", "", "Open source");
      link.href = source.source_reference;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      details.append(link);
    }
    return details;
  }

  function renderOwned(documentObject, records, heading) {
    if (!records?.length) return null;
    const section = element(documentObject, "section", "event-calendar-overlay");
    section.append(element(documentObject, "h4", "", heading));
    const list = element(documentObject, "ul", "event-calendar-records");
    for (const record of records) {
      const li = element(documentObject, "li");
      const link = element(documentObject, "a", "", `${record.name || "Pokémon"}${record.form ? ` · ${record.form}` : ""} · CP ${record.cp ?? "?"}`);
      link.href = record.route || `index.html?record=${encodeURIComponent(record.record_id || "")}`;
      li.append(link);
      if (record.pvp_best_rank_percent != null) li.append(element(documentObject, "small", "", ` · PvP rank-percent signal ${Number(record.pvp_best_rank_percent).toFixed(1)}%`));
      list.append(li);
    }
    section.append(list);
    return section;
  }

  function renderItem(root, item, timeZone, parentEvent = null) {
    const documentObject = root.document;
    const article = element(documentObject, "article", "event-calendar-item ds-card");
    article.dataset.kind = item.kind || "event";
    const header = element(documentObject, "header", "event-calendar-item-header");
    header.append(element(documentObject, "h3", "", item.title || "Event window"));
    const source = item.source || {};
    header.append(element(documentObject, "span", "ds-source-chip", `${source.authority || "Unknown"} · ${source.freshness?.state || "unknown"}`));
    article.append(header);
    article.append(element(documentObject, "p", "event-calendar-time", `${formatDateTime(item.starts_at, timeZone)} to ${formatDateTime(item.ends_at, timeZone)}`));

    if (item.kind === "event") {
      const restrictions = item.restrictions || {};
      if (restrictions.state === "qualified") {
        article.append(element(documentObject, "p", "event-calendar-warning", `Restrictions/paid conditions are present in the reviewed source. Expand evidence before planning.`));
      }
      const overlays = item.overlays || {};
      const goals = matchingGoals(root.localStorage, item);
      if (goals.length) {
        const goalSection = element(documentObject, "section", "event-calendar-overlay");
        goalSection.append(element(documentObject, "h4", "", "Local goals matched exactly"));
        const list = element(documentObject, "ul");
        for (const goal of goals) list.append(element(documentObject, "li", "", `${goal.label} (${goal.kind})`));
        goalSection.append(list);
        article.append(goalSection);
      }
      const owned = renderOwned(documentObject, overlays.exact_owned_records, "Exact owned records related to this event");
      if (owned) article.append(owned);
      const pvp = renderOwned(documentObject, overlays.strong_pvp_records, "Strong Poke Genie PvP rank-percent signals among those records");
      if (pvp) article.append(pvp);
      if (overlays.missing_featured_species?.length) {
        const section = element(documentObject, "section", "event-calendar-overlay");
        section.append(element(documentObject, "h4", "", "Featured collection gaps"));
        const list = element(documentObject, "ul");
        for (const gap of overlays.missing_featured_species) {
          const li = element(documentObject, "li");
          addLink(documentObject, li, `#${gap.dex} ${gap.name || "missing species"}`, gap.route);
          list.append(li);
        }
        section.append(list);
        article.append(section);
      }
      if (overlays.related_weak_roster_types?.length) {
        article.append(element(documentObject, "p", "event-calendar-note", `Related weakest roster types: ${overlays.related_weak_roster_types.join(", ")}. This is preparation context, not proof the featured species fixes the gap.`));
      }
      const prep = element(documentObject, "div", "event-calendar-links");
      for (const [key, href] of Object.entries(overlays.prep_links || {})) addLink(documentObject, prep, key.replaceAll("_", " "), href);
      if (prep.childNodes.length) article.append(prep);
    } else {
      const exact = renderOwned(documentObject, item.exact_owned_records, "Exact owned records eligible for review");
      if (exact) article.append(exact);
      if (item.target?.exclusive_move) article.append(element(documentObject, "p", "event-calendar-note", `Exclusive move: ${item.target.exclusive_move}`));
      if (item.manual_confirmation) article.append(element(documentObject, "p", "event-calendar-warning", item.manual_confirmation));
      if (parentEvent) article.append(element(documentObject, "p", "event-calendar-note", `Parent event: ${parentEvent.title}`));
    }

    article.append(renderEvidence(documentObject, item));
    if (item.route) addLink(documentObject, article, "Open related planner", item.route);
    return article;
  }

  function allItems(payload) {
    const parents = new Map((payload.events || []).map((item) => [String(item.id), item]));
    const combined = [
      ...(payload.events || []).map((item) => ({ item, parent: null })),
      ...(payload.deadlines || []).map((item) => ({ item, parent: parents.get(String(item.parent_event_id)) || null })),
    ];
    return combined.sort((a, b) => Date.parse(a.item.starts_at || a.item.ends_at || "") - Date.parse(b.item.starts_at || b.item.ends_at || "") || String(a.item.id).localeCompare(String(b.item.id)));
  }

  function itemsForScope(payload, scope, now = Date.now(), timeZone = "UTC") {
    const selected = SCOPES.includes(scope) ? scope : "now";
    return allItems(payload).filter(({ item }) => scopeFor(item, now, timeZone) === selected);
  }

  function renderReminders(root, state, saveAndRender, timeZone) {
    const documentObject = root.document;
    const mount = documentObject.getElementById("event-reminder-list");
    if (!mount) return;
    mount.replaceChildren();
    if (!state.reminders.length) {
      mount.append(element(documentObject, "p", "ds-empty", "No local reminders."));
      return;
    }
    const list = element(documentObject, "ul", "event-calendar-reminder-list");
    for (const reminder of state.reminders) {
      const li = element(documentObject, "li", reminder.done ? "is-done" : "");
      const label = element(documentObject, "label");
      const check = element(documentObject, "input");
      check.type = "checkbox";
      check.checked = reminder.done;
      check.addEventListener("change", () => {
        reminder.done = check.checked;
        saveAndRender();
      });
      label.append(check, element(documentObject, "span", "", `${reminder.title} · ${formatDateTime(reminder.at, timeZone)}`));
      const remove = element(documentObject, "button", "", "Remove");
      remove.type = "button";
      remove.addEventListener("click", () => {
        state.reminders = state.reminders.filter((item) => item.id !== reminder.id);
        saveAndRender();
      });
      li.append(label, remove);
      list.append(li);
    }
    mount.append(list);
  }

  async function install(root) {
    const documentObject = root.document;
    const mount = documentObject?.getElementById("event-calendar-root");
    if (!mount) return;
    const status = documentObject.getElementById("event-calendar-status");
    const timeZone = (() => {
      try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; }
      catch { return "UTC"; }
    })();
    const timezoneLabel = documentObject.getElementById("event-calendar-timezone");
    if (timezoneLabel) timezoneLabel.textContent = `Times are displayed in your browser timezone: ${timeZone}.`;

    let payload;
    try {
      const response = await root.fetch("data/event-calendar.json");
      if (!response.ok) throw new Error(`Event Calendar data returned HTTP ${response.status}`);
      payload = await response.json();
    } catch (error) {
      mount.replaceChildren(element(documentObject, "p", "ds-notice", `Event Calendar unavailable: ${error.message || error}`));
      return;
    }

    const state = loadState(root.localStorage);
    const queryEvent = (() => {
      try { return new URL(root.location.href).searchParams.get("event"); } catch { return null; }
    })();

    const render = () => {
      saveState(root.localStorage, state);
      documentObject.querySelectorAll("[data-calendar-scope]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.calendarScope === state.selected_scope)));
      mount.replaceChildren();
      let rows = itemsForScope(payload, state.selected_scope, Date.now(), timeZone);
      if (queryEvent) rows = rows.filter(({ item, parent }) => String(item.id) === queryEvent || String(item.parent_event_id) === queryEvent || String(parent?.id) === queryEvent);
      const heading = element(documentObject, "section", "event-calendar-summary ds-card");
      const totalCurrent = allItems(payload).filter(({ item }) => runtimeActionable(item)).length;
      heading.append(element(documentObject, "h2", "", `${state.selected_scope === "next7" ? "Next 7 days" : state.selected_scope[0].toUpperCase() + state.selected_scope.slice(1)} agenda`));
      heading.append(element(documentObject, "p", "", `${rows.length} item${rows.length === 1 ? "" : "s"} in this scope. ${totalCurrent} source-fresh window${totalCurrent === 1 ? "" : "s"} remain potentially actionable at runtime.`));
      mount.append(heading);
      if (!rows.length) {
        const message = state.selected_scope === "history"
          ? "No retained stale or expired event windows are available."
          : "No event instruction is available in this scope. Stale or expired snapshots are intentionally excluded from actionable planning.";
        mount.append(element(documentObject, "p", "ds-empty", message));
      }
      for (const { item, parent } of rows) mount.append(renderItem(root, item, timeZone, parent));
      if (status) status.textContent = `Showing ${rows.length} ${state.selected_scope} agenda item${rows.length === 1 ? "" : "s"}.`;
      renderReminders(root, state, render, timeZone);
    };

    documentObject.querySelectorAll("[data-calendar-scope]").forEach((button) => button.addEventListener("click", () => {
      state.selected_scope = SCOPES.includes(button.dataset.calendarScope) ? button.dataset.calendarScope : "now";
      render();
    }));

    documentObject.getElementById("event-reminder-add")?.addEventListener("click", () => {
      const title = String(documentObject.getElementById("event-reminder-title")?.value || "").trim().slice(0, 120);
      const rawAt = String(documentObject.getElementById("event-reminder-at")?.value || "").trim();
      const parsed = Date.parse(rawAt);
      if (!title || !Number.isFinite(parsed)) {
        if (status) status.textContent = "Enter a reminder title and valid local date/time.";
        return;
      }
      const id = `reminder-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      state.reminders.push({ id, title, at: new Date(parsed).toISOString(), done: false });
      state.reminders.sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
      const titleInput = documentObject.getElementById("event-reminder-title");
      const atInput = documentObject.getElementById("event-reminder-at");
      if (titleInput) titleInput.value = "";
      if (atInput) atInput.value = "";
      render();
    });

    render();
  }

  return {
    STATE_KEY,
    STATE_VERSION,
    SCOPES,
    normalizeState,
    loadState,
    saveState,
    runtimeFreshSource,
    validWindow,
    runtimeActionable,
    localDateKey,
    scopeFor,
    exactGoalTargets,
    matchingGoals,
    allItems,
    itemsForScope,
    install,
  };
});
