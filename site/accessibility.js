"use strict";

(function exposeAccessibility(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionAccessibility = api;
  if (root?.document) api.install(root);
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
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

  function install(root) {
    root.document.addEventListener(
      "DOMContentLoaded",
      () => installSortHeaders(root.document, root.MutationObserver),
      { once: true },
    );
  }

  return { normalizeSortHeader, installSortHeaders, install };
});
