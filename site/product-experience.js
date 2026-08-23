"use strict";

(function exposeProductExperience(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionProductExperience = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const GUIDANCE_KEY = "pokemon-go-collection:guidance:v1";
  const ONBOARDING_KEY = "pokemon-go-collection:onboarding:v1";
  const RECENT_KEY = "pokemon-go-collection:global-search-recent:v1";
  const TODAY_STATE_KEY = "pokemon-go-collection:today-dismissals:v1";
  const SAVED_VIEWS_KEY = "pokemon-go-collection:saved-views:v1";
  const GUIDANCE = ["essential", "detailed", "expert"];
  const DOMAIN_LABELS = {
    action: "Actions",
    "owned-record": "Owned Pokémon",
    "owned-species": "Owned species",
    reference: "Species reference",
    family: "Families",
    type: "Types",
    move: "Moves",
    mechanic: "Mechanics",
    current: "Current data",
    "saved-view": "Saved views",
  };
  const GLOSSARY = {
    "IV %": "A summary of the three appraisal IVs. Exact Attack, Defense, and HP IVs are the authoritative values when present.",
    "Exact IV": "The individual Attack, Defense, and HP appraisal values, each from 0 to 15.",
    "PvP rank": "Poke Genie ranking of an IV combination under a league cap. It is not a current-meta ranking.",
    "Stat product": "A bulk-and-attack product used to compare PvP IV combinations under a league cap.",
    Shadow: "A Pokémon explicitly identified as Shadow in the collection source. Shadow battle mechanics and availability require supported mechanics/current data.",
    "Mega / Max": "Transformation or Max eligibility from the versioned knowledge snapshot. Current availability is a separate fresh-data question.",
    "Build cost": "Known Stardust or Candy inputs. Cost alone is not a recommendation to spend resources.",
    Freshness: "Whether time-sensitive data is still inside its declared age and validity window.",
    Uncertainty: "Missing or unsupported source fields stay unknown instead of being inferred.",
  };

  function normalizeGuidance(value) {
    const normalized = String(value || "").toLowerCase();
    return GUIDANCE.includes(normalized) ? normalized : "essential";
  }

  function safeJson(raw, fallback) {
    try { return JSON.parse(raw); } catch { return fallback; }
  }

  function readStorage(storage, key, fallback) {
    try { return safeJson(storage?.getItem(key), fallback); } catch { return fallback; }
  }

  function writeStorage(storage, key, value) {
    try { storage?.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
  }

  function element(documentObject, tag, className, text) {
    const node = documentObject.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function appendTextRow(documentObject, parent, label, value, className = "") {
    const row = element(documentObject, "div", `product-kv ${className}`.trim());
    row.append(element(documentObject, "dt", "", label), element(documentObject, "dd", "", value ?? "Unknown"));
    parent.append(row);
    return row;
  }

  function formatDateTime(value) {
    if (!value) return "Unknown";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    try {
      if (globalThis.CollectionI18n?.formatDateTime) return globalThis.CollectionI18n.formatDateTime(date);
    } catch { /* Intl fallback below */ }
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
  }

  function runtimeFresh(value, now = Date.now()) {
    if (!value || value.freshness?.state !== "fresh") return false;
    const dataset = Date.parse(value.dataset_timestamp || value.datasetTimestamp || "");
    const maxAgeHours = Number(value.freshness?.max_age_hours);
    if (!Number.isFinite(dataset) || !Number.isFinite(maxAgeHours) || maxAgeHours <= 0) return false;
    if ((now - dataset) / 3600000 > maxAgeHours) return false;
    const validUntil = value.validity?.valid_until || value.deadline;
    if (validUntil) {
      const deadline = Date.parse(validUntil);
      if (!Number.isFinite(deadline) || now > deadline) return false;
    }
    return true;
  }

  function searchText(item) {
    return [item.title, item.subtitle, ...(item.terms || [])].filter(Boolean).join(" ").toLocaleLowerCase();
  }

  function scoreSearchItem(item, query) {
    const text = String(query || "").trim().toLocaleLowerCase();
    if (!text) return 1;
    const tokens = text.split(/\s+/).filter(Boolean);
    const haystack = searchText(item);
    if (!tokens.every((token) => haystack.includes(token))) return 0;
    const title = String(item.title || "").toLocaleLowerCase();
    let score = 10;
    if (title === text) score += 200;
    else if (title.startsWith(text)) score += 100;
    else if (title.includes(text)) score += 50;
    score += tokens.reduce((total, token) => total + (title.includes(token) ? 8 : 2), 0);
    if (item.domain === "action") score += 3;
    if (item.domain === "owned-record") score += 2;
    return score;
  }

  function currentSearchItemAllowed(item, now = Date.now()) {
    if (item?.domain !== "current") return true;
    if (item.freshness !== "fresh") return false;
    const dataset = Date.parse(item.dataset_timestamp || "");
    if (!Number.isFinite(dataset)) return false;
    // Search index lacks a category-specific policy by design, so current results are
    // also verified against data/external/index.json when the palette loads.
    return dataset <= now;
  }

  function createDialog(documentObject, id, label) {
    let dialog = documentObject.getElementById(id);
    if (dialog) return dialog;
    dialog = element(documentObject, "dialog", "product-dialog");
    dialog.id = id;
    dialog.setAttribute("aria-label", label);
    const shell = element(documentObject, "div", "product-dialog-shell");
    const header = element(documentObject, "header", "product-dialog-header");
    header.append(element(documentObject, "h2", "", label));
    const close = element(documentObject, "button", "product-dialog-close", "Close");
    close.type = "button";
    close.addEventListener("click", () => dialog.close());
    header.append(close);
    const body = element(documentObject, "div", "product-dialog-body");
    shell.append(header, body);
    dialog.append(shell);
    documentObject.body.append(dialog);
    return dialog;
  }

  function termButton(documentObject, term) {
    const button = element(documentObject, "button", "product-term", "?");
    button.type = "button";
    button.dataset.term = term;
    button.setAttribute("aria-label", `Define ${term}`);
    return button;
  }

  function installGlossary(root) {
    const documentObject = root.document;
    const dialog = createDialog(documentObject, "product-glossary-dialog", "Definitions");
    documentObject.addEventListener("click", (event) => {
      const button = event.target.closest?.("[data-term]");
      if (!button) return;
      const term = button.dataset.term;
      const body = dialog.querySelector(".product-dialog-body");
      body.replaceChildren();
      body.append(element(documentObject, "h3", "", term));
      body.append(element(documentObject, "p", "", GLOSSARY[term] || "No definition is published for this term."));
      dialog.showModal();
    });
    return dialog;
  }

  function applyGuidance(documentObject, level) {
    const normalized = normalizeGuidance(level);
    documentObject.documentElement.dataset.guidance = normalized;
    documentObject.querySelectorAll("[data-guidance-choice]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.guidanceChoice === normalized));
    });
    return normalized;
  }

  function installGuidance(root, utilityBar) {
    const documentObject = root.document;
    const storage = root.localStorage;
    const saved = (() => {
      try { return storage?.getItem(GUIDANCE_KEY); } catch { return null; }
    })();
    const initial = applyGuidance(documentObject, saved || "essential");
    const dialog = createDialog(documentObject, "product-guidance-dialog", "Guidance level");
    const body = dialog.querySelector(".product-dialog-body");
    const description = element(documentObject, "p", "", "Guidance changes presentation depth only. It never changes filters, calculations, safety warnings, URLs, or underlying results.");
    const choices = element(documentObject, "div", "ds-segmented product-guidance-choices");
    for (const level of GUIDANCE) {
      const button = element(documentObject, "button", "", level[0].toUpperCase() + level.slice(1));
      button.type = "button";
      button.dataset.guidanceChoice = level;
      button.setAttribute("aria-pressed", String(level === initial));
      button.addEventListener("click", () => {
        applyGuidance(documentObject, level);
        try { storage?.setItem(GUIDANCE_KEY, level); } catch { /* local preference only */ }
      });
      choices.append(button);
    }
    const defs = element(documentObject, "section", "product-guidance-definitions");
    defs.append(element(documentObject, "h3", "", "Just-in-time definitions"));
    const terms = element(documentObject, "div", "product-term-list");
    for (const term of Object.keys(GLOSSARY)) {
      const button = element(documentObject, "button", "product-definition-button", term);
      button.type = "button";
      button.dataset.term = term;
      terms.append(button);
    }
    defs.append(terms);
    body.append(description, choices, defs);

    const open = element(documentObject, "button", "product-utility-button", "Guidance");
    open.type = "button";
    open.addEventListener("click", () => dialog.showModal());
    utilityBar.append(open);

    let oriented = false;
    try { oriented = storage?.getItem(ONBOARDING_KEY) === "done"; } catch { oriented = false; }
    if (!oriented) {
      const onboarding = createDialog(documentObject, "product-onboarding-dialog", "Quick orientation");
      const onboardingBody = onboarding.querySelector(".product-dialog-body");
      onboardingBody.append(
        element(documentObject, "p", "", "Collection is the owned-record workspace. Today prioritizes shared action queues. Insights summarizes the collection. Tools contains planning and local-data utilities. Reference covers every supported species/form."),
        element(documentObject, "p", "", "Evidence labels matter: owned collection facts, versioned stable knowledge, calculated outputs, browser-local preferences, and fresh current data are kept distinct."),
        element(documentObject, "p", "", "Safety, stale-data, missing-data, uncertainty, and irreversible-action warnings remain visible at every guidance level."),
      );
      const done = element(documentObject, "button", "", "Got it");
      done.type = "button";
      done.addEventListener("click", () => {
        try { storage?.setItem(ONBOARDING_KEY, "done"); } catch { /* non-fatal */ }
        onboarding.close();
      });
      onboardingBody.append(done);
      root.setTimeout(() => onboarding.showModal(), 0);
    }
  }

  async function loadExternalFreshness(root) {
    try {
      const response = await root.fetch("data/external/index.json");
      if (!response.ok) return new Map();
      const payload = await response.json();
      const map = new Map();
      for (const snapshot of payload.snapshots || []) {
        if (runtimeFresh(snapshot)) map.set(snapshot.path, snapshot);
      }
      return map;
    } catch { return new Map(); }
  }

  function savedViewItems(storage) {
    const payload = readStorage(storage, SAVED_VIEWS_KEY, { version: 1, views: [] });
    if (payload?.version !== 1 || !Array.isArray(payload.views)) return [];
    return payload.views.flatMap((view, index) => {
      const name = String(view?.name || "").trim();
      const query = String(view?.query || "");
      if (!name || (!query.startsWith("?") && query !== "")) return [];
      return [{ id: `saved-view:${index}:${name}`, domain: "saved-view", title: name, subtitle: "Browser-local saved Collection view", route: `index.html${query}`, terms: ["saved view", name] }];
    });
  }

  function recentState(storage) {
    const value = readStorage(storage, RECENT_KEY, { version: 1, queries: [], selections: [] });
    return value?.version === 1 && Array.isArray(value.queries) && Array.isArray(value.selections)
      ? value
      : { version: 1, queries: [], selections: [] };
  }

  function rememberSearch(storage, query, item) {
    const state = recentState(storage);
    const cleanQuery = String(query || "").trim();
    if (cleanQuery) state.queries = [cleanQuery, ...state.queries.filter((value) => value !== cleanQuery)].slice(0, 8);
    if (item) {
      const minimal = { id: item.id, domain: item.domain, title: item.title, subtitle: item.subtitle, route: item.route };
      state.selections = [minimal, ...state.selections.filter((value) => value.id !== item.id)].slice(0, 8);
    }
    writeStorage(storage, RECENT_KEY, state);
  }

  function installGlobalSearch(root, utilityBar) {
    const documentObject = root.document;
    const storage = root.localStorage;
    const dialog = createDialog(documentObject, "product-global-search", "Global search and commands");
    dialog.classList.add("product-search-dialog");
    const body = dialog.querySelector(".product-dialog-body");
    const input = element(documentObject, "input", "product-global-search-input");
    input.type = "search";
    input.placeholder = "Search owned Pokémon, species, moves, tools, current data…";
    input.setAttribute("aria-label", "Global search");
    input.setAttribute("autocomplete", "off");
    const status = element(documentObject, "p", "product-search-status", "Type to search every supported domain.");
    status.setAttribute("role", "status");
    const results = element(documentObject, "div", "product-search-results");
    results.setAttribute("role", "listbox");
    const recent = element(documentObject, "div", "product-search-recent");
    const clearRecent = element(documentObject, "button", "product-clear-recent", "Clear recent");
    clearRecent.type = "button";
    clearRecent.addEventListener("click", () => {
      writeStorage(storage, RECENT_KEY, { version: 1, queries: [], selections: [] });
      renderRecent();
    });
    body.append(input, status, results, recent, clearRecent);

    let staticIndex = null;
    let freshPaths = new Map();
    let activeButtons = [];
    let activeIndex = -1;

    async function ensureIndex() {
      if (staticIndex) return staticIndex;
      const [response, freshness] = await Promise.all([
        root.fetch("data/global-search-index.json"),
        loadExternalFreshness(root),
      ]);
      if (!response.ok) throw new Error("Global search index could not be loaded");
      staticIndex = await response.json();
      freshPaths = freshness;
      return staticIndex;
    }

    function allowed(item) {
      if (item.domain !== "current") return true;
      return currentSearchItemAllowed(item) && [...freshPaths.values()].some((snapshot) =>
        snapshot.data_category && item.id.includes(`current:${snapshot.data_category}:`));
    }

    function select(item, query) {
      rememberSearch(storage, query, item);
      root.location.assign(item.route);
    }

    function groupResults(matches, query) {
      results.replaceChildren();
      activeButtons = [];
      activeIndex = -1;
      const grouped = new Map();
      for (const match of matches) {
        if (!grouped.has(match.item.domain)) grouped.set(match.item.domain, []);
        grouped.get(match.item.domain).push(match.item);
      }
      const order = staticIndex?.domain_order || Object.keys(DOMAIN_LABELS);
      for (const domain of order) {
        const items = grouped.get(domain);
        if (!items?.length) continue;
        const section = element(documentObject, "section", "product-search-group");
        section.append(element(documentObject, "h3", "", DOMAIN_LABELS[domain] || domain));
        for (const item of items.slice(0, 8)) {
          const button = element(documentObject, "button", "product-search-result");
          button.type = "button";
          button.setAttribute("role", "option");
          button.append(element(documentObject, "strong", "", item.title), element(documentObject, "small", "", item.subtitle));
          button.addEventListener("click", () => select(item, query));
          section.append(button);
          activeButtons.push(button);
        }
        results.append(section);
      }
      status.textContent = `${matches.length} matching results across ${grouped.size} groups.`;
    }

    async function runSearch() {
      try {
        const index = await ensureIndex();
        const query = input.value.trim();
        const dynamic = savedViewItems(storage);
        const matches = [...index.items, ...dynamic]
          .filter(allowed)
          .map((item) => ({ item, score: scoreSearchItem(item, query) }))
          .filter((candidate) => candidate.score > 0)
          .sort((a, b) => b.score - a.score || String(a.item.title).localeCompare(String(b.item.title)))
          .slice(0, 80);
        groupResults(matches, query);
      } catch (error) {
        status.textContent = error?.message || "Global search is unavailable.";
        results.replaceChildren();
      }
    }

    function renderRecent() {
      recent.replaceChildren();
      const state = recentState(storage);
      if (!state.queries.length && !state.selections.length) return;
      recent.append(element(documentObject, "h3", "", "Recent"));
      const wrap = element(documentObject, "div", "product-recent-items");
      for (const query of state.queries.slice(0, 4)) {
        const button = element(documentObject, "button", "", query);
        button.type = "button";
        button.addEventListener("click", () => { input.value = query; runSearch(); input.focus(); });
        wrap.append(button);
      }
      for (const item of state.selections.slice(0, 4)) {
        const link = element(documentObject, "a", "", item.title);
        link.href = item.route;
        wrap.append(link);
      }
      recent.append(wrap);
    }

    function open() {
      renderRecent();
      dialog.showModal();
      root.setTimeout(() => { input.focus(); runSearch(); }, 0);
    }

    input.addEventListener("input", runSearch);
    input.addEventListener("keydown", (event) => {
      if (!activeButtons.length) return;
      if (event.key === "ArrowDown") {
        event.preventDefault(); activeIndex = (activeIndex + 1) % activeButtons.length; activeButtons[activeIndex].focus();
      } else if (event.key === "ArrowUp") {
        event.preventDefault(); activeIndex = (activeIndex - 1 + activeButtons.length) % activeButtons.length; activeButtons[activeIndex].focus();
      }
    });
    results.addEventListener("keydown", (event) => {
      const index = activeButtons.indexOf(documentObject.activeElement);
      if (index < 0) return;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        activeIndex = (index + step + activeButtons.length) % activeButtons.length;
        activeButtons[activeIndex].focus();
      }
    });
    root.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); open();
      }
    });
    const button = element(documentObject, "button", "product-utility-button product-search-open", "Global search");
    button.type = "button";
    button.setAttribute("aria-keyshortcuts", "Control+K Meta+K");
    button.addEventListener("click", open);
    utilityBar.prepend(button);
  }

  function todayState(storage) {
    const value = readStorage(storage, TODAY_STATE_KEY, { version: 1, items: {} });
    return value?.version === 1 && value.items && typeof value.items === "object" ? value : { version: 1, items: {} };
  }

  function todayHidden(storage, card, now = Date.now()) {
    if (card.safety_critical || !card.dismissible) return false;
    const state = todayState(storage).items[card.id];
    if (!state) return false;
    if (state.kind === "dismiss") return true;
    if (state.kind === "snooze") return Number(state.until || 0) > now;
    return false;
  }

  function saveTodayState(storage, cardId, value) {
    const state = todayState(storage);
    state.items[cardId] = value;
    writeStorage(storage, TODAY_STATE_KEY, state);
  }

  function cardStillCurrent(card) {
    if (card.kind !== "current") return true;
    return runtimeFresh({
      freshness: card.freshness,
      dataset_timestamp: card.dataset_timestamp,
      validity: { valid_until: card.deadline },
    });
  }

  function renderCard(root, card, rerender) {
    const documentObject = root.document;
    const article = element(documentObject, "article", "product-action-card ds-card");
    if (card.safety_critical) article.dataset.safetyCritical = "true";
    if (card.kind === "current") article.id = `current-${String(card.id).split(":")[1] || "data"}`;
    const header = element(documentObject, "header", "product-card-header");
    header.append(element(documentObject, "h3", "", card.title));
    const layer = element(documentObject, "span", "ds-source-chip", card.evidence_layer || card.kind);
    header.append(layer);
    article.append(header, element(documentObject, "p", "product-card-summary", card.summary));
    const why = element(documentObject, "div", "product-card-why");
    why.append(element(documentObject, "strong", "", "Why this is here"));
    const list = element(documentObject, "ul");
    for (const reason of card.why || []) list.append(element(documentObject, "li", "", String(reason).replaceAll("_", " ")));
    why.append(list);
    article.append(why);
    if (card.deadline) article.append(element(documentObject, "p", "product-deadline", `Deadline: ${formatDateTime(card.deadline)}`));
    if (card.reversibility) article.append(element(documentObject, "p", "product-reversibility", `Reversibility: ${card.reversibility.replaceAll("-", " ")}`));
    for (const warning of card.warnings || []) {
      const notice = element(documentObject, "p", "ds-notice product-warning", `Warning: ${String(warning).replaceAll("_", " ")}`);
      notice.dataset.kind = "warning";
      notice.dataset.safetyCritical = "true";
      article.append(notice);
    }
    const actions = element(documentObject, "div", "product-card-actions");
    if (card.route) {
      const link = element(documentObject, "a", "", "Open evidence / action");
      link.href = card.route;
      actions.append(link);
    }
    if (card.source_reference && /^https?:\/\//i.test(card.source_reference)) {
      const source = element(documentObject, "a", "", "Source");
      source.href = card.source_reference;
      source.target = "_blank";
      source.rel = "noopener noreferrer";
      actions.append(source);
    }
    if (card.dismissible && !card.safety_critical) {
      const snooze = element(documentObject, "button", "", "Snooze 24h");
      snooze.type = "button";
      snooze.addEventListener("click", () => {
        saveTodayState(root.localStorage, card.id, { kind: "snooze", until: Date.now() + 86400000 });
        rerender();
      });
      const dismiss = element(documentObject, "button", "", "Dismiss");
      dismiss.type = "button";
      dismiss.addEventListener("click", () => { saveTodayState(root.localStorage, card.id, { kind: "dismiss" }); rerender(); });
      actions.append(snooze, dismiss);
    }
    article.append(actions);
    return article;
  }

  async function installToday(root) {
    const documentObject = root.document;
    const mount = documentObject.getElementById("today-root");
    if (!mount) return;
    try {
      const response = await root.fetch("data/today.json");
      if (!response.ok) throw new Error("Today data could not be loaded");
      const payload = await response.json();
      const storage = root.localStorage;
      const render = () => {
        mount.replaceChildren();
        const visible = (cards) => (cards || []).filter((card) => cardStillCurrent(card) && !todayHidden(storage, card));
        const top = visible(payload.top_actions);
        const priority = element(documentObject, "section", "product-section product-priority");
        priority.append(element(documentObject, "h2", "", "Top actions"));
        if (!top.length) priority.append(element(documentObject, "p", "ds-empty", "No actionable card is both current and visible right now."));
        else for (const card of top) priority.append(renderCard(root, card, render));
        mount.append(priority);

        const sectionDefs = [
          ["now", "Now"],
          ["my_collection", "My collection"],
          ["build_opportunities", "Build opportunities"],
          ["event_prep", "Event prep"],
          ["roster_gaps", "Roster gaps"],
        ];
        const grid = element(documentObject, "div", "today-grid");
        for (const [key, label] of sectionDefs) {
          const data = payload.sections?.[key] || {};
          const section = element(documentObject, "section", "product-section");
          section.append(element(documentObject, "h2", "", label));
          const cards = visible(data.cards);
          if (cards.length) for (const card of cards) section.append(renderCard(root, card, render));
          else section.append(element(documentObject, "p", "ds-empty", data.empty_message || "Nothing to show."));
          if (data.planned_dependency) {
            const note = element(documentObject, "p", "product-muted", `Planned dependency: ${data.planned_dependency}`);
            note.dataset.guidanceMin = "detailed";
            section.append(note);
          }
          grid.append(section);
        }
        mount.append(grid);

        const health = payload.sections?.data_health || {};
        const healthSection = element(documentObject, "section", "product-section product-data-health");
        healthSection.dataset.safetyCritical = "true";
        healthSection.append(element(documentObject, "h2", "", "Data health"));
        if (!(health.blockers || []).length) healthSection.append(element(documentObject, "p", "ds-notice", "No elevated scan-health blockers in the published health resource."));
        for (const blocker of health.blockers || []) {
          const row = element(documentObject, "p", "ds-notice", `${blocker.count} ${blocker.label}`);
          row.dataset.kind = "warning";
          row.dataset.safetyCritical = "true";
          if (blocker.route) {
            const link = element(documentObject, "a", "", " Review");
            link.href = blocker.route;
            row.append(link);
          }
          healthSection.append(row);
        }
        mount.append(healthSection);
      };
      render();
    } catch (error) {
      mount.replaceChildren(element(documentObject, "p", "ds-notice", error?.message || "Today is unavailable."));
    }
  }

  function matchesReferenceQuery(item, params) {
    const type = params.get("type");
    if (type && !(item.types || []).some((value) => String(value).toLocaleLowerCase() === type.toLocaleLowerCase())) return false;
    const family = params.get("family");
    if (family && String(item.family_id || "") !== family) return false;
    const query = params.get("search");
    if (query) {
      const haystack = [item.display_name, item.base_name, item.form_label, item.form_key, ...(item.form_aliases || []), ...(item.types || [])].join(" ").toLocaleLowerCase();
      if (!String(query).toLocaleLowerCase().split(/\s+/).every((term) => haystack.includes(term))) return false;
    }
    return true;
  }

  function factMatchesSpecies(value, speciesId, dex) {
    if (Array.isArray(value)) return value.some((item) => factMatchesSpecies(item, speciesId, dex));
    if (!value || typeof value !== "object") return false;
    for (const [key, child] of Object.entries(value)) {
      const normalized = key.toLocaleLowerCase();
      if (["species_id", "pokemon_id"].includes(normalized) && String(child) === String(speciesId)) return true;
      if (["dex", "pokemon_number", "boss_dex"].includes(normalized) && Number(child) === Number(dex)) return true;
      if (["featured_dex", "boss_dexes"].includes(normalized) && Array.isArray(child) && child.some((item) => Number(item) === Number(dex))) return true;
      if (factMatchesSpecies(child, speciesId, dex)) return true;
    }
    return false;
  }

  function renderJsonSummary(documentObject, value, className = "product-json-summary") {
    const pre = element(documentObject, "pre", className);
    pre.textContent = JSON.stringify(value, null, 2);
    return pre;
  }

  async function freshSpeciesFacts(root, speciesId, dex) {
    try {
      const indexResponse = await root.fetch("data/external/index.json");
      if (!indexResponse.ok) return { status: "unavailable", facts: [], reason: "Current-data index unavailable." };
      const index = await indexResponse.json();
      const fresh = (index.snapshots || []).filter(runtimeFresh);
      const groups = await Promise.all(fresh.map(async (snapshot) => {
        try {
          const response = await root.fetch(snapshot.path);
          if (!response.ok) return [];
          const payload = await response.json();
          return (payload.facts || []).filter((fact) => factMatchesSpecies(fact, speciesId, dex)).map((fact) => ({ snapshot, fact }));
        } catch { return []; }
      }));
      const facts = groups.flat();
      return facts.length
        ? { status: "fresh", facts }
        : { status: "unavailable", facts: [], reason: "No fresh current snapshot contains an exact species/form fact for this entry." };
    } catch {
      return { status: "unavailable", facts: [], reason: "Current species facts could not be verified." };
    }
  }

  async function renderReferenceEntry(root, mount, index, selected) {
    const documentObject = root.document;
    const [knowledgeResponse, pokemonResponse, current] = await Promise.all([
      root.fetch(index.knowledge_resource),
      root.fetch("data/pokemon.json"),
      freshSpeciesFacts(root, selected.species_id, selected.dex),
    ]);
    if (!knowledgeResponse.ok || !pokemonResponse.ok) throw new Error("Reference knowledge or owned records could not be loaded");
    const knowledge = await knowledgeResponse.json();
    const pokemon = await pokemonResponse.json();
    const entry = (knowledge.entries || []).find((item) => String(item.species_id) === String(selected.species_id));
    if (!entry) throw new Error("The requested species/form is not present in the versioned knowledge snapshot");
    const ownedIds = new Set(selected.owned_record_ids || []);
    const owned = (pokemon.records || []).filter((record) => ownedIds.has(record.identity?.record_id));

    mount.replaceChildren();
    const heading = element(documentObject, "section", "reference-heading ds-card");
    heading.append(element(documentObject, "p", "product-eyebrow", `#${String(entry.dex).padStart(4, "0")} · Stable reference`));
    heading.append(element(documentObject, "h2", "", entry.display_name));
    heading.append(element(documentObject, "p", "", `${entry.form_label || "Normal"} · ${(entry.types || []).join(" / ") || "Type unknown"}`));
    const evidence = element(documentObject, "div", "ds-toolbar");
    evidence.append(element(documentObject, "span", "ds-source-chip", `${knowledge.classification || "Versioned data"} · ${knowledge.dataset_version || "unknown version"}`));
    if (owned.length) evidence.append(element(documentObject, "span", "ds-status", `${owned.length} owned`));
    heading.append(evidence);
    mount.append(heading);

    const basics = element(documentObject, "section", "product-section reference-stable");
    basics.append(element(documentObject, "h2", "", "Stable facts"));
    const dl = element(documentObject, "dl", "product-kv-list");
    appendTextRow(documentObject, dl, "Canonical species ID", entry.species_id);
    appendTextRow(documentObject, dl, "Types", (entry.types || []).join(" / "));
    appendTextRow(documentObject, dl, "Base Attack", entry.base_stats?.attack);
    appendTextRow(documentObject, dl, "Base Defense", entry.base_stats?.defense);
    appendTextRow(documentObject, dl, "Base Stamina", entry.base_stats?.stamina);
    appendTextRow(documentObject, dl, "Released", entry.released ? "Yes" : "No");
    basics.append(dl);
    mount.append(basics);

    const planning = element(documentObject, "section", "product-section reference-planning");
    planning.dataset.guidanceMin = "detailed";
    const planningTitle = element(documentObject, "h2", "", "Evolution and planning");
    planningTitle.append(termButton(documentObject, "Mega / Max"));
    planning.append(planningTitle);
    const planningDl = element(documentObject, "dl", "product-kv-list");
    appendTextRow(documentObject, planningDl, "Buddy distance", entry.buddy_distance_km == null ? "Unknown" : `${entry.buddy_distance_km} km`);
    appendTextRow(documentObject, planningDl, "Shadow eligible", String(entry.shadow_eligible));
    appendTextRow(documentObject, planningDl, "Dynamax eligibility", entry.dynamax_eligibility == null ? "Unknown" : String(entry.dynamax_eligibility));
    appendTextRow(documentObject, planningDl, "Gigantamax eligibility", entry.gigantamax_eligibility == null ? "Unknown" : String(entry.gigantamax_eligibility));
    planning.append(planningDl);
    const familyDetails = element(documentObject, "details", "product-details");
    familyDetails.append(element(documentObject, "summary", "", "Family, evolution, transformation, and second-move data"));
    familyDetails.append(renderJsonSummary(documentObject, {
      family: entry.family,
      transformation: entry.transformation,
      transformations: entry.transformations,
      second_charged_move_cost: entry.second_charged_move_cost,
    }));
    planning.append(familyDetails);
    mount.append(planning);

    const moves = element(documentObject, "section", "product-section reference-moves");
    moves.dataset.guidanceMin = "detailed";
    moves.append(element(documentObject, "h2", "", "Moves from the stable knowledge snapshot"));
    moves.append(renderJsonSummary(documentObject, entry.moves));
    mount.append(moves);

    const ownedSection = element(documentObject, "section", "product-section reference-owned");
    const ownedTitle = element(documentObject, "h2", "", "Owned copies");
    ownedTitle.append(termButton(documentObject, "Exact IV"));
    ownedSection.append(ownedTitle);
    if (!owned.length) ownedSection.append(element(documentObject, "p", "ds-empty", "No exact owned record in the current canonical export."));
    for (const record of owned) {
      const card = element(documentObject, "article", "reference-owned-card ds-card");
      const ivs = record.ivs || {};
      card.append(element(documentObject, "h3", "", `CP ${record.cp ?? "?"} · ${ivs.attack ?? "?"}/${ivs.defense ?? "?"}/${ivs.stamina ?? "?"}`));
      const meta = element(documentObject, "p", "", `IV ${ivs.average_percent ?? "?"}% · Level ${record.level?.minimum ?? "?"} · ${record.status?.shadow_purified || "normal"}`);
      meta.append(termButton(documentObject, "IV %"));
      card.append(meta);
      const id = element(documentObject, "code", "", record.identity?.record_id || "missing record ID");
      card.append(id);
      const link = element(documentObject, "a", "", "Open exact owned record");
      link.href = `index.html?record=${encodeURIComponent(record.identity?.record_id || "")}`;
      card.append(link);
      ownedSection.append(card);
    }
    mount.append(ownedSection);

    const currentSection = element(documentObject, "section", "product-section reference-current");
    currentSection.id = "reference-current";
    currentSection.append(element(documentObject, "h2", "", "Current facts"));
    const currentInfo = element(documentObject, "p", "product-muted", "Time-sensitive facts are shown only after a live freshness re-check of the published static snapshot.");
    currentInfo.append(termButton(documentObject, "Freshness"));
    currentSection.append(currentInfo);
    if (current.status !== "fresh") {
      const unavailable = element(documentObject, "p", "ds-empty", current.reason || "No fresh current species-specific fact is available.");
      unavailable.dataset.safetyCritical = "true";
      currentSection.append(unavailable);
    } else {
      for (const pair of current.facts) {
        const article = element(documentObject, "article", "ds-card reference-current-fact");
        article.append(element(documentObject, "strong", "", `${pair.snapshot.data_category} · ${pair.snapshot.provider}`));
        article.append(element(documentObject, "p", "", `Current as of ${formatDateTime(pair.snapshot.dataset_timestamp)}`));
        const source = element(documentObject, "a", "", "Source");
        source.href = pair.snapshot.source_reference;
        source.target = "_blank";
        source.rel = "noopener noreferrer";
        article.append(source);
        const expert = renderJsonSummary(documentObject, pair.fact);
        expert.dataset.guidanceMin = "expert";
        article.append(expert);
        currentSection.append(article);
      }
    }
    mount.append(currentSection);
  }

  function renderReferenceList(root, mount, entries) {
    const documentObject = root.document;
    mount.replaceChildren();
    const section = element(documentObject, "section", "product-section");
    section.append(element(documentObject, "h2", "", `Reference results (${entries.length})`));
    const list = element(documentObject, "div", "reference-list");
    for (const item of entries.slice(0, 500)) {
      const link = element(documentObject, "a", "reference-list-item ds-card");
      link.href = item.route;
      link.append(element(documentObject, "strong", "", `#${String(item.dex).padStart(4, "0")} ${item.display_name}`));
      link.append(element(documentObject, "small", "", `${item.form_label || "Normal"} · ${(item.types || []).join(" / ")} · ${item.owned_count || 0} owned`));
      list.append(link);
    }
    section.append(list);
    if (entries.length > 500) section.append(element(documentObject, "p", "product-muted", "Showing the first 500 deterministic matches. Use Global search to narrow further."));
    mount.append(section);
  }

  async function installReference(root) {
    const mount = root.document.getElementById("reference-root");
    if (!mount) return;
    try {
      const response = await root.fetch("data/reference/index.json");
      if (!response.ok) throw new Error("Reference index could not be loaded");
      const index = await response.json();
      const params = new URL(root.location.href).searchParams;
      const speciesId = params.get("species");
      if (speciesId) {
        const selected = (index.entries || []).find((item) => String(item.species_id) === speciesId);
        if (!selected) throw new Error("Unknown canonical species/form route");
        await renderReferenceEntry(root, mount, index, selected);
      } else {
        renderReferenceList(root, mount, (index.entries || []).filter((item) => matchesReferenceQuery(item, params)));
      }
    } catch (error) {
      mount.replaceChildren(element(root.document, "p", "ds-notice", error?.message || "Reference is unavailable."));
    }
  }

  function flattenRecord(value, prefix = "", rows = []) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      for (const [key, child] of Object.entries(value)) flattenRecord(child, prefix ? `${prefix}.${key}` : key, rows);
    } else if (Array.isArray(value)) rows.push([prefix, value.join(", ")]);
    else rows.push([prefix, value == null || value === "" ? "Missing" : String(value)]);
    return rows;
  }

  async function installExactRecordRoute(root) {
    const recordId = new URL(root.location.href).searchParams.get("record");
    if (!recordId) return;
    const dialog = createDialog(root.document, "product-record-dialog", "Exact owned Pokémon record");
    const body = dialog.querySelector(".product-dialog-body");
    try {
      const response = await root.fetch("data/pokemon.json");
      if (!response.ok) throw new Error("Canonical collection could not be loaded");
      const payload = await response.json();
      const record = (payload.records || []).find((item) => String(item.identity?.record_id) === recordId);
      if (!record) throw new Error("That canonical record ID is not present in this build");
      body.replaceChildren();
      body.append(element(root.document, "h3", "", `#${String(record.pokemon_number).padStart(4, "0")} ${record.name}${record.form ? ` · ${record.form}` : ""}`));
      const summary = element(root.document, "p", "", `CP ${record.cp ?? "?"} · IV ${record.ivs?.average_percent ?? "?"}% · Level ${record.level?.minimum ?? "?"}`);
      summary.append(termButton(root.document, "IV %"));
      body.append(summary);
      const id = element(root.document, "p", "product-record-id");
      id.append(element(root.document, "strong", "", "Canonical record ID: "), element(root.document, "code", "", recordId));
      body.append(id);
      const details = element(root.document, "details", "product-details");
      details.append(element(root.document, "summary", "", "All normalized fields"));
      const dl = element(root.document, "dl", "product-kv-list");
      for (const [key, value] of flattenRecord(record)) appendTextRow(root.document, dl, key, value);
      details.append(dl);
      body.append(details);
      const ref = element(root.document, "a", "", "Open species reference");
      ref.href = `reference.html?search=${encodeURIComponent(record.name)}`;
      body.append(ref);
      dialog.showModal();
    } catch (error) {
      body.replaceChildren(element(root.document, "p", "ds-notice", error?.message || "Exact record unavailable."));
      dialog.showModal();
    }
  }

  function installUtilityBar(root) {
    const documentObject = root.document;
    if (documentObject.getElementById("product-utility-bar")) return documentObject.getElementById("product-utility-bar");
    const bar = element(documentObject, "nav", "product-utility-bar");
    bar.id = "product-utility-bar";
    bar.setAttribute("aria-label", "Global collection utilities");
    const today = element(documentObject, "a", "product-utility-link", "Today");
    today.href = "today.html";
    const reference = element(documentObject, "a", "product-utility-link", "Reference");
    reference.href = "reference.html";
    bar.append(today, reference);
    const header = documentObject.querySelector(".site-header, .product-page-header, header");
    if (header) header.after(bar); else documentObject.body.prepend(bar);
    return bar;
  }

  function install(root) {
    const utilityBar = installUtilityBar(root);
    installGlossary(root);
    installGuidance(root, utilityBar);
    installGlobalSearch(root, utilityBar);
    installExactRecordRoute(root);
    installToday(root);
    installReference(root);
  }

  return {
    GUIDANCE_KEY,
    ONBOARDING_KEY,
    RECENT_KEY,
    TODAY_STATE_KEY,
    GLOSSARY,
    normalizeGuidance,
    runtimeFresh,
    scoreSearchItem,
    currentSearchItemAllowed,
    factMatchesSpecies,
    matchesReferenceQuery,
    install,
  };
});
