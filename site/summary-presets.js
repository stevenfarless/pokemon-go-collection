"use strict";

(function exposeSummaryPresets(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionSummaryPresets = api;
  if (root?.document) api.install(root);
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  function dispatchInput(element, root) {
    element.dispatchEvent(new root.Event("input", { bubbles: true }));
  }

  function clickWithShift(element, root) {
    element.dispatchEvent(new root.MouseEvent("click", { bubbles: true, shiftKey: true }));
  }

  function numericText(element) {
    return Number(String(element?.textContent || "").replace(/[^0-9.-]/g, ""));
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

  function install(root) {
    root.document.addEventListener("DOMContentLoaded", () => {
      root.document.querySelectorAll("[data-summary-preset]").forEach((button) => {
        button.addEventListener("click", () => {
          applySummaryPreset(root.document, root, button.dataset.summaryPreset);
        });
      });
    }, { once: true });
  }

  return { numericText, resetPreservingPageSize, applySummaryPreset, install };
});
