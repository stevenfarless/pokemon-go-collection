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

  function install(root) {
    root.document.addEventListener(
      "DOMContentLoaded",
      () => {
        installStaticSemantics(root.document);
        installSortHeaders(root.document, root.MutationObserver);
        installDrawers(root);
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
    install,
  };
});
