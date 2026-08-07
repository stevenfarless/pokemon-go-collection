"use strict";

(function exposeCompanion(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionCompanion = api;
  if (root?.document) {
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", () => api.install(root), { once: true });
    else api.install(root);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const SAVED_VIEWS_KEY = "pokemon-go-collection:saved-views:v1";
  const SAVED_VIEWS_VERSION = 1;
  const MAX_COMPARE = 6;
  const GO_SEARCH_VERIFIED = "2026-08-07";
  const GO_SEARCH_SOURCE = "https://niantic.helpshift.com/hc/en/6-pokemon-go/faq/1486-searching-filtering-your-pokemon-inventory/";

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  const numberValue = (value) => {
    const parsed = Number(String(value ?? "").replace(/[^0-9.-]/g, ""));
    return Number.isFinite(parsed) ? parsed : null;
  };

  function fnv1a(value) {
    let hash = 0x811c9dc5;
    for (const character of String(value)) {
      hash ^= character.charCodeAt(0);
      hash = Math.imul(hash, 0x01000193);
    }
    return (hash >>> 0).toString(36);
  }

  function recordIdentitySeed(record) {
    return JSON.stringify([
      record?.pokemon_number,
      record?.name,
      record?.form,
      record?.gender,
      record?.dates?.catch,
      record?.dates?.original_scan,
      record?.dates?.scan,
    ]);
  }

  function stableRecordId(record, ordinal = 0) {
    return `p-${Number(record?.pokemon_number || 0)}-${fnv1a(recordIdentitySeed(record))}-${ordinal}`;
  }

  function rowProbe(row) {
    const cells = row?.cells || [];
    const identity = cells[0]?.querySelector("strong")?.textContent || "";
    const dex = Number(identity.match(/^#(\d+)/)?.[1] || 0);
    return {
      dex,
      cp: numberValue(cells[1]?.querySelector("strong")?.textContent),
      iv: numberValue(cells[2]?.querySelector("strong")?.textContent),
      level: numberValue(cells[3]?.querySelector("strong")?.textContent),
      fastMove: String(cells[4]?.querySelector("strong")?.textContent || "").trim(),
      catchDate: String(cells[7]?.querySelector("strong")?.textContent || "").trim(),
    };
  }

  function recordMatchesProbe(record, probe) {
    if (!record || !probe || Number(record.pokemon_number) !== probe.dex) return false;
    if (probe.cp !== null && Number(record.cp) !== probe.cp) return false;
    if (probe.iv !== null && record.ivs?.average_percent !== null && Math.abs(Number(record.ivs.average_percent) - probe.iv) > 0.011) return false;
    if (probe.level !== null && record.level?.minimum !== null && Number(record.level.minimum) !== probe.level) return false;
    if (probe.fastMove && String(record.moves?.fast || "") !== probe.fastMove) return false;
    if (probe.catchDate && probe.catchDate !== "Unknown catch" && String(record.dates?.catch || "") !== probe.catchDate) return false;
    return true;
  }

  function formatValue(value) {
    if (value === null || value === undefined || value === "") return "Missing";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (typeof value === "number") return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return String(value);
  }

  function flattenRecord(value, prefix = "", rows = []) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      for (const [key, child] of Object.entries(value)) {
        flattenRecord(child, prefix ? `${prefix}.${key}` : key, rows);
      }
    } else if (Array.isArray(value)) {
      rows.push([prefix, value.map(formatValue).join(", ") || "Missing"]);
    } else {
      rows.push([prefix, formatValue(value)]);
    }
    return rows;
  }

  function normalizedSavedViews(payload) {
    if (!payload || payload.version !== SAVED_VIEWS_VERSION || !Array.isArray(payload.views)) return null;
    const names = new Set();
    const views = [];
    for (const raw of payload.views) {
      const name = String(raw?.name || "").trim();
      const query = String(raw?.query || "");
      if (!name || names.has(name.toLocaleLowerCase()) || (!query.startsWith("?") && query !== "")) return null;
      const columns = Array.isArray(raw.columns) ? raw.columns.map(String) : [];
      names.add(name.toLocaleLowerCase());
      views.push({ name, query, columns });
    }
    return { version: SAVED_VIEWS_VERSION, views };
  }

  function loadSavedViews(storage) {
    try {
      const raw = storage?.getItem(SAVED_VIEWS_KEY);
      if (!raw) return { version: SAVED_VIEWS_VERSION, views: [] };
      return normalizedSavedViews(JSON.parse(raw)) || { version: SAVED_VIEWS_VERSION, views: [] };
    } catch {
      return { version: SAVED_VIEWS_VERSION, views: [] };
    }
  }

  function saveSavedViews(storage, payload) {
    const normalized = normalizedSavedViews(payload);
    if (!normalized) return false;
    try {
      storage?.setItem(SAVED_VIEWS_KEY, JSON.stringify(normalized));
      return true;
    } catch {
      return false;
    }
  }

  function uniqueViewName(name, existing) {
    const taken = new Set(existing.map((view) => view.name.toLocaleLowerCase()));
    if (!taken.has(name.toLocaleLowerCase())) return name;
    let suffix = 2;
    while (taken.has(`${name} (${suffix})`.toLocaleLowerCase())) suffix += 1;
    return `${name} (${suffix})`;
  }

  function rangeTerm(prefix, minimum, maximum) {
    const min = String(minimum || "").trim();
    const max = String(maximum || "").trim();
    if (min && max) return min === max ? `${prefix}${min}` : `${prefix}${min}-${max}`;
    if (min) return `${prefix}${min}-`;
    if (max) return `${prefix}-${max}`;
    return "";
  }

  function generateGoSearch(documentObject) {
    const exact = [];
    const approximate = [];
    const omitted = [];
    const control = (id) => documentObject.getElementById(id)?.value || "";
    const addExact = (term, label) => { if (term) exact.push({ term, label, kind: "Exact" }); };
    const addApprox = (term, label, warning) => { if (term) approximate.push({ term, label, warning, kind: "Approximate" }); };
    const addOmitted = (label, warning) => omitted.push({ label, warning, kind: "Not representable" });

    const species = control("species-filter").trim();
    if (species) addExact(species, `Species: ${species}`);

    const dexMin = control("dex-min");
    const dexMax = control("dex-max");
    if (dexMin || dexMax) {
      if (dexMin && dexMax && dexMin === dexMax) addExact(dexMin, `Pokédex #${dexMin}`);
      else addOmitted("Pokédex range", "The official help page documents exact Pokédex-number search, not a general Pokédex-number range operator.");
    }

    addExact(rangeTerm("cp", control("cp-min"), control("cp-max")), "CP range");
    addExact(rangeTerm("hp", control("hp-min"), control("hp-max")), "HP range");

    const status = control("status-filter");
    if (status === "shadow") addExact("shadow", "Shadow status");
    else if (status === "purified") addExact("purified", "Purified status");
    else if (status === "normal") addOmitted("Normal status", "Pokémon GO does not expose one single documented search term meaning every non-Shadow, non-Purified normal record.");

    for (const [id, term, label] of [
      ["lucky-filter", "lucky", "Lucky"],
      ["favorite-filter", "favorite", "Favorite"],
    ]) {
      const value = control(id);
      if (value === "yes") addExact(term, `${label}: yes`);
      else if (value === "no") addExact(`!${term}`, `${label}: no`);
    }

    const hundo = control("hundo-filter");
    if (hundo === "yes") addExact("4*", "Hundo");
    else if (hundo === "no") addExact("!4*", "Not a hundo");

    const nundo = control("nundo-filter");
    if (nundo === "yes") addExact("0attack&0defense&0hp", "Nundo (0/0/0)");
    else if (nundo === "no") addOmitted("Not a nundo", "Negating a three-stat conjunction cannot be safely flattened into the surrounding Pokémon GO search expression without changing its Boolean meaning.");

    const fast = control("fast-move-filter").trim();
    if (fast) addExact(`@1${fast}`, `Fast move: ${fast}`);
    const charged = control("charged-move-filter").trim();
    if (charged) addApprox(`@${charged}`, `Charged move: ${charged}`, "The broad @move search can also match a Fast Attack with the same name; the dashboard filter is charged-move specific.");

    if (control("search").trim()) addOmitted("Dashboard free-text search", "Dashboard free text can search several normalized fields at once and has no one-to-one Pokémon GO equivalent.");
    if (control("form-filter").trim()) addOmitted("Form filter", "Form names in Poke Genie do not map uniformly to documented Pokémon GO search terms.");
    if (control("gender-filter") && control("gender-filter") !== "any") addOmitted("Gender filter", "This generator only emits operators verified in the current official search help page.");
    if (control("iv-min") || control("iv-max") || control("iv-total-min") || control("iv-total-max")) addOmitted("IV percentage/total range", "Pokémon GO documents appraisal bands and per-stat appraisal searches, not arbitrary IV percentages or IV totals.");
    if (control("level-min") || control("level-max") || control("level-cap-min") || control("level-cap-max")) addOmitted("Level range", "No current official level search operator is documented.");
    if (control("pvp-percent-min") || control("pvp-percent-max") || control("pvp-rank-min") || control("pvp-rank-max") || control("pvp-eligibility-filter") !== "any") addOmitted("PvP ranking filters", "Poke Genie PvP ranks are not Pokémon GO inventory-search fields.");
    if (control("data-quality-filter") !== "any") addOmitted("Scan-quality filter", "Scan completeness is Poke Genie data, not Pokémon GO inventory metadata.");
    if (control("second-move-filter") !== "any") addOmitted("Second charged move unlocked", "The official move-position syntax searches attack type/name and is not a documented generic second-move-unlocked flag.");
    if (control("catch-from") || control("catch-to") || control("scan-from") || control("scan-to")) addOmitted("Date range", "Pokémon GO's age/year terms do not exactly reproduce the dashboard's absolute catch/scan date filters.");

    const terms = [...exact, ...approximate].map((item) => item.term).filter(Boolean);
    return {
      text: terms.join("&"),
      exact,
      approximate,
      omitted,
      verified: GO_SEARCH_VERIFIED,
      source: GO_SEARCH_SOURCE,
    };
  }

  class RecordStore {
    constructor(root) {
      this.root = root;
      this.records = null;
      this.promise = null;
      this.ids = new WeakMap();
    }

    async load() {
      if (this.records) return this.records;
      if (!this.promise) {
        this.promise = this.root.fetch("data/pokemon.json")
          .then((response) => {
            if (!response.ok) throw new Error("Collection records could not be loaded");
            return response.json();
          })
          .then((payload) => {
            this.records = payload.records || [];
            const counts = new Map();
            for (const record of this.records) {
              const seed = recordIdentitySeed(record);
              const ordinal = counts.get(seed) || 0;
              counts.set(seed, ordinal + 1);
              this.ids.set(record, stableRecordId(record, ordinal));
            }
            return this.records;
          });
      }
      return this.promise;
    }

    id(record) {
      return this.ids.get(record) || stableRecordId(record);
    }

    async fromRow(row) {
      const records = await this.load();
      const probe = rowProbe(row);
      const candidates = records.filter((record) => recordMatchesProbe(record, probe));
      if (!candidates.length) return null;
      if (candidates.length === 1) return candidates[0];
      const siblings = [...row.parentElement.querySelectorAll("tr")].filter((candidate) => {
        const other = rowProbe(candidate);
        return JSON.stringify(other) === JSON.stringify(probe);
      });
      const ordinal = Math.max(0, siblings.indexOf(row));
      return candidates[Math.min(ordinal, candidates.length - 1)];
    }
  }

  function createDialog(documentObject, id, label) {
    let dialog = documentObject.getElementById(id);
    if (dialog) return dialog;
    dialog = documentObject.createElement("dialog");
    dialog.id = id;
    dialog.className = "companion-dialog";
    dialog.setAttribute("aria-label", label);
    dialog.innerHTML = `<div class="companion-dialog-shell"><header><h2></h2><button type="button" data-dialog-close aria-label="Close ${escapeHtml(label)}">×</button></header><div class="companion-dialog-body"></div></div>`;
    dialog.querySelector("[data-dialog-close]").addEventListener("click", () => dialog.close());
    documentObject.body.append(dialog);
    return dialog;
  }

  function detailMarkup(record) {
    const pvp = record.pvp || {};
    const headline = `#${String(record.pokemon_number || 0).padStart(4, "0")} ${escapeHtml(record.name || "Unknown")}${record.form ? ` · ${escapeHtml(record.form)}` : ""}`;
    const summary = `<div class="detail-summary"><span><strong>${formatValue(record.cp)}</strong><small>CP</small></span><span><strong>${formatValue(record.ivs?.average_percent)}%</strong><small>IV</small></span><span><strong>${formatValue(record.level?.minimum)}</strong><small>Level</small></span></div>`;
    const league = (key, label) => `<section><h3>${label}</h3><p>${pvp[key]?.rank_percent == null ? "No ranking" : `${formatValue(pvp[key].rank_percent)}% · Rank #${formatValue(pvp[key].rank_number)} · stat ${formatValue(pvp[key].stat_product)} · ${formatValue(pvp[key].dust_cost)} dust`}</p></section>`;
    const rows = flattenRecord(record).map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("");
    return { headline, html: `${summary}<div class="detail-pvp">${league("great", "Great League")}${league("ultra", "Ultra League")}${league("little", "Little League")}</div><details><summary>All normalized fields</summary><dl class="record-fields">${rows}</dl></details>` };
  }

  function installMobileAndComparison(root, store) {
    const documentObject = root.document;
    const body = documentObject.getElementById("pokemon-body");
    const tableCard = documentObject.querySelector(".table-card");
    if (!body || !tableCard) return;

    const cards = documentObject.createElement("div");
    cards.id = "mobile-results";
    cards.className = "mobile-results";
    cards.setAttribute("aria-label", "Pokémon results");
    tableCard.after(cards);

    const detailDialog = createDialog(documentObject, "pokemon-detail-dialog", "Pokémon details");
    const compareDialog = createDialog(documentObject, "pokemon-compare-dialog", "Pokémon comparison");
    const selected = new Map();

    const tray = documentObject.createElement("section");
    tray.id = "comparison-tray";
    tray.className = "comparison-tray";
    tray.hidden = true;
    tray.innerHTML = `<span><strong data-compare-count>0</strong> selected</span><button type="button" data-open-comparison>Compare</button><button type="button" data-clear-comparison>Clear</button>`;
    documentObject.body.append(tray);

    const updateTray = () => {
      tray.hidden = selected.size === 0;
      tray.querySelector("[data-compare-count]").textContent = String(selected.size);
    };

    const renderComparison = () => {
      const records = [...selected.values()];
      compareDialog.querySelector("h2").textContent = `Compare ${records.length} Pokémon`;
      const bodyElement = compareDialog.querySelector(".companion-dialog-body");
      bodyElement.innerHTML = `<p class="comparison-warning">PvP rank, IV percentage, CP, status, move availability, and investment cost answer different questions. A higher number here never makes another copy automatically safe to transfer.</p><div class="comparison-grid">${records.map((record, index) => {
        const id = store.id(record);
        return `<article data-compare-id="${escapeHtml(id)}"><h3>${escapeHtml(record.name)}${record.form ? ` <small>${escapeHtml(record.form)}</small>` : ""}</h3><p>#${record.pokemon_number} · ${formatValue(record.cp)} CP · Lv ${formatValue(record.level?.minimum)}</p><p>IV ${formatValue(record.ivs?.average_percent)}% · ${formatValue(record.ivs?.attack)}/${formatValue(record.ivs?.defense)}/${formatValue(record.ivs?.stamina)}</p><p>${escapeHtml(record.status?.shadow_purified || "normal")}${record.status?.lucky ? " · lucky" : ""}</p><p>${escapeHtml(record.moves?.fast || "Unknown")} · ${escapeHtml(record.moves?.charged || "Unknown")}</p><p>GL ${formatValue(record.pvp?.great?.rank_percent)}% · UL ${formatValue(record.pvp?.ultra?.rank_percent)}% · Little ${formatValue(record.pvp?.little?.rank_percent)}%</p><div class="comparison-actions"><button type="button" data-move-left="${escapeHtml(id)}"${index === 0 ? " disabled" : ""}>←</button><button type="button" data-move-right="${escapeHtml(id)}"${index === records.length - 1 ? " disabled" : ""}>→</button><button type="button" data-remove-compare="${escapeHtml(id)}">Remove</button></div></article>`;
      }).join("")}</div>`;
    };

    const reorder = (id, offset) => {
      const entries = [...selected.entries()];
      const index = entries.findIndex(([key]) => key === id);
      const target = index + offset;
      if (index < 0 || target < 0 || target >= entries.length) return;
      [entries[index], entries[target]] = [entries[target], entries[index]];
      selected.clear();
      entries.forEach(([key, value]) => selected.set(key, value));
      renderComparison();
    };

    compareDialog.addEventListener("click", (event) => {
      const remove = event.target.closest("[data-remove-compare]");
      if (remove) {
        selected.delete(remove.dataset.removeCompare);
        updateTray();
        renderComparison();
      }
      const left = event.target.closest("[data-move-left]");
      if (left) reorder(left.dataset.moveLeft, -1);
      const right = event.target.closest("[data-move-right]");
      if (right) reorder(right.dataset.moveRight, 1);
    });

    tray.querySelector("[data-open-comparison]").addEventListener("click", () => {
      renderComparison();
      compareDialog.showModal();
    });
    tray.querySelector("[data-clear-comparison]").addEventListener("click", () => {
      selected.clear();
      updateTray();
      if (compareDialog.open) renderComparison();
      decorate();
    });

    async function showDetails(row) {
      const record = await store.fromRow(row);
      if (!record) return;
      const markup = detailMarkup(record);
      detailDialog.querySelector("h2").textContent = markup.headline;
      detailDialog.querySelector(".companion-dialog-body").innerHTML = markup.html;
      detailDialog.dataset.recordId = store.id(record);
      detailDialog.showModal();
      const url = new URL(root.location.href);
      url.hash = `pokemon=${encodeURIComponent(store.id(record))}`;
      root.history.replaceState(null, "", url);
    }

    detailDialog.addEventListener("close", () => {
      const url = new URL(root.location.href);
      if (url.hash.startsWith("#pokemon=")) {
        url.hash = "";
        root.history.replaceState(null, "", url);
      }
    });

    async function toggleCompare(row, button) {
      const record = await store.fromRow(row);
      if (!record) return;
      const id = store.id(record);
      if (selected.has(id)) selected.delete(id);
      else if (selected.size < MAX_COMPARE) selected.set(id, record);
      else {
        root.alert(`You can compare up to ${MAX_COMPARE} Pokémon at a time.`);
        return;
      }
      button.setAttribute("aria-pressed", String(selected.has(id)));
      button.textContent = selected.has(id) ? "Selected" : "Compare";
      updateTray();
    }

    function decorate() {
      const rows = [...body.querySelectorAll("tr")];
      cards.innerHTML = rows.map((row, index) => {
        const cells = row.cells;
        const identity = cells[0]?.querySelector("strong")?.textContent || "Unknown";
        const form = cells[0]?.querySelector("small")?.textContent || "";
        const cp = cells[1]?.querySelector("strong")?.textContent || "?";
        const iv = cells[2]?.textContent?.trim() || "Unknown IV";
        const level = cells[3]?.querySelector("strong")?.textContent || "?";
        const status = cells[5]?.textContent?.trim() || "normal";
        const pvp = cells[6]?.textContent?.trim() || "No ranking";
        return `<article class="pokemon-card" data-row-index="${index}" tabindex="0"><div><h3>${escapeHtml(identity)}</h3>${form ? `<p>${escapeHtml(form)}</p>` : ""}</div><div class="pokemon-card-stats"><span><strong>${escapeHtml(cp)}</strong><small>CP</small></span><span><strong>${escapeHtml(iv.split(/\s+/)[0])}</strong><small>IV</small></span><span><strong>${escapeHtml(level)}</strong><small>Lv</small></span></div><p class="pokemon-card-meta">${escapeHtml(status)} · ${escapeHtml(pvp)}</p><div class="pokemon-card-actions"><button type="button" data-card-detail="${index}">Details</button><button type="button" data-card-compare="${index}" aria-pressed="false">Compare</button></div></article>`;
      }).join("");

      rows.forEach((row) => {
        if (row.querySelector(".row-companion-actions")) return;
        const actions = documentObject.createElement("span");
        actions.className = "row-companion-actions";
        actions.innerHTML = '<button type="button" data-row-detail>Details</button><button type="button" data-row-compare aria-pressed="false">Compare</button>';
        row.cells[0]?.append(actions);
      });
    }

    cards.addEventListener("click", async (event) => {
      const detail = event.target.closest("[data-card-detail]");
      if (detail) await showDetails(body.querySelectorAll("tr")[Number(detail.dataset.cardDetail)]);
      const compare = event.target.closest("[data-card-compare]");
      if (compare) await toggleCompare(body.querySelectorAll("tr")[Number(compare.dataset.cardCompare)], compare);
    });
    cards.addEventListener("keydown", (event) => {
      if ((event.key === "Enter" || event.key === " ") && event.target.classList.contains("pokemon-card")) {
        event.preventDefault();
        event.target.querySelector("[data-card-detail]")?.click();
      }
    });
    body.addEventListener("click", async (event) => {
      const row = event.target.closest("tr");
      if (!row) return;
      if (event.target.closest("[data-row-detail]")) await showDetails(row);
      const compare = event.target.closest("[data-row-compare]");
      if (compare) await toggleCompare(row, compare);
    });

    decorate();
    new MutationObserver(decorate).observe(body, { childList: true });
  }

  function installSavedViews(root) {
    const documentObject = root.document;
    const anchor = documentObject.querySelector(".preset-control");
    if (!anchor || documentObject.getElementById("saved-views")) return;
    const details = documentObject.createElement("details");
    details.id = "saved-views";
    details.className = "saved-views";
    details.innerHTML = `<summary>Saved views</summary><div class="saved-views-card"><label>Name<input id="saved-view-name" maxlength="60" autocomplete="off"></label><button type="button" id="save-current-view">Save current</button><div id="saved-view-list"></div><div class="saved-view-backup"><button type="button" id="export-saved-views">Export JSON</button><label class="import-button">Import JSON<input id="import-saved-views" type="file" accept="application/json,.json"></label><label><input id="replace-saved-view-conflicts" type="checkbox"> Replace duplicate names on import</label></div><p id="saved-view-status" class="muted" role="status" aria-live="polite"></p><p class="muted">Saved views stay only in this browser until you export a JSON backup.</p></div>`;
    anchor.after(details);

    const storage = root.localStorage;
    const status = details.querySelector("#saved-view-status");
    const list = details.querySelector("#saved-view-list");
    const currentColumns = () => {
      try {
        const key = root.CollectionDashboard?.Columns?.COLUMN_STORAGE_KEY;
        return key ? JSON.parse(storage.getItem(key) || "[]") : [];
      } catch { return []; }
    };
    const setColumns = (columns) => {
      const key = root.CollectionDashboard?.Columns?.COLUMN_STORAGE_KEY;
      if (key) storage.setItem(key, JSON.stringify(columns || []));
    };

    const render = () => {
      const data = loadSavedViews(storage);
      list.innerHTML = data.views.length ? data.views.map((view, index) => `<article class="saved-view-row"><button type="button" data-apply-view="${index}">${escapeHtml(view.name)}</button><button type="button" data-rename-view="${index}" aria-label="Rename ${escapeHtml(view.name)}">Rename</button><button type="button" data-duplicate-view="${index}" aria-label="Duplicate ${escapeHtml(view.name)}">Duplicate</button><button type="button" data-delete-view="${index}" aria-label="Delete ${escapeHtml(view.name)}">Delete</button></article>`).join("") : '<p class="muted">No personal saved views yet.</p>';
    };

    details.querySelector("#save-current-view").addEventListener("click", () => {
      const nameInput = details.querySelector("#saved-view-name");
      const requested = nameInput.value.trim();
      if (!requested) { status.textContent = "Enter a name first."; return; }
      const data = loadSavedViews(storage);
      const name = uniqueViewName(requested, data.views);
      data.views.push({ name, query: root.location.search, columns: currentColumns() });
      saveSavedViews(storage, data);
      nameInput.value = "";
      status.textContent = name === requested ? `Saved “${name}”.` : `Saved as “${name}” because that name already existed.`;
      render();
    });

    list.addEventListener("click", (event) => {
      const data = loadSavedViews(storage);
      const action = event.target.closest("button");
      if (!action) return;
      const index = Number(action.dataset.applyView ?? action.dataset.renameView ?? action.dataset.duplicateView ?? action.dataset.deleteView);
      const view = data.views[index];
      if (!view) return;
      if (action.dataset.applyView !== undefined) {
        setColumns(view.columns);
        root.location.assign(`${root.location.pathname}${view.query}`);
      } else if (action.dataset.renameView !== undefined) {
        const next = root.prompt("Rename saved view", view.name)?.trim();
        if (!next) return;
        view.name = uniqueViewName(next, data.views.filter((_, candidate) => candidate !== index));
        saveSavedViews(storage, data); render();
      } else if (action.dataset.duplicateView !== undefined) {
        data.views.splice(index + 1, 0, { ...view, name: uniqueViewName(`${view.name} copy`, data.views), columns: [...view.columns] });
        saveSavedViews(storage, data); render();
      } else if (action.dataset.deleteView !== undefined && root.confirm(`Delete saved view “${view.name}”?`)) {
        data.views.splice(index, 1); saveSavedViews(storage, data); render();
      }
    });

    details.querySelector("#export-saved-views").addEventListener("click", () => {
      const blob = new Blob([`${JSON.stringify(loadSavedViews(storage), null, 2)}\n`], { type: "application/json" });
      const link = documentObject.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "pokemon-go-collection-saved-views.json";
      link.click();
      URL.revokeObjectURL(link.href);
      status.textContent = "Saved views exported.";
    });

    details.querySelector("#import-saved-views").addEventListener("change", async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      try {
        const incoming = normalizedSavedViews(JSON.parse(await file.text()));
        if (!incoming) throw new Error("Unsupported or invalid saved-view backup.");
        const current = loadSavedViews(storage);
        const replace = details.querySelector("#replace-saved-view-conflicts").checked;
        for (const view of incoming.views) {
          const index = current.views.findIndex((candidate) => candidate.name.toLocaleLowerCase() === view.name.toLocaleLowerCase());
          if (index >= 0 && replace) current.views[index] = view;
          else current.views.push({ ...view, name: uniqueViewName(view.name, current.views) });
        }
        if (!saveSavedViews(storage, current)) throw new Error("Browser storage is unavailable.");
        status.textContent = `Imported ${incoming.views.length} saved view${incoming.views.length === 1 ? "" : "s"}.`;
        render();
      } catch (error) {
        status.textContent = error instanceof Error ? error.message : "Import failed.";
      } finally {
        event.target.value = "";
      }
    });
    render();
  }

  function installGoSearch(root) {
    const documentObject = root.document;
    const toolbar = documentObject.querySelector(".primary-toolbar");
    if (!toolbar || documentObject.getElementById("go-search-builder")) return;
    const button = documentObject.createElement("button");
    button.id = "go-search-builder";
    button.type = "button";
    button.className = "go-search-builder";
    button.textContent = "GO Search";
    toolbar.append(button);
    const dialog = createDialog(documentObject, "go-search-dialog", "Pokémon GO search string");

    const render = () => {
      const result = generateGoSearch(documentObject);
      dialog.querySelector("h2").textContent = "Pokémon GO search string";
      dialog.querySelector(".companion-dialog-body").innerHTML = `<p class="comparison-warning">This generator translates only conditions it can explain. It never claims a transfer search is safe to use blindly.</p><label>Generated string<textarea id="go-search-output" readonly>${escapeHtml(result.text)}</textarea></label><button type="button" id="copy-go-search"${result.text ? "" : " disabled"}>Copy</button><p id="go-search-copy-status" role="status" aria-live="polite"></p><section><h3>Exact</h3>${result.exact.length ? `<ul>${result.exact.map((item) => `<li><code>${escapeHtml(item.term)}</code> — ${escapeHtml(item.label)}</li>`).join("")}</ul>` : "<p>None.</p>"}</section><section><h3>Approximate</h3>${result.approximate.length ? `<ul>${result.approximate.map((item) => `<li><code>${escapeHtml(item.term)}</code> — ${escapeHtml(item.label)}. ${escapeHtml(item.warning)}</li>`).join("")}</ul>` : "<p>None.</p>"}</section><section><h3>Not represented</h3>${result.omitted.length ? `<ul>${result.omitted.map((item) => `<li>${escapeHtml(item.label)}: ${escapeHtml(item.warning)}</li>`).join("")}</ul>` : "<p>None.</p>"}</section><p class="muted">Operators verified ${escapeHtml(result.verified)} against the <a href="${escapeHtml(result.source)}" target="_blank" rel="noopener noreferrer">official Pokémon GO Help Center search documentation</a>.</p>`;
      dialog.querySelector("#copy-go-search")?.addEventListener("click", async () => {
        try {
          await root.navigator.clipboard.writeText(result.text);
          dialog.querySelector("#go-search-copy-status").textContent = "Copied.";
        } catch {
          dialog.querySelector("#go-search-output").select();
          dialog.querySelector("#go-search-copy-status").textContent = "Clipboard permission was unavailable. The text is selected for manual copy.";
        }
      });
    };
    button.addEventListener("click", () => { render(); dialog.showModal(); });
  }

  function installPwa(root) {
    const documentObject = root.document;
    if (!root.navigator?.serviceWorker || !/^https?:$/.test(root.location.protocol)) return;
    const banner = documentObject.createElement("aside");
    banner.id = "offline-status";
    banner.className = "offline-status";
    banner.hidden = true;
    banner.innerHTML = '<span data-offline-message></span><button type="button" data-pwa-refresh>Refresh</button>';
    documentObject.body.prepend(banner);
    const message = banner.querySelector("[data-offline-message]");
    const exportText = documentObject.querySelector(".data-menu-card small")?.textContent?.replace(/^Exported\s*/i, "") || "cached export";
    let registration;

    const updateOnlineState = () => {
      if (!root.navigator.onLine) {
        banner.hidden = false;
        message.textContent = `Offline · using ${exportText}`;
      } else if (registration?.waiting) {
        banner.hidden = false;
        message.textContent = "A newer app version is ready.";
      } else {
        banner.hidden = true;
      }
    };

    root.addEventListener("online", updateOnlineState);
    root.addEventListener("offline", updateOnlineState);
    banner.querySelector("[data-pwa-refresh]").addEventListener("click", () => {
      if (registration?.waiting) registration.waiting.postMessage({ type: "SKIP_WAITING" });
      else root.location.reload();
    });

    root.navigator.serviceWorker.register("sw.js").then((value) => {
      registration = value;
      registration.addEventListener("updatefound", () => {
        registration.installing?.addEventListener("statechange", updateOnlineState);
      });
      updateOnlineState();
    }).catch(() => { /* Ordinary online static-site behavior remains available. */ });
  }

  function install(root) {
    const store = new RecordStore(root);
    installMobileAndComparison(root, store);
    installSavedViews(root);
    installGoSearch(root);
    installPwa(root);
  }

  return {
    SAVED_VIEWS_KEY,
    SAVED_VIEWS_VERSION,
    GO_SEARCH_VERIFIED,
    GO_SEARCH_SOURCE,
    stableRecordId,
    rowProbe,
    recordMatchesProbe,
    flattenRecord,
    normalizedSavedViews,
    loadSavedViews,
    saveSavedViews,
    uniqueViewName,
    rangeTerm,
    generateGoSearch,
    install,
  };
});
