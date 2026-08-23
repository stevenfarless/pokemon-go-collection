"use strict";

(() => {
  const LOCALE_KEY = "pokemon-go-collection:locale:v1";
  const TIMEZONE_KEY = "pokemon-go-collection:timezone:v1";
  const CATALOG_VERSION = "1.0.0";
  const CATALOG = Object.freeze({
    "app.theme": "Theme",
    "app.locale": "Language/locale",
    "app.timezone": "Planning timezone",
    "theme.system": "System",
    "theme.light": "Light",
    "theme.dark": "Dark",
    "status.healthy": "Healthy",
    "status.limited": "Limited",
    "status.offline": "Offline",
    "status.needsAttention": "Needs attention",
    "freshness.currentAsOf": "Current as of {time}",
    "freshness.source": "Source {source}",
    "freshness.state": "Freshness {state}",
    "styleGuide.title": "Design system",
    "styleGuide.description": "Shared semantic tokens and interaction patterns.",
    "mechanics.coverage": "Mechanics coverage",
    "mechanics.reviewed": "Reviewed {date}",
    "currentData.unavailable": "No reviewed current-data path is available for this category.",
  });
  const SUPPORTED_CATALOGS = new Set(["en", "en-XA"]);

  function safeStorage() { try { return window.localStorage; } catch { return null; } }
  function canonicalLocale(value) {
    const raw = String(value || "").trim();
    if (raw.toLowerCase() === "en-xa") return "en-XA";
    try { return Intl.getCanonicalLocales(raw || navigator.language || "en")[0] || "en"; } catch { return "en"; }
  }
  function getLocale() { return canonicalLocale(safeStorage()?.getItem(LOCALE_KEY) || navigator.language || "en"); }
  function getCatalogLocale(locale = getLocale()) { return locale === "en-XA" ? "en-XA" : "en"; }
  function getTimeZone() {
    const stored = safeStorage()?.getItem(TIMEZONE_KEY);
    if (stored) return stored;
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  }
  function validateTimeZone(value) {
    try { new Intl.DateTimeFormat("en", { timeZone: value }).format(); return true; } catch { return false; }
  }
  function pseudo(text) {
    const expanded = String(text).replace(/[A-Za-z]/g, (char) => ({a:"á",e:"ë",i:"ï",o:"ô",u:"ü",A:"Á",E:"Ë",I:"Ï",O:"Ô",U:"Ü"}[char] || char));
    return `［${expanded} ～～］`;
  }
  function t(key, variables = {}, locale = getLocale()) {
    let text = CATALOG[key] || key;
    text = text.replace(/\{([A-Za-z0-9_]+)\}/g, (_, name) => String(variables[name] ?? `{${name}}`));
    return getCatalogLocale(locale) === "en-XA" ? pseudo(text) : text;
  }
  function setLocale(value) {
    const locale = canonicalLocale(value);
    safeStorage()?.setItem(LOCALE_KEY, locale);
    applyDocumentLocale(locale);
    window.dispatchEvent(new CustomEvent("collection-localechange", { detail: { locale, timeZone: getTimeZone() } }));
    return locale;
  }
  function setTimeZone(value) {
    if (!validateTimeZone(value)) throw new Error(`Invalid IANA timezone: ${value}`);
    safeStorage()?.setItem(TIMEZONE_KEY, value);
    window.dispatchEvent(new CustomEvent("collection-timezonechange", { detail: { locale: getLocale(), timeZone: value } }));
    return value;
  }
  function formatDateTime(value, options = {}) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.valueOf())) return "";
    return new Intl.DateTimeFormat(getLocale(), { dateStyle: "medium", timeStyle: "short", timeZone: options.timeZone || getTimeZone(), ...options }).format(date);
  }
  function formatNumber(value, options = {}) { return new Intl.NumberFormat(getLocale(), options).format(value); }
  function compare(a, b) { return new Intl.Collator(getLocale(), { numeric: true, sensitivity: "base" }).compare(String(a), String(b)); }
  function formatRelativeTime(value, unit = "day") { return new Intl.RelativeTimeFormat(getLocale(), { numeric: "auto" }).format(value, unit); }
  function applyDocumentLocale(locale = getLocale()) {
    document.documentElement.lang = locale === "en-XA" ? "en" : locale;
    document.documentElement.dir = "ltr";
    document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n, {}, locale); });
  }
  function installControl() {
    if (document.getElementById("collection-locale-choice")) return;
    const host = document.querySelector(".data-menu-card nav") || document.querySelector(".site-header") || document.body;
    if (!host) return;
    const localeLabel = document.createElement("label");
    localeLabel.className = "ds-preference-control";
    localeLabel.textContent = `${t("app.locale")} `;
    const localeSelect = document.createElement("select");
    localeSelect.id = "collection-locale-choice";
    for (const [value, label] of [["en", "English"], ["en-XA", "Pseudo locale"]]) {
      const option = document.createElement("option"); option.value = value; option.textContent = label; localeSelect.append(option);
    }
    localeSelect.value = getCatalogLocale();
    localeSelect.addEventListener("change", () => setLocale(localeSelect.value));
    localeLabel.append(localeSelect);
    host.append(localeLabel);
  }
  applyDocumentLocale();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => { applyDocumentLocale(); installControl(); }, { once: true });
  else installControl();

  const api = { LOCALE_KEY, TIMEZONE_KEY, CATALOG_VERSION, CATALOG, SUPPORTED_CATALOGS, canonicalLocale, getLocale, getCatalogLocale, getTimeZone, validateTimeZone, t, setLocale, setTimeZone, formatDateTime, formatNumber, formatRelativeTime, compare, applyDocumentLocale, installControl };
  window.CollectionI18n = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
