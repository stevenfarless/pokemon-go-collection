"use strict";

(function exposeAccessibility(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionAccessibility = api;
  if (root?.document) api.install(root);
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const FILTER_OPTIONS_PATH = "__FILTER_OPTIONS_PATH__";
  const FOCUSABLE_SELECTOR = [
    "a[href]", "button:not([disabled])", "input:not([disabled])",
    "select:not([disabled])", "textarea:not([disabled])", "summary", "[tabindex]",
  ].join(",");

  function normalizeSortHeader(button, instructionId = "sort-instructions") {
    if (!button) return;
    button.removeAttribute("aria-label");
    button.setAttribute("aria-describedby", instructionId);
    const header = button.closest?.("th");
    if (header && !header.hasAttribute("aria-sort")) header.setAttribute("aria-sort", "none");
  }

  function installSortHeaders(documentObject, Observer = globalThis.MutationObserver) {
    const table = documentObject.querySelector?.(".table-card table");
    const caption = table?.querySelector?.("caption");
    const head = table?.querySelector?.("thead");
    if (!table || !caption || !head) return null;

    caption.id = caption.id || "sort-instructions";
    const apply = () => {
      documentObject.querySelectorAll?.(".sort-header").forEach((button) => {
        normalizeSortHeader(button, caption.id);
      });
    };
    apply();

    if (typeof Observer !== "function") return null;
    const observer = new Observer(apply);
    observer.observe(head, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["aria-label", "aria-sort"],
    });
    return observer;
  }

  function installStaticSemantics(documentObject) {
    const labelledSummaries = [
      ["#advanced-filters > summary", "Filters"],
      ["#sort-details > summary", "Sort collection"],
      [".columns-menu > summary", "Desktop columns"],
    ];
    for (const [selector, label] of labelledSummaries) {
      const summary = documentObject.querySelector?.(selector);
      if (summary && !summary.hasAttribute("aria-label")) summary.setAttribute("aria-label", label);
    }

    const scrollRegion = documentObject.querySelector?.(".table-card .table-scroll");
    if (scrollRegion) {
      if (!scrollRegion.hasAttribute("tabindex")) scrollRegion.setAttribute("tabindex", "0");
      if (!scrollRegion.hasAttribute("role")) scrollRegion.setAttribute("role", "region");
      if (!scrollRegion.hasAttribute("aria-label")) scrollRegion.setAttribute("aria-label", "Scrollable Pokémon table");
    }
  }

  function visibleFocusable(container) {
    return [...container.querySelectorAll(FOCUSABLE_SELECTOR)].filter((element) => {
      if (element.hasAttribute("disabled") || element.getAttribute("aria-hidden") === "true") return false;
      return element.getClientRects().length > 0;
    });
  }

  function setOutsideInert(documentObject, drawer, inert) {
    const affected = [];
    documentObject.querySelectorAll(FOCUSABLE_SELECTOR).forEach((element) => {
      if (drawer.contains(element)) return;
      if (inert) {
        affected.push({ element, inert: Boolean(element.inert) });
        element.inert = true;
      }
    });
    return affected;
  }

  function restoreOutsideInert(affected) {
    for (const item of affected || []) item.element.inert = item.inert;
  }

  async function populateFilterOptions(documentObject, fetchFunction = globalThis.fetch) {
    const drawer = documentObject.getElementById("advanced-filters");
    if (!drawer || drawer.dataset.optionsLoaded === "true") return;
    drawer.dataset.optionsLoaded = "loading";
    try {
      const response = await fetchFunction(FILTER_OPTIONS_PATH);
      if (!response.ok) throw new Error("Filter options could not be loaded");
      const options = await response.json();
      const mappings = [
        ["species-options", options.species],
        ["form-options", options.forms],
        ["fast-move-options", options.fast_moves],
        ["charged-move-options", options.charged_moves],
        ["evolution-options", options.evolutions],
      ];
      for (const [id, values] of mappings) {
        const list = documentObject.getElementById(id);
        if (!list) continue;
        list.replaceChildren(...(values || []).map((value) => {
          const option = documentObject.createElement("option");
          option.value = value;
          return option;
        }));
      }
      drawer.dataset.optionsLoaded = "true";
    } catch (error) {
      drawer.dataset.optionsLoaded = "error";
      const warning = documentObject.getElementById("filter-warning");
      if (warning) warning.textContent = error instanceof Error ? error.message : "Filter options could not be loaded";
    }
  }

  function installDrawers(root) {
    const documentObject = root.document;
    const drawers = [...documentObject.querySelectorAll("details.drawer-control")];
    let active = null;
    let returnFocus = null;
    let inertItems = [];

    function close(drawer, { restoreFocus = true } = {}) {
      if (!drawer) return;
      const shouldClean = active === drawer || inertItems.length > 0;
      if (drawer.open) drawer.open = false;
      if (!shouldClean) return;
      const panel = drawer.querySelector(".drawer-panel");
      panel?.removeAttribute("aria-modal");
      documentObject.body.style.removeProperty("overflow");
      restoreOutsideInert(inertItems);
      inertItems = [];
      active = null;
      if (restoreFocus && returnFocus?.isConnected) returnFocus.focus();
      returnFocus = null;
    }

    function open(drawer) {
      for (const other of drawers) {
        if (other !== drawer && other.open) close(other, { restoreFocus: false });
      }
      active = drawer;
      returnFocus = drawer.querySelector(":scope > summary");
      const panel = drawer.querySelector(".drawer-panel");
      if (!panel) return;
      panel.setAttribute("role", "dialog");
      panel.setAttribute("aria-modal", "true");
      documentObject.body.style.overflow = "hidden";
      inertItems = setOutsideInert(documentObject, drawer, true);
      if (drawer.id === "advanced-filters") void populateFilterOptions(documentObject, root.fetch.bind(root));
      root.requestAnimationFrame(() => {
        const first = visibleFocusable(panel)[0] || panel;
        if (first === panel) panel.tabIndex = -1;
        first.focus();
      });
    }

    for (const drawer of drawers) {
      drawer.addEventListener("toggle", () => drawer.open ? open(drawer) : close(drawer, { restoreFocus: false }));
    }

    documentObject.addEventListener("keydown", (event) => {
      if (!active?.open) return;
      if (event.key === "Escape") {
        event.preventDefault();
        close(active);
        return;
      }
      if (event.key !== "Tab") return;
      const panel = active.querySelector(".drawer-panel");
      const focusable = panel ? visibleFocusable(panel) : [];
      if (!focusable.length) {
        event.preventDefault();
        panel?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && documentObject.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && documentObject.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });

    return { close: () => close(active) };
  }

  function titleCaseStatus(value) {
    const text = String(value || "normal").trim();
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Normal";
  }

  function spacedIvDetail(value) {
    return String(value || "")
      .replace(/\s*\/\s*/g, " / ")
      .replace(/\s*·\s*/g, " · ")
      .trim();
  }

  function enhanceMobileCard(card, row, documentObject) {
    if (!card || !row) return false;
    const cells = row.cells || [];
    const ivPercent = String(cells[2]?.querySelector("strong")?.textContent || "").trim();
    const ivDetail = spacedIvDetail(cells[2]?.querySelector("small")?.textContent || "");
    const badges = [...(cells[5]?.querySelectorAll(".badge") || [])]
      .map((badge) => titleCaseStatus(badge.textContent))
      .filter(Boolean);
    const normalStatus = String(cells[5]?.querySelector(".muted")?.textContent || "").trim();
    const statusText = badges.length ? badges.join(" · ") : titleCaseStatus(normalStatus || "normal");
    const leagueKey = documentObject.getElementById("league-filter")?.value || "great";
    const leagueLabel = { great: "Great League", ultra: "Ultra League", little: "Little League" }[leagueKey] || "Selected league";
    const pvpPercent = String(cells[6]?.querySelector("strong")?.textContent || "").trim();
    const pvpText = pvpPercent
      ? `${leagueLabel} IV rank: ${pvpPercent}`
      : `${leagueLabel}: no Poke Genie IV rank`;
    const signature = [ivPercent, ivDetail, statusText, pvpText].join("|");
    if (card.dataset.mobileSemanticSource === signature) return false;

    const ivStat = card.querySelectorAll(".pokemon-card-stats > span")[1];
    if (ivStat) {
      const value = ivStat.querySelector("strong");
      const label = ivStat.querySelector("small:not(.pokemon-card-iv-detail)");
      if (value) value.textContent = ivPercent || "Unknown";
      if (label) label.textContent = "IV";
      let detail = ivStat.querySelector(".pokemon-card-iv-detail");
      if (!detail) {
        detail = documentObject.createElement("small");
        detail.className = "pokemon-card-iv-detail";
        ivStat.append(detail);
      }
      detail.textContent = ivDetail || "Exact IVs unavailable";
      ivStat.setAttribute("aria-label", ivDetail ? `IV ${ivPercent || "unknown"}; exact ${ivDetail}` : `IV ${ivPercent || "unknown"}`);
    }

    const meta = card.querySelector(".pokemon-card-meta");
    if (meta) {
      const status = documentObject.createElement("span");
      status.className = "pokemon-card-status";
      status.textContent = statusText;
      const ranking = documentObject.createElement("span");
      ranking.className = "pokemon-card-ranking";
      ranking.textContent = pvpText;
      meta.replaceChildren(status, ranking);
    }

    card.dataset.mobileSemanticSource = signature;
    return true;
  }

  function placePaginationForViewport(root) {
    const documentObject = root.document;
    const tableCard = documentObject.querySelector(".table-card");
    const cards = documentObject.getElementById("mobile-results");
    const pagination = documentObject.querySelector(".pagination");
    if (!tableCard || !cards || !pagination) return false;
    const mobile = root.matchMedia?.("(max-width: 720px)").matches ?? false;
    if (mobile && pagination.previousElementSibling !== cards) {
      cards.after(pagination);
      return true;
    }
    if (!mobile && pagination.parentElement !== tableCard) {
      tableCard.append(pagination);
      return true;
    }
    return false;
  }

  function installMobileActionOverflow(root) {
    const documentObject = root.document;
    const toolbar = documentObject.querySelector(".primary-toolbar");
    if (!toolbar || typeof root.MutationObserver !== "function") return null;

    let more = documentObject.getElementById("mobile-more");
    if (!more) {
      more = documentObject.createElement("details");
      more.id = "mobile-more";
      more.className = "mobile-more";
      more.innerHTML = '<summary>More</summary><div class="mobile-more-panel" aria-label="More collection actions"></div>';
      toolbar.append(more);
    }
    const panel = more.querySelector(".mobile-more-panel");
    const selectors = ["#saved-views", ".columns-menu", "#copy-link", "#go-search-builder"];
    const markers = new Map();
    let scheduled = false;

    const remember = (element) => {
      if (!element || markers.has(element)) return;
      const marker = documentObject.createComment(`mobile-more:${element.id || element.className || element.tagName}`);
      element.before(marker);
      markers.set(element, marker);
    };

    const apply = () => {
      scheduled = false;
      const mobile = root.matchMedia?.("(max-width: 720px)").matches ?? false;
      more.hidden = !mobile;
      for (const selector of selectors) {
        const element = documentObject.querySelector(selector);
        if (!element || element === more || more.contains(element) && element.matches?.(".mobile-more-panel")) continue;
        remember(element);
        const marker = markers.get(element);
        if (mobile) {
          if (element.parentElement !== panel) panel.append(element);
        } else if (marker?.parentNode && element.previousSibling !== marker) {
          marker.after(element);
        }
      }
      if (!mobile) more.open = false;
    };

    const schedule = () => {
      if (scheduled) return;
      scheduled = true;
      root.requestAnimationFrame(apply);
    };
    const observer = new root.MutationObserver(schedule);
    observer.observe(toolbar, { childList: true, subtree: true });
    root.matchMedia?.("(max-width: 720px)").addEventListener?.("change", schedule);
    schedule();
    return observer;
  }

  function installMobileCardSemantics(root) {
    const documentObject = root.document;
    if (typeof root.MutationObserver !== "function") return null;
    let scheduled = false;
    const apply = () => {
      scheduled = false;
      placePaginationForViewport(root);
      const body = documentObject.getElementById("pokemon-body");
      const cards = [...documentObject.querySelectorAll("#mobile-results .pokemon-card")];
      if (!body || !cards.length) return;
      const rows = [...body.querySelectorAll("tr")];
      cards.forEach((card, index) => {
        const rowIndex = Number(card.dataset.rowIndex ?? index);
        enhanceMobileCard(card, rows[rowIndex], documentObject);
      });
    };
    const schedule = () => {
      if (scheduled) return;
      scheduled = true;
      root.requestAnimationFrame(apply);
    };
    const observer = new root.MutationObserver(schedule);
    observer.observe(documentObject.body, { childList: true, subtree: true });
    documentObject.getElementById("league-filter")?.addEventListener("change", schedule);
    root.matchMedia?.("(max-width: 720px)").addEventListener?.("change", schedule);
    schedule();
    return observer;
  }

  function install(root) {
    root.document.addEventListener(
      "DOMContentLoaded",
      () => {
        installStaticSemantics(root.document);
        installSortHeaders(root.document, root.MutationObserver);
        installDrawers(root);
        installMobileActionOverflow(root);
        installMobileCardSemantics(root);
      },
      { once: true },
    );
  }

  return {
    normalizeSortHeader,
    installSortHeaders,
    installStaticSemantics,
    visibleFocusable,
    populateFilterOptions,
    installDrawers,
    titleCaseStatus,
    spacedIvDetail,
    enhanceMobileCard,
    placePaginationForViewport,
    installMobileActionOverflow,
    installMobileCardSemantics,
    install,
  };
});
