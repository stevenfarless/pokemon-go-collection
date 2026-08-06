"use strict";

(function exposeUsability(root, factory) {
  const usability = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = usability;
  if (root) root.CollectionUsability = usability;
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const SEARCH_DELAY_MS = 100;
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

  function normalizeWhitespace(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function isDefaultSortDescription(value) {
    return DEFAULT_SORT_TEXTS.has(normalizeWhitespace(value));
  }

  function removeFilterLabel(label) {
    return `Remove ${normalizeWhitespace(label)} filter`;
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
    if (!engine || engine.__usabilitySearchCacheInstalled) return null;
    const originalMatchesRecord = engine.matchesRecord;
    const cache = new WeakMap();
    engine.matchesRecord = function matchesRecordWithCachedSearch(record, filters = {}) {
      const query = String(filters.query || "").trim();
      if (!query) return originalMatchesRecord(record, filters);
      if (!queryMatchesCachedText(engine, record, query, cache)) return false;
      return originalMatchesRecord(record, { ...filters, query: "" });
    };
    Object.defineProperty(engine, "__usabilitySearchCacheInstalled", {
      value: true,
      configurable: true,
    });
    return { cache, originalMatchesRecord };
  }

  function clearFilterControls(documentObject) {
    const pageSize = documentObject.getElementById("page-size")?.value || "50";
    for (const [id, defaultValue] of Object.entries(SIMPLE_DEFAULTS)) {
      const control = documentObject.getElementById(id);
      if (control) control.value = defaultValue;
    }
    documentObject.querySelectorAll(
      "#advanced-filters input[type='number'], #advanced-filters input[type='date']",
    ).forEach((control) => { control.value = ""; });
    const pageSizeControl = documentObject.getElementById("page-size");
    if (pageSizeControl) pageSizeControl.value = pageSize;
    const preset = documentObject.getElementById("preset-select");
    if (preset) preset.value = "";
  }

  function installDrawerGuard(documentObject, windowObject) {
    const allowed = new WeakSet();
    const drawers = DRAWER_IDS
      .map((id) => documentObject.getElementById(id))
      .filter(Boolean);

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

    function dispatchSearch() {
      if (!latestTarget) return;
      windowObject.clearTimeout(timer);
      timer = 0;
      dispatching = true;
      metrics.searchDispatches += 1;
      latestTarget.dispatchEvent(new Event("input", { bubbles: true }));
      dispatching = false;
    }

    documentObject.addEventListener("input", (event) => {
      if (event.target?.id !== "search" || dispatching) return;
      event.stopImmediatePropagation();
      latestTarget = event.target;
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

  function installClearAndReset(documentObject, windowObject) {
    const clearButton = documentObject.getElementById("reset-filters");
    if (clearButton) {
      clearButton.textContent = "Clear filters";
      clearButton.setAttribute("aria-label", "Clear all search and filter criteria");
    }

    const dataNav = documentObject.querySelector(".data-menu-card nav");
    if (dataNav && !documentObject.getElementById("reset-view")) {
      const resetView = documentObject.createElement("button");
      resetView.id = "reset-view";
      resetView.type = "button";
      resetView.className = "reset-view-action";
      resetView.textContent = "Reset view";
      resetView.setAttribute(
        "aria-label",
        "Reset filters, sorting, pagination, preset, and rows per page",
      );
      dataNav.append(resetView);
      resetView.addEventListener("click", () => {
        windowObject.location.replace(windowObject.location.pathname);
      });
    }

    documentObject.addEventListener("click", (event) => {
      const button = event.target?.closest?.("#reset-filters");
      if (!button) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      clearFilterControls(documentObject);
      const immediateControl = documentObject.getElementById("status-filter");
      immediateControl?.dispatchEvent(new Event("input", { bubbles: true }));
      const status = documentObject.getElementById("filter-change-status");
      if (status) status.textContent = "All search and filter criteria cleared";
    }, true);
  }

  function installFilterChipAccessibility(documentObject) {
    const container = documentObject.getElementById("active-filters");
    if (!container) return;
    container.removeAttribute("aria-live");
    container.setAttribute("aria-label", "Active filters");

    let status = documentObject.getElementById("filter-change-status");
    if (!status) {
      status = documentObject.createElement("p");
      status.id = "filter-change-status";
      status.className = "visually-hidden";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      container.after(status);
    }

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
      if (added.length === 1 && removed.length === 0) status.textContent = `Applied ${added[0]} filter`;
      else if (removed.length === 1 && added.length === 0) status.textContent = `Removed ${removed[0]} filter`;
      else if (added.length || removed.length) status.textContent = "Active filters updated";
      previous = current;
    }).observe(container, { childList: true, subtree: true });
  }

  function installSortStatusChip(documentObject) {
    const compact = documentObject.getElementById("sort-compact");
    const statusRow = documentObject.querySelector(".search-status");
    const clearButton = documentObject.getElementById("reset-filters");
    const sortDrawerSummary = documentObject.querySelector("#sort-details > summary");
    if (!compact || !statusRow || !clearButton || !sortDrawerSummary) return;

    const chip = documentObject.createElement("button");
    chip.id = "sort-status-chip";
    chip.type = "button";
    chip.className = "sort-status-chip";
    chip.hidden = true;
    statusRow.insertBefore(chip, clearButton);
    chip.addEventListener("click", () => sortDrawerSummary.click());

    function update() {
      const description = normalizeWhitespace(compact.textContent);
      const isDefault = isDefaultSortDescription(description);
      chip.hidden = isDefault;
      chip.textContent = isDefault ? "" : `Sort: ${description}`;
      chip.setAttribute("aria-label", `Edit sort order: ${description}`);
    }

    update();
    new MutationObserver(update).observe(compact, { childList: true, subtree: true });
  }

  function initialize(documentObject = document, windowObject = window) {
    installSearchCache(globalThis.CollectionFilterEngine);
    installDrawerGuard(documentObject, windowObject);
    installDebouncedSearch(documentObject, windowObject);
    installClearAndReset(documentObject, windowObject);
    installFilterChipAccessibility(documentObject);
    installSortStatusChip(documentObject);
  }

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", () => initialize(document, window));
  }

  return {
    SEARCH_DELAY_MS,
    SIMPLE_DEFAULTS,
    metrics,
    normalizeWhitespace,
    isDefaultSortDescription,
    removeFilterLabel,
    queryMatchesCachedText,
    installSearchCache,
    clearFilterControls,
    initialize,
  };
});
