"use strict";

(() => {
  const STORAGE_KEY = "pokemon-go-collection:appearance:v1";
  const VALID = new Set(["system", "light", "dark"]);

  function storage() {
    try { return window.localStorage; } catch { return null; }
  }

  function getPreference() {
    const value = storage()?.getItem(STORAGE_KEY) || "system";
    return VALID.has(value) ? value : "system";
  }

  function applyPreference(value = getPreference()) {
    const root = document.documentElement;
    if (value === "system") root.removeAttribute("data-theme");
    else root.dataset.theme = value;
    root.dataset.themePreference = value;
    return value;
  }

  function setPreference(value) {
    if (!VALID.has(value)) throw new Error(`Unsupported appearance preference: ${value}`);
    const store = storage();
    if (store) {
      if (value === "system") store.removeItem(STORAGE_KEY);
      else store.setItem(STORAGE_KEY, value);
    }
    applyPreference(value);
    window.dispatchEvent(new CustomEvent("collection-appearancechange", { detail: { value } }));
    return value;
  }

  function installControl() {
    if (document.getElementById("collection-appearance-choice")) return;
    const host = document.querySelector(".data-menu-card nav") || document.querySelector(".site-header") || document.body;
    if (!host) return;
    const label = document.createElement("label");
    label.className = "ds-preference-control";
    label.textContent = "Theme ";
    const select = document.createElement("select");
    select.id = "collection-appearance-choice";
    select.setAttribute("aria-label", "Theme");
    for (const [value, text] of [["system", "System"], ["light", "Light"], ["dark", "Dark"]]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.append(option);
    }
    select.value = getPreference();
    select.addEventListener("change", () => setPreference(select.value));
    label.append(select);
    host.append(label);
  }

  const media = typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  media?.addEventListener?.("change", () => { if (getPreference() === "system") applyPreference("system"); });
  applyPreference();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", installControl, { once: true });
  else installControl();

  const api = { STORAGE_KEY, getPreference, setPreference, applyPreference, installControl };
  window.CollectionDesignSystem = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
