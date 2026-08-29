"use strict";

(function exposeGlossaryExperience(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionGlossaryExperience = api;
  if (root?.document) {
    const start = () => root.setTimeout(() => api.install(root), 0);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const GLOSSARY_PATH = "data/knowledge/glossary.json";
  const SHARE_DRAFT_KEY = "pokemon-go-collection:share-packet-draft:v1";

  const normalize = (value) => String(value || "").trim().toLocaleLowerCase();

  function entryText(entry) {
    return [entry.term, ...(entry.aliases || []), entry.definition, entry.why_it_matters, entry.classification]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase();
  }

  function findEntry(entries, value) {
    const needle = normalize(value);
    if (!needle) return null;
    return entries.find((entry) => normalize(entry.term) === needle || (entry.aliases || []).some((alias) => normalize(alias) === needle)) || null;
  }

  function searchEntries(entries, query, limit = 8) {
    const text = normalize(query);
    if (!text) return [];
    const tokens = text.split(/\s+/).filter(Boolean);
    return entries
      .map((entry) => {
        const haystack = entryText(entry);
        if (!tokens.every((token) => haystack.includes(token))) return null;
        const term = normalize(entry.term);
        let score = 10;
        if (term === text) score += 200;
        else if (term.startsWith(text)) score += 100;
        else if (term.includes(text)) score += 50;
        score += tokens.reduce((total, token) => total + (term.includes(token) ? 8 : 2), 0);
        return { entry, score };
      })
      .filter(Boolean)
      .sort((a, b) => b.score - a.score || String(a.entry.term).localeCompare(String(b.entry.term)))
      .slice(0, Math.max(0, Number(limit) || 0))
      .map((candidate) => candidate.entry);
  }

  function installShareHandoff(root) {
    const d=root.document,b=d.querySelector("[data-share-current]");if(!b)return false;b.onclick=()=>{const l=root.location||{},a=[];try{const q=new URLSearchParams(l.search||"");["record_id","record"].forEach(k=>{if(q.get(k))a.push(q.get(k))})}catch(_){}for(const n of d.querySelectorAll('[data-record-id][aria-selected="true"],input[data-record-id]:checked')||[])a.push(n.dataset?.recordId);const r=[...new Set(a.map(String).filter(Boolean))].slice(0,12),s=b.dataset.shareSource,t=b.dataset.shareType==="pokemon-decision"&&r.length>1?"comparison":b.dataset.shareType||"pokemon-decision",x={packet_type:t,title:String(d.title||"Current view").slice(0,160),record_ids:r,unknowns:r.length?[]:["No exact record selected."],links:[`${s}${l.search||""}${l.hash||""}`.slice(0,500)]};try{root.sessionStorage?.setItem(SHARE_DRAFT_KEY,JSON.stringify(x))}catch{return}l.href="tools.html#share-packets"};return true;
  }

  async function loadGlossary(root) {
    const response = await root.fetch(GLOSSARY_PATH);
    if (!response.ok) throw new Error("Glossary could not be loaded");
    const payload = await response.json();
    if (!Array.isArray(payload?.entries)) throw new Error("Glossary entries are invalid");
    return payload;
  }

  function element(documentObject, tag, className, text) {
    const node = documentObject.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function renderDefinition(root, payload, entry) {
    const documentObject = root.document;
    const dialog = documentObject.getElementById("product-glossary-dialog");
    const body = dialog?.querySelector(".product-dialog-body");
    if (!dialog || !body) return false;
    body.replaceChildren();
    body.append(element(documentObject, "h3", "", entry.term));
    body.append(element(documentObject, "p", "", entry.definition));
    const why = element(documentObject, "section", "product-glossary-why");
    why.append(element(documentObject, "h4", "", "Why this matters"));
    why.append(element(documentObject, "p", "", entry.why_it_matters));
    body.append(why);
    const details = element(documentObject, "dl", "product-glossary-details");
    const rows = [
      ["Classification", entry.classification],
      ["Reviewed", payload.reviewed_at],
      ["Dataset", payload.dataset_version],
    ];
    for (const [label, value] of rows) {
      if (!value) continue;
      details.append(element(documentObject, "dt", "", label), element(documentObject, "dd", "", value));
    }
    if (entry.source_resource) {
      details.append(element(documentObject, "dt", "", "Source resource"));
      const value = element(documentObject, "dd");
      const link = element(documentObject, "a", "", entry.source_resource);
      link.href = entry.source_resource;
      value.append(link);
      details.append(value);
    }
    body.append(details);
    dialog.showModal();
    return true;
  }

  function renderGuidanceTerms(root, payload) {
    const documentObject = root.document;
    const list = documentObject.querySelector(".product-guidance-definitions .product-term-list");
    if (!list) return;
    list.replaceChildren();
    for (const entry of payload.entries) {
      const button = element(documentObject, "button", "product-definition-button", entry.term);
      button.type = "button";
      button.dataset.term = entry.term;
      list.append(button);
    }
  }

  function installGlossaryClicks(root, payload) {
    root.document.addEventListener("click", (event) => {
      const button = event.target.closest?.("[data-term]");
      if (!button) return;
      const entry = findEntry(payload.entries, button.dataset.term);
      if (!entry) return;
      if (renderDefinition(root, payload, entry)) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    }, true);
  }

  function installSearchResults(root, payload) {
    const documentObject = root.document;
    const dialog = documentObject.getElementById("product-global-search");
    const input = dialog?.querySelector(".product-global-search-input");
    const results = dialog?.querySelector(".product-search-results");
    if (!input || !results || typeof root.MutationObserver !== "function") return;
    let queued = false;

    function render() {
      queued = false;
      results.querySelector("[data-glossary-search-results]")?.remove();
      const matches = searchEntries(payload.entries, input.value, 8);
      if (!matches.length) return;
      const section = element(documentObject, "section", "product-search-group");
      section.dataset.glossarySearchResults = "true";
      section.append(element(documentObject, "h3", "", "Definitions"));
      for (const entry of matches) {
        const button = element(documentObject, "button", "product-search-result");
        button.type = "button";
        button.append(
          element(documentObject, "strong", "", entry.term),
          element(documentObject, "small", "", entry.definition),
        );
        button.addEventListener("click", () => renderDefinition(root, payload, entry));
        section.append(button);
      }
      results.append(section);
    }

    function queueRender() {
      if (queued) return;
      queued = true;
      root.queueMicrotask(render);
    }

    input.addEventListener("input", queueRender);
    const observer = new root.MutationObserver((mutations) => {
      if (mutations.some((mutation) => [...mutation.addedNodes].some((node) => node?.dataset?.glossarySearchResults))) return;
      queueRender();
    });
    observer.observe(results, { childList: true });
  }

  async function install(root) {
    installShareHandoff(root);
    try {
      const payload = await loadGlossary(root);
      installGlossaryClicks(root, payload);
      renderGuidanceTerms(root, payload);
      installSearchResults(root, payload);
      return payload;
    } catch {
      return null;
    }
  }

  return { GLOSSARY_PATH, SHARE_DRAFT_KEY, findEntry, searchEntries, installShareHandoff, loadGlossary, install };
});