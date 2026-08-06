"use strict";

(function exposeDashboard(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) {
    root.CollectionDashboard = api;
    root.CollectionSummaryPresets = api.SummaryPresets;
    root.CollectionUsability = api.Usability;
  }
  if (root?.document) api.install(root);
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const SEARCH_DELAY_MS = 100;
  const COLUMN_STORAGE_KEY = "pokemon-go-collection:columns:v1";
  const COLUMN_ORDER = Object.freeze(["pokemon", "cp", "iv", "level", "moves", "status", "pvp", "dates"]);
  const DEFAULT_COLUMNS = Object.freeze(["pokemon", "cp", "iv", "level", "status", "pvp"]);
  const QUALIFIED_FIELDS = new Set(["name", "form", "move", "cp", "iv", "level", "status", "pvp", "rank"]);
  const DEFAULT_SORT_TEXTS = new Set(["CP ↓", "1. CP ↓"]);
  const DRAWER_IDS = ["advanced-filters", "sort-details"];
  const SIMPLE_DEFAULTS = Object.freeze({
    search: "",
    "species-filter": "",
    "form-filter": "",
    "gender-filter": "any",
    "status-filter": "any",
    "lucky-filter": "any",
    "favorite-filter": "any",
    "pvp-marked-filter": "any",
    "hundo-filter": "any",
    "nundo-filter": "any",
    "second-move-filter": "any",
    "data-quality-filter": "any",
    "fast-move-filter": "",
    "charged-move-filter": "",
    "evolution-filter": "",
    "pvp-status-filter": "any",
    "league-filter": "great",
    "pvp-eligibility-filter": "any",
  });

  const metrics = {
    searchEventsSuppressed: 0,
    searchDispatches: 0,
    searchCacheBuilds: 0,
    searchCacheHits: 0,
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function normalizeWhitespace(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function isMissing(value) {
    return value === null || value === undefined || value === "";
  }

  function numericText(element) {
    return Number(String(element?.textContent || "").replace(/[^0-9.-]/g, ""));
  }

  function dispatchInput(element, root) {
    element.dispatchEvent(new root.Event("input", { bubbles: true }));
  }

  function clickWithShift(element, root) {
    element.dispatchEvent(new root.MouseEvent("click", { bubbles: true, shiftKey: true }));
  }

  function parseNumericConstraint(value, limits = {}) {
    const text = String(value || "").trim();
    let minimum;
    let maximum;
    let match = text.match(/^(\d+(?:\.\d+)?)$/);
    if (match) {
      minimum = Number(match[1]);
      maximum = minimum;
    } else if ((match = text.match(/^(\d+(?:\.\d+)?)\+$/))) {
      minimum = Number(match[1]);
      maximum = null;
    } else if ((match = text.match(/^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$/))) {
      minimum = Number(match[1]);
      maximum = Number(match[2]);
    } else {
      return null;
    }
    if (!Number.isFinite(minimum) || (maximum !== null && !Number.isFinite(maximum))) return null;
    if (maximum !== null && minimum > maximum) return null;
    if (limits.integer && (!Number.isInteger(minimum) || (maximum !== null && !Number.isInteger(maximum)))) return null;
    if (limits.minimum !== undefined && minimum < limits.minimum) return null;
    if (limits.maximum !== undefined && (minimum > limits.maximum || (maximum !== null && maximum > limits.maximum))) return null;
    return { minimum, maximum };
  }

  function validQualifiedValue(field, value) {
    const text = String(value || "").trim();
    if (!text) return false;
    if (["name", "form", "move"].includes(field)) return true;
    if (field === "status") {
      return new Set(["normal", "shadow", "purified", "lucky", "favorite", "hundo", "nundo", "pvp-marked"]).has(text.toLocaleLowerCase());
    }
    if (field === "pvp") return new Set(["great", "ultra", "little"]).has(text.toLocaleLowerCase());
    if (field === "rank" && ["ranked", "unranked"].includes(text.toLocaleLowerCase())) return true;
    if (field === "cp") return Boolean(parseNumericConstraint(text, { minimum: 0, integer: true }));
    if (field === "iv") return Boolean(parseNumericConstraint(text, { minimum: 0, maximum: 100 }));
    if (field === "level") return Boolean(parseNumericConstraint(text, { minimum: 0, maximum: 60 }));
    if (field === "rank") return Boolean(parseNumericConstraint(text, { minimum: 1, integer: true }));
    return false;
  }

  function parseQualifiedQuery(query) {
    const qualified = [];
    const plainParts = [];
    const invalid = [];
    const expression = /(-?)(?:([a-z][a-z-]*):(?:"([^"]*)"|(\S+))|"([^"]+)"|(\S+))/gi;
    let match;
    while ((match = expression.exec(String(query || ""))) !== null) {
      const negated = match[1] === "-";
      const field = String(match[2] || "").toLocaleLowerCase();
      const fieldValue = match[3] ?? match[4];
      const quotedPlain = match[5];
      const barePlain = match[6];
      if (field && QUALIFIED_FIELDS.has(field)) {
        if (validQualifiedValue(field, fieldValue)) {
          qualified.push({ field, value: String(fieldValue).trim(), negated });
        } else {
          invalid.push(match[0]);
          plainParts.push(match[0]);
        }
      } else if (field) {
        plainParts.push(match[0]);
      } else if (quotedPlain !== undefined) {
        plainParts.push(`${negated ? "-" : ""}"${quotedPlain}"`);
      } else if (barePlain) {
        plainParts.push(`${negated ? "-" : ""}${barePlain}`);
      }
    }
    return {
      qualified,
      plainQuery: plainParts.join(" "),
      invalid,
    };
  }

  function numberMatches(value, constraint) {
    if (!constraint || isMissing(value)) return false;
    const number = Number(value);
    if (!Number.isFinite(number) || number < constraint.minimum) return false;
    return constraint.maximum === null || number <= constraint.maximum;
  }

  function textContains(value, expected) {
    return String(value || "").toLocaleLowerCase().includes(String(expected || "").toLocaleLowerCase());
  }

  function matchesQualifiedTerm(record, term, selectedLeague = "great") {
    const value = term.value.toLocaleLowerCase();
    let matched = false;
    switch (term.field) {
      case "name":
        matched = textContains(record.name, value);
        break;
      case "form":
        matched = textContains(record.form, value);
        break;
      case "move":
        matched = textContains(
          [record.moves?.fast, record.moves?.charged, record.moves?.charged_second].filter(Boolean).join(" "),
          value,
        );
        break;
      case "cp":
        matched = numberMatches(record.cp, parseNumericConstraint(value, { minimum: 0, integer: true }));
        break;
      case "iv":
        matched = numberMatches(record.ivs?.average_percent, parseNumericConstraint(value, { minimum: 0, maximum: 100 }));
        break;
      case "level":
        matched = numberMatches(record.level?.minimum, parseNumericConstraint(value, { minimum: 0, maximum: 60 }));
        break;
      case "status":
        if (["normal", "shadow", "purified"].includes(value)) matched = record.status?.shadow_purified === value;
        else if (value === "lucky") matched = Boolean(record.status?.lucky);
        else if (value === "favorite") matched = Boolean(record.status?.favorite);
        else if (value === "hundo") matched = Boolean(record.ivs?.is_hundo);
        else if (value === "nundo") matched = Boolean(record.ivs?.is_nundo);
        else if (value === "pvp-marked") matched = Boolean(record.status?.marked_for_pvp);
        break;
      case "pvp":
        matched = !isMissing(record.pvp?.[value]?.rank_percent);
        break;
      case "rank": {
        const rank = record.pvp?.[selectedLeague]?.rank_number;
        if (value === "ranked") matched = !isMissing(rank);
        else if (value === "unranked") matched = isMissing(rank);
        else matched = numberMatches(rank, parseNumericConstraint(value, { minimum: 1, integer: true }));
        break;
      }
      default:
        matched = true;
    }
    return term.negated ? !matched : matched;
  }

  function installQualifiedSearch(engine) {
    if (!engine || engine.__qualifiedSearchInstalled) return null;
    const originalMatchesRecord = engine.matchesRecord;
    engine.matchesRecord = function matchesRecordWithQualifiedSearch(record, filters = {}) {
      const parsed = parseQualifiedQuery(filters.query || "");
      const league = ["great", "ultra", "little"].includes(filters.league) ? filters.league : "great";
      if (!parsed.qualified.every((term) => matchesQualifiedTerm(record, term, league))) return false;
      return originalMatchesRecord(record, { ...filters, query: parsed.plainQuery });
    };
    Object.defineProperty(engine, "__qualifiedSearchInstalled", { value: true, configurable: true });
    return { originalMatchesRecord };
  }

  function queryMatchesCachedText(engine, record, query, cache) {
    const parsed = engine.parseSearchQuery(query);
    if (!parsed.positive.length && !parsed.negative.length) return true;
    let haystack = cache.get(record);
    if (haystack === undefined) {
      haystack = engine.recordSearchText(record);
      cache.set(record, haystack);
      metrics.searchCacheBuilds += 1;
    } else {
      metrics.searchCacheHits += 1;
    }
    return parsed.positive.every((term) => haystack.includes(term)) &&
      parsed.negative.every((term) => !haystack.includes(term));
  }

  function installSearchCache(engine) {
    if (!engine || engine.__dashboardSearchCacheInstalled) return null;
    const originalMatchesRecord = engine.matchesRecord;
    const cache = new WeakMap();
    engine.matchesRecord = function matchesRecordWithCachedSearch(record, filters = {}) {
      const query = String(filters.query || "").trim();
      if (query) {
        const plainQuery = parseQualifiedQuery(query).plainQuery;
        if (plainQuery && !queryMatchesCachedText(engine, record, plainQuery, cache)) return false;
      }
      return originalMatchesRecord(record, filters);
    };
    Object.defineProperty(engine, "__dashboardSearchCacheInstalled", { value: true, configurable: true });
    return { cache, originalMatchesRecord };
  }

  function clearFilterControls(documentObject) {
    const pageSize = documentObject.getElementById("page-size")?.value || "50";
    for (const [id, defaultValue] of Object.entries(SIMPLE_DEFAULTS)) {
      const control = documentObject.getElementById(id);
      if (control) control.value = defaultValue;
    }
    documentObject.querySelectorAll("#advanced-filters input[type='number'], #advanced-filters input[type='date']")
      .forEach((control) => { control.value = ""; });
    const pageSizeControl = documentObject.getElementById("page-size");
    if (pageSizeControl) pageSizeControl.value = pageSize;
    const preset = documentObject.getElementById("preset-select");
    if (preset) preset.value = "";
  }

  function isDefaultSortDescription(value) {
    return DEFAULT_SORT_TEXTS.has(normalizeWhitespace(value));
  }

  function removeFilterLabel(label) {
    return `Remove ${normalizeWhitespace(label)} filter`;
  }

  function installDrawerGuard(documentObject, windowObject) {
    const allowed = new WeakSet();
    const drawers = DRAWER_IDS.map((id) => documentObject.getElementById(id)).filter(Boolean);

    function directSummary(target) {
      const summary = target?.closest?.("summary");
      if (!summary) return null;
      const drawer = summary.parentElement;
      return drawers.includes(drawer) && drawer.firstElementChild === summary ? drawer : null;
    }

    function allowFromEvent(event) {
      const drawer = directSummary(event.target);
      if (!drawer) return;
      if (event.type === "keydown" && !["Enter", " "].includes(event.key)) return;
      allowed.add(drawer);
      windowObject.setTimeout(() => allowed.delete(drawer), 0);
    }

    documentObject.addEventListener("pointerdown", allowFromEvent, true);
    documentObject.addEventListener("click", allowFromEvent, true);
    documentObject.addEventListener("keydown", allowFromEvent, true);

    for (const drawer of drawers) {
      new MutationObserver(() => {
        if (!drawer.open) return;
        if (allowed.has(drawer)) {
          allowed.delete(drawer);
          return;
        }
        drawer.open = false;
      }).observe(drawer, { attributes: true, attributeFilter: ["open"] });
    }
  }

  function installDebouncedSearch(documentObject, windowObject) {
    let timer = 0;
    let dispatching = false;
    let latestTarget = null;

    function updateSyntaxStatus(target) {
      const status = documentObject.getElementById("search-syntax-status");
      if (!status) return;
      const parsed = parseQualifiedQuery(target?.value || "");
      status.textContent = parsed.invalid.length
        ? `Malformed qualified terms are being treated as ordinary text: ${parsed.invalid.join(", ")}`
        : "";
    }

    function dispatchSearch() {
      if (!latestTarget) return;
      windowObject.clearTimeout(timer);
      timer = 0;
      dispatching = true;
      metrics.searchDispatches += 1;
      latestTarget.dispatchEvent(new windowObject.Event("input", { bubbles: true }));
      dispatching = false;
    }

    documentObject.addEventListener("input", (event) => {
      if (event.target?.id !== "search" || dispatching) return;
      event.stopImmediatePropagation();
      latestTarget = event.target;
      updateSyntaxStatus(latestTarget);
      metrics.searchEventsSuppressed += 1;
      windowObject.clearTimeout(timer);
      timer = windowObject.setTimeout(dispatchSearch, SEARCH_DELAY_MS);
    }, true);

    documentObject.addEventListener("keydown", (event) => {
      if (event.target?.id === "search" && event.key === "Enter" && timer) dispatchSearch();
    }, true);
    documentObject.addEventListener("focusout", (event) => {
      if (event.target?.id === "search" && timer) dispatchSearch();
    }, true);
    documentObject.addEventListener("search", (event) => {
      if (event.target?.id === "search" && timer) dispatchSearch();
    }, true);
  }

  function normalizeColumnPreference(value) {
    const candidates = Array.isArray(value) ? value : [];
    const selected = new Set(candidates.filter((key) => COLUMN_ORDER.includes(key)));
    selected.add("pokemon");
    if (selected.size === 1) DEFAULT_COLUMNS.forEach((key) => selected.add(key));
    return COLUMN_ORDER.filter((key) => selected.has(key));
  }

  function loadColumnPreference(storage) {
    try {
      const raw = storage?.getItem(COLUMN_STORAGE_KEY);
      return raw ? normalizeColumnPreference(JSON.parse(raw)) : [...DEFAULT_COLUMNS];
    } catch {
      return [...DEFAULT_COLUMNS];
    }
  }

  function saveColumnPreference(storage, columns) {
    try {
      storage?.setItem(COLUMN_STORAGE_KEY, JSON.stringify(normalizeColumnPreference(columns)));
      return true;
    } catch {
      return false;
    }
  }

  function applyColumnVisibility(documentObject, visibleColumns) {
    const visible = new Set(normalizeColumnPreference(visibleColumns));
    documentObject.querySelectorAll("thead [data-column]").forEach((cell) => {
      cell.dataset.columnHidden = String(!visible.has(cell.dataset.column));
    });
    documentObject.querySelectorAll("#pokemon-body tr").forEach((row) => {
      [...row.cells].forEach((cell, index) => {
        const key = COLUMN_ORDER[index];
        if (!key) return;
        cell.dataset.column = key;
        cell.dataset.columnHidden = String(!visible.has(key));
      });
    });
    const table = documentObject.querySelector(".table-card table");
    if (table) table.dataset.visibleColumns = String(visible.size);
    documentObject.querySelectorAll("[data-column-toggle]").forEach((input) => {
      input.checked = visible.has(input.dataset.columnToggle);
    });
    return [...visible];
  }

  function installColumns(documentObject, windowObject) {
    const body = documentObject.getElementById("pokemon-body");
    const controls = [...documentObject.querySelectorAll("[data-column-toggle]")];
    if (!body || !controls.length) return;
    let visible = loadColumnPreference(windowObject.localStorage);

    const apply = () => { visible = applyColumnVisibility(documentObject, visible); };
    apply();
    new MutationObserver(apply).observe(body, { childList: true, subtree: true });

    controls.forEach((input) => input.addEventListener("change", () => {
      const selected = controls.filter((control) => control.checked).map((control) => control.dataset.columnToggle);
      visible = normalizeColumnPreference(selected);
      saveColumnPreference(windowObject.localStorage, visible);
      apply();
    }));

    documentObject.getElementById("reset-columns")?.addEventListener("click", () => {
      visible = [...DEFAULT_COLUMNS];
      saveColumnPreference(windowObject.localStorage, visible);
      apply();
      documentObject.getElementById("column-status").textContent = "Recommended columns restored";
    });

    const compact = documentObject.getElementById("sort-compact");
    const note = documentObject.getElementById("hidden-sort-note");
    const sortGroups = {
      pokemon: ["pokémon name", "form", "pokédex number", "gender"],
      cp: ["cp", "hp"],
      iv: ["iv %", "iv total", "attack iv", "defense iv", "hp iv"],
      level: ["minimum level", "maximum level", "power-up dust"],
      moves: ["fast move", "charged move"],
      status: ["shadow status", "lucky", "favorite", "poke genie pvp mark", "weight", "height"],
      pvp: ["pvp percentile", "pvp rank number", "pvp stat product", "pvp build dust", "pvp build candy"],
      dates: ["catch date", "scan date", "original scan date"],
    };
    const updateHiddenSort = () => {
      if (!compact || !note) return;
      const description = compact.textContent.toLocaleLowerCase();
      const hidden = Object.entries(sortGroups)
        .filter(([column, labels]) => !visible.includes(column) && labels.some((label) => description.includes(label)))
        .map(([column]) => column);
      note.textContent = hidden.length ? `Sorting uses hidden column${hidden.length > 1 ? "s" : ""}: ${hidden.join(", ")}. The active sort chip remains visible.` : "";
    };
    updateHiddenSort();
    if (compact) new MutationObserver(updateHiddenSort).observe(compact, { childList: true, subtree: true });
    controls.forEach((input) => input.addEventListener("change", updateHiddenSort));
  }

  function installClearAndReset(documentObject, windowObject) {
    const clearButton = documentObject.getElementById("reset-filters");
    if (clearButton) {
      clearButton.textContent = "Clear filters";
      clearButton.setAttribute("aria-label", "Clear all search and filter criteria");
    }

    const resetView = documentObject.getElementById("reset-view");
    resetView?.addEventListener("click", () => {
      try { windowObject.localStorage.removeItem(COLUMN_STORAGE_KEY); } catch { /* Ignore unavailable storage. */ }
      windowObject.location.replace(windowObject.location.pathname);
    });

    documentObject.addEventListener("click", (event) => {
      const button = event.target?.closest?.("#reset-filters");
      if (!button || !event.isTrusted) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      clearFilterControls(documentObject);
      const immediateControl = documentObject.getElementById("status-filter");
      immediateControl?.dispatchEvent(new windowObject.Event("input", { bubbles: true }));
      const status = documentObject.getElementById("filter-change-status");
      if (status) status.textContent = "All search and filter criteria cleared";
    }, true);
  }

  function installFilterChipAccessibility(documentObject) {
    const container = documentObject.getElementById("active-filters");
    if (!container) return;
    container.removeAttribute("aria-live");
    container.setAttribute("aria-label", "Active filters");

    const status = documentObject.getElementById("filter-change-status");
    function labels() {
      return new Set([...container.querySelectorAll(".filter-chip")].map((button) => {
        const label = normalizeWhitespace(button.querySelector("span")?.textContent || button.textContent);
        button.setAttribute("aria-label", removeFilterLabel(label));
        button.setAttribute("title", removeFilterLabel(label));
        return label;
      }));
    }

    let previous = labels();
    new MutationObserver(() => {
      const current = labels();
      const added = [...current].filter((label) => !previous.has(label));
      const removed = [...previous].filter((label) => !current.has(label));
      if (status) {
        if (added.length === 1 && removed.length === 0) status.textContent = `Applied ${added[0]} filter`;
        else if (removed.length === 1 && added.length === 0) status.textContent = `Removed ${removed[0]} filter`;
        else if (added.length || removed.length) status.textContent = "Active filters updated";
      }
      previous = current;
    }).observe(container, { childList: true, subtree: true });
  }

  function installSortStatusChip(documentObject) {
    const compact = documentObject.getElementById("sort-compact");
    const chip = documentObject.getElementById("sort-status-chip");
    const sortDrawerSummary = documentObject.querySelector("#sort-details > summary");
    if (!compact || !chip || !sortDrawerSummary) return;
    chip.addEventListener("click", () => sortDrawerSummary.click());
    const update = () => {
      const description = normalizeWhitespace(compact.textContent);
      const isDefault = isDefaultSortDescription(description);
      chip.hidden = isDefault;
      chip.textContent = isDefault ? "" : `Sort: ${description}`;
      chip.setAttribute("aria-label", `Edit sort order: ${description}`);
    };
    update();
    new MutationObserver(update).observe(compact, { childList: true, subtree: true });
  }

  function resetPreservingPageSize(documentObject, root) {
    const pageSize = documentObject.getElementById("page-size");
    const savedPageSize = pageSize?.value;
    documentObject.getElementById("reset-filters")?.click();
    if (pageSize && savedPageSize && pageSize.value !== savedPageSize) {
      pageSize.value = savedPageSize;
      dispatchInput(pageSize, root);
    }
  }

  function announce(documentObject, message) {
    const status = documentObject.getElementById("summary-shortcut-status");
    if (status) status.textContent = message;
  }

  function applySummaryPreset(documentObject, root, preset) {
    if (!documentObject.getElementById("reset-filters")) return false;
    resetPreservingPageSize(documentObject, root);
    switch (preset) {
      case "all":
        announce(documentObject, `Showing all ${documentObject.getElementById("total-count")?.textContent || ""} Pokémon.`);
        return true;
      case "species": {
        const nameHeader = documentObject.querySelector('[data-sort-key="name"]');
        const cpHeader = documentObject.querySelector('[data-sort-key="cp"]');
        nameHeader?.click();
        if (cpHeader) clickWithShift(cpHeader, root);
        announce(documentObject, "Grouped by species and form, with highest CP first within each group.");
        return true;
      }
      case "hundos": {
        const control = documentObject.getElementById("hundo-filter");
        if (!control) return false;
        control.value = "yes";
        dispatchInput(control, root);
        announce(documentObject, `Showing ${documentObject.getElementById("hundo-count")?.textContent || ""} hundos.`);
        return true;
      }
      case "shadows": {
        const control = documentObject.getElementById("status-filter");
        if (!control) return false;
        control.value = "shadow";
        dispatchInput(control, root);
        announce(documentObject, `Showing ${documentObject.getElementById("shadow-count")?.textContent || ""} Shadow Pokémon.`);
        return true;
      }
      case "lucky": {
        const control = documentObject.getElementById("lucky-filter");
        if (!control) return false;
        control.value = "yes";
        dispatchInput(control, root);
        announce(documentObject, `Showing ${documentObject.getElementById("lucky-count")?.textContent || ""} Lucky Pokémon.`);
        return true;
      }
      case "max-cp": {
        const maximum = numericText(documentObject.getElementById("highest-cp"));
        const minimumControl = documentObject.getElementById("cp-min");
        const maximumControl = documentObject.getElementById("cp-max");
        if (!Number.isFinite(maximum) || !minimumControl || !maximumControl) return false;
        minimumControl.value = String(maximum);
        maximumControl.value = String(maximum);
        dispatchInput(maximumControl, root);
        announce(documentObject, `Showing Pokémon at ${maximum.toLocaleString()} CP, the collection maximum.`);
        return true;
      }
      default:
        return false;
    }
  }

  function installSummaryPresets(documentObject, root) {
    documentObject.querySelectorAll("[data-summary-preset]").forEach((button) => {
      button.addEventListener("click", () => applySummaryPreset(documentObject, root, button.dataset.summaryPreset));
    });
  }

  async function copyText(documentObject, windowObject, text) {
    if (windowObject.navigator.clipboard?.writeText) {
      try {
        await windowObject.navigator.clipboard.writeText(text);
        return;
      } catch { /* Fall through to selection-based copying. */ }
    }
    const textarea = documentObject.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    documentObject.body.append(textarea);
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);
    const copied = documentObject.execCommand("copy");
    textarea.remove();
    if (!copied) throw new Error("Copy command failed");
  }

  function installTrainerCopy(documentObject, windowObject) {
    const button = documentObject.getElementById("copy-friend-code");
    const status = documentObject.getElementById("friend-code-status");
    if (!button || !status) return;
    button.addEventListener("click", async () => {
      try {
        await copyText(documentObject, windowObject, button.dataset.friendCode || "");
        status.textContent = "Copied";
        button.dataset.copied = "true";
        windowObject.clearTimeout(button.friendCodeStatusTimer);
        button.friendCodeStatusTimer = windowObject.setTimeout(() => {
          status.textContent = "";
          delete button.dataset.copied;
        }, 2500);
      } catch {
        status.textContent = "Copy failed";
        delete button.dataset.copied;
      }
    });
  }

  function formatTimestamp(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value || "Unknown") : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  }

  function renderDataHealth(panel, data) {
    const counts = data.counts || {};
    const links = data.links || {};
    const item = (key, label) => {
      const count = Number(counts[key] || 0);
      const content = `<strong>${count.toLocaleString()}</strong><span>${escapeHtml(label)}</span>`;
      return links[key]
        ? `<a class="health-item" href="${escapeHtml(links[key])}">${content}</a>`
        : `<span class="health-item">${content}</span>`;
    };
    panel.dataset.state = data.build?.error_count > 0 || data.build?.warning_count > 0 || data.source?.unknown_column_count > 0 ? "warning" : "healthy";
    panel.innerHTML = `<h3>Data Health</h3>
      <div class="health-meta">
        <span><strong>Export:</strong> ${escapeHtml(data.source?.filename || "Unknown")}</span>
        <span><strong>Export timestamp:</strong> ${escapeHtml(data.source?.export_timestamp || "Unknown")} (${escapeHtml(data.source?.timestamp_basis || "filename timestamp")})</span>
        <span><strong>Built:</strong> ${escapeHtml(formatTimestamp(data.build?.generated_at_utc))}</span>
        <span><strong>Parser:</strong> ${escapeHtml(data.build?.export_schema_version || "Unknown")} · normalized ${escapeHtml(data.build?.normalized_schema_version || "Unknown")}</span>
      </div>
      <div class="health-grid">
        ${item("records", "records")}
        ${item("incomplete_scans", "incomplete scans")}
        ${item("missing_ivs", "missing IV fields")}
        ${item("missing_levels", "missing level fields")}
        ${item("missing_moves", "missing move fields")}
        ${item("missing_selected_pvp", `missing ${escapeHtml(data.selected_league || "great")} PvP data`)}
        ${item("stale_scans", `scans older than ${Number(data.thresholds?.stale_scan_days || 0)} days`)}
        ${item("recent_catches", `catches in the last ${Number(data.thresholds?.recent_catch_days || 0)} days`)}
      </div>
      <p class="insight-note">Build warnings: ${Number(data.build?.warning_count || 0).toLocaleString()} · errors: ${Number(data.build?.error_count || 0).toLocaleString()} · unknown source columns: ${Number(data.source?.unknown_column_count || 0).toLocaleString()}.</p>`;
  }

  function installDataHealth(documentObject) {
    const button = documentObject.getElementById("data-health-toggle");
    const panel = documentObject.getElementById("data-health-panel");
    if (!button || !panel) return;
    let loaded = false;
    button.addEventListener("click", async () => {
      panel.hidden = !panel.hidden;
      button.setAttribute("aria-expanded", String(!panel.hidden));
      if (panel.hidden || loaded) return;
      panel.innerHTML = '<p class="muted">Loading data health…</p>';
      try {
        const response = await fetch("data/data-health.json");
        if (!response.ok) throw new Error("Data Health could not be loaded");
        renderDataHealth(panel, await response.json());
        loaded = true;
      } catch (error) {
        panel.innerHTML = `<p class="data-health-error">${escapeHtml(error instanceof Error ? error.message : "Data Health could not be loaded")}</p>`;
      }
    });
  }

  function installUi(root) {
    const documentObject = root.document;
    installDrawerGuard(documentObject, root);
    installDebouncedSearch(documentObject, root);
    installClearAndReset(documentObject, root);
    installFilterChipAccessibility(documentObject);
    installSortStatusChip(documentObject);
    installSummaryPresets(documentObject, root);
    installTrainerCopy(documentObject, root);
    installColumns(documentObject, root);
    installDataHealth(documentObject);
  }

  function install(root) {
    installQualifiedSearch(root.CollectionFilterEngine);
    installSearchCache(root.CollectionFilterEngine);
    if (root.document.readyState === "loading") {
      root.document.addEventListener("DOMContentLoaded", () => installUi(root), { once: true });
    } else {
      installUi(root);
    }
  }

  const SummaryPresets = {
    numericText,
    resetPreservingPageSize,
    applySummaryPreset,
    install: (root) => installSummaryPresets(root.document, root),
  };

  const Usability = {
    SEARCH_DELAY_MS,
    SIMPLE_DEFAULTS,
    metrics,
    normalizeWhitespace,
    isDefaultSortDescription,
    removeFilterLabel,
    queryMatchesCachedText,
    installSearchCache,
    clearFilterControls,
  };

  const QualifiedSearch = {
    QUALIFIED_FIELDS,
    parseNumericConstraint,
    parseQualifiedQuery,
    matchesQualifiedTerm,
    installQualifiedSearch,
  };

  const Columns = {
    COLUMN_STORAGE_KEY,
    COLUMN_ORDER,
    DEFAULT_COLUMNS,
    normalizeColumnPreference,
    loadColumnPreference,
    saveColumnPreference,
    applyColumnVisibility,
  };

  return {
    SummaryPresets,
    Usability,
    QualifiedSearch,
    Columns,
    renderDataHealth,
    install,
  };
});
