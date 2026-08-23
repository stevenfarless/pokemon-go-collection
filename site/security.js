"use strict";

(function exposeSecurity(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionSecurity = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const SAFE_PROTOCOLS = new Set(["http:", "https:"]);

  function safeUrl(value, base = "https://example.invalid/") {
    const text = String(value ?? "").trim();
    if (!text) return null;
    try {
      const parsed = new URL(text, base);
      return SAFE_PROTOCOLS.has(parsed.protocol) ? parsed.href : null;
    } catch {
      return null;
    }
  }

  function hardenAnchor(anchor, base) {
    const raw = anchor?.getAttribute?.("href");
    if (raw == null) return true;
    const safe = safeUrl(raw, base);
    if (!safe) {
      anchor.removeAttribute("href");
      anchor.dataset.blockedUnsafeHref = "true";
      return false;
    }
    if (anchor.target === "_blank") anchor.rel = "noopener noreferrer";
    return true;
  }

  function setText(element, value) {
    if (element) element.textContent = String(value ?? "");
    return element;
  }

  function safeJsonParse(text, validator = null) {
    try {
      const value = JSON.parse(String(text ?? ""));
      if (typeof validator === "function" && !validator(value)) return { ok: false, value: null, error: "schema" };
      return { ok: true, value, error: "" };
    } catch {
      return { ok: false, value: null, error: "parse" };
    }
  }

  function inspectDocument(documentObject, base) {
    const unsafe_links = [];
    for (const anchor of documentObject?.querySelectorAll?.("a[href]") || []) {
      const href = anchor.getAttribute("href");
      if (!safeUrl(href, base)) unsafe_links.push(href);
    }
    const inline_handlers = [];
    for (const element of documentObject?.querySelectorAll?.("*") || []) {
      for (const attribute of element.attributes || []) {
        if (/^on/i.test(attribute.name)) inline_handlers.push({ tag: element.tagName, attribute: attribute.name });
      }
    }
    return { unsafe_links, inline_handlers };
  }

  function install(root) {
    const documentObject = root.document;
    const base = root.location?.href || "https://example.invalid/";
    const apply = (node) => {
      if (!node || node.nodeType !== 1) return;
      if (node.matches?.("a[href]")) hardenAnchor(node, base);
      node.querySelectorAll?.("a[href]").forEach((anchor) => hardenAnchor(anchor, base));
    };
    documentObject.querySelectorAll("a[href]").forEach((anchor) => hardenAnchor(anchor, base));
    if (typeof root.MutationObserver === "function") {
      const observer = new root.MutationObserver((mutations) => {
        for (const mutation of mutations) {
          if (mutation.type === "attributes") apply(mutation.target);
          for (const node of mutation.addedNodes || []) apply(node);
        }
      });
      observer.observe(documentObject.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ["href"] });
    }
    documentObject.addEventListener("click", (event) => {
      const anchor = event.target?.closest?.("a[href]");
      if (anchor && !safeUrl(anchor.getAttribute("href"), base)) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);
  }

  return { SAFE_PROTOCOLS, safeUrl, hardenAnchor, setText, safeJsonParse, inspectDocument, install };
});
