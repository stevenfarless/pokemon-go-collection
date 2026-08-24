"use strict";

(function exposeActionWorkflows(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionActionWorkflows = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const LAST_SEEN_KEY = "pokemon-go-collection:last-seen-build:v1";
  const LOCAL_PLANNING_KEYS = [
    "pokemon-go-collection:saved-views:v1",
    "pokemon-go-collection:goals:v1",
    "pokemon-go-collection:annotations:v1",
    "pokemon-go-collection:enrichment:v1",
  ];

  function el(documentObject, tag, className, text) {
    const node = documentObject.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function safeJson(raw, fallback) {
    try { return JSON.parse(raw); } catch { return fallback; }
  }

  function parseCsv(text) {
    const rows = [];
    let row = [], field = "", quoted = false;
    const source = String(text || "").replace(/^\uFEFF/, "");
    for (let index = 0; index < source.length; index += 1) {
      const character = source[index];
      if (quoted) {
        if (character === '"' && source[index + 1] === '"') { field += '"'; index += 1; }
        else if (character === '"') quoted = false;
        else field += character;
      } else if (character === '"') quoted = true;
      else if (character === ",") { row.push(field); field = ""; }
      else if (character === "\n") { row.push(field.replace(/\r$/, "")); rows.push(row); row = []; field = ""; }
      else field += character;
    }
    if (quoted) throw new Error("CSV contains an unterminated quoted field.");
    if (field !== "" || row.length) { row.push(field.replace(/\r$/, "")); rows.push(row); }
    while (rows.length && rows[rows.length - 1].every((value) => value === "")) rows.pop();
    if (!rows.length) return { headers: [], rows: [] };
    const headers = rows[0].map((value) => value.trim());
    const records = rows.slice(1).map((values, rowIndex) => {
      const record = {};
      headers.forEach((header, columnIndex) => { record[header] = values[columnIndex] ?? ""; });
      return { rowNumber: rowIndex + 2, values: record, extraValues: values.slice(headers.length) };
    });
    return { headers, rows: records };
  }

  function validateFilename(name) {
    const match = String(name || "").match(/^shared-text-(\d{4})-(\d{2})-(\d{2}) (\d{2})_(\d{2})_(\d{2})\.(\d{3})\.csv$/);
    if (!match) return { valid: false, timestamp: null, reason: "Filename must use shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv." };
    const [, year, month, day, hour, minute, second, millisecond] = match;
    const parts = [year, month, day, hour, minute, second, millisecond].map(Number);
    const date = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2], parts[3], parts[4], parts[5], parts[6]));
    const valid = date.getUTCFullYear() === parts[0] && date.getUTCMonth() === parts[1] - 1 && date.getUTCDate() === parts[2] && date.getUTCHours() === parts[3] && date.getUTCMinutes() === parts[4] && date.getUTCSeconds() === parts[5];
    return valid
      ? { valid: true, timestamp: `${year}-${month}-${day}T${hour}:${minute}:${second}.${millisecond}`, reason: null }
      : { valid: false, timestamp: null, reason: "Filename contains an impossible date or time." };
  }

  function parseNumeric(raw, column) {
    let text = String(raw ?? "").trim().replaceAll(",", "").replace(/%$/, "");
    if (column === "Weight") text = text.replace(/kg$/, "");
    if (column === "Height") text = text.replace(/m$/, "");
    if (!text) return null;
    const number = Number(text);
    return Number.isFinite(number) ? number : NaN;
  }

  function analyzePreflight(filename, text, contract, active = {}) {
    const parsed = parseCsv(text);
    const filenameCheck = validateFilename(filename);
    const required = new Set(contract?.required_columns || ["Name", "Pokemon Number", "CP"]);
    const known = new Set(contract?.known_columns || []);
    const missingColumns = [...required].filter((column) => !parsed.headers.includes(column));
    const unknownColumns = parsed.headers.filter((column) => known.size && !known.has(column));
    const errors = [], warnings = [];
    if (!filenameCheck.valid) errors.push({ kind: "filename", message: filenameCheck.reason });
    missingColumns.forEach((column) => errors.push({ kind: "schema", column, message: `Missing required column: ${column}` }));
    if (!parsed.rows.length) errors.push({ kind: "rows", message: "CSV contains no Pokémon rows." });

    const integerRules = contract?.integer_rules || {};
    const numberRules = contract?.number_rules || {};
    const statusColumns = new Set(contract?.status_columns || []);
    const booleanColumns = new Set(contract?.boolean_columns || []);
    const trueValues = new Set((contract?.true_values || ["1", "true", "yes", "y"]).map((value) => String(value).toLowerCase()));
    const falseValues = new Set((contract?.false_values || ["0", "false", "no", "n"]).map((value) => String(value).toLowerCase()));
    const signatures = new Map();
    const localRows = [];

    for (const entry of parsed.rows) {
      const row = entry.values;
      if (!String(row.Name ?? "").trim()) errors.push({ kind: "row", row: entry.rowNumber, column: "Name", message: "Required Pokémon name is blank." });
      for (const [column, rule] of Object.entries(integerRules)) {
        if (!parsed.headers.includes(column)) continue;
        const raw = String(row[column] ?? "").trim();
        if (!raw) {
          if (rule.required) errors.push({ kind: "row", row: entry.rowNumber, column, message: "Required numeric value is blank." });
          continue;
        }
        const value = parseNumeric(raw, column);
        const invalid = !Number.isFinite(value) || !Number.isInteger(value) || (rule.minimum != null && value < rule.minimum) || (rule.maximum != null && value > rule.maximum);
        if (invalid) (rule.required ? errors : warnings).push({ kind: "row", row: entry.rowNumber, column, message: rule.required ? "Invalid required integer; production build would stop." : "Invalid optional integer; production build publishes this field as null." });
      }
      for (const [column, rule] of Object.entries(numberRules)) {
        if (!parsed.headers.includes(column)) continue;
        const raw = String(row[column] ?? "").trim();
        if (!raw) continue;
        const value = parseNumeric(raw, column);
        let invalid = !Number.isFinite(value) || (rule.minimum != null && value < rule.minimum) || (rule.maximum != null && value > rule.maximum);
        if (!invalid && ["Level Min", "Level Max"].includes(column) && !Number.isInteger(value * 2)) invalid = true;
        if (invalid) warnings.push({ kind: "row", row: entry.rowNumber, column, message: "Invalid optional number; production build publishes this field as null." });
      }
      for (const column of booleanColumns) {
        if (!parsed.headers.includes(column)) continue;
        const raw = String(row[column] ?? "").trim().toLowerCase();
        if (raw && !trueValues.has(raw) && !falseValues.has(raw)) warnings.push({ kind: "row", row: entry.rowNumber, column, message: "Unknown boolean value; verify before upload." });
      }
      for (const column of statusColumns) {
        if (!parsed.headers.includes(column)) continue;
        const raw = String(row[column] ?? "").trim();
        if (raw && !["0", "1", "2"].includes(raw)) warnings.push({ kind: "row", row: entry.rowNumber, column, message: "Unknown status code; production validation will not silently invent a supported state." });
      }
      const signature = [row.Name, row.Form, row["Pokemon Number"], row.Gender, row.CP, row["Atk IV"], row["Def IV"], row["Sta IV"], row["Original Scan Date"]].map((value) => String(value ?? "").trim().toLowerCase()).join("|");
      signatures.set(signature, (signatures.get(signature) || 0) + 1);
      localRows.push({ name: String(row.Name || "").trim(), dex: Number(parseNumeric(row["Pokemon Number"], "Pokemon Number")), cp: Number(parseNumeric(row.CP, "CP")), form: String(row.Form || "").trim(), signature, row: entry.rowNumber });
    }

    const activeRecords = active?.records || [];
    const activeGroups = new Map();
    for (const record of activeRecords) {
      const key = `${String(record.name || "").toLowerCase()}|${Number(record.pokemon_number)}|${Number(record.cp)}|${String(record.form || "").toLowerCase()}`;
      if (!activeGroups.has(key)) activeGroups.set(key, []);
      activeGroups.get(key).push(record);
    }
    const comparison = { matched: 0, new: 0, ambiguous: 0 };
    for (const row of localRows) {
      const key = `${row.name.toLowerCase()}|${row.dex}|${row.cp}|${row.form.toLowerCase()}`;
      const candidates = activeGroups.get(key) || [];
      if (candidates.length === 1) comparison.matched += 1;
      else if (candidates.length > 1) comparison.ambiguous += 1;
      else comparison.new += 1;
    }
    const duplicateRows = [...signatures.values()].reduce((sum, count) => sum + Math.max(0, count - 1), 0);
    const activeTimestamp = active?.export_timestamp || null;
    const timestampOrder = filenameCheck.valid && activeTimestamp
      ? (filenameCheck.timestamp > String(activeTimestamp) ? "newer" : filenameCheck.timestamp === String(activeTimestamp) ? "same" : "older")
      : "unknown";
    return {
      accepted: errors.length === 0,
      filename: filenameCheck,
      columns: { required: [...required], missing: missingColumns, unknown: unknownColumns, source: parsed.headers },
      rowCount: parsed.rows.length,
      duplicateRows,
      comparison,
      timestampOrder,
      activeTimestamp,
      errors,
      warnings,
      localRows,
    };
  }

  function narrowRecordSearch(record) {
    const terms = [], gaps = [];
    if (record?.pokemon_number != null) terms.push(String(Number(record.pokemon_number)));
    if (record?.cp != null) terms.push(`cp${Number(record.cp)}`);
    if (["shadow", "purified"].includes(record?.status?.shadow_purified)) terms.push(record.status.shadow_purified);
    if (record?.status?.lucky) terms.push("lucky");
    if (record?.status?.favorite) terms.push("favorite");
    if (record?.ivs?.is_hundo) terms.push("4*");
    else if (record?.ivs?.is_nundo) terms.push("0attack", "0defense", "0hp");
    else if ([record?.ivs?.attack, record?.ivs?.defense, record?.ivs?.stamina].some((value) => value != null)) gaps.push("Exact non-hundo/nundo IV values require manual verification.");
    const safeMove = (value) => value && !/[&,;:]/.test(String(value)) ? String(value) : null;
    const fast = safeMove(record?.moves?.fast), charged = safeMove(record?.moves?.charged);
    if (fast) terms.push(`@1${fast}`); else if (record?.moves?.fast) gaps.push("Fast move omitted because it contains search syntax characters.");
    if (charged) terms.push(`@2${charged}`); else if (record?.moves?.charged) gaps.push("Charged move omitted because it contains search syntax characters.");
    if (record?.form) gaps.push("Form requires manual verification.");
    gaps.push("Canonical record ID and scan/catch timestamps cannot be searched in Pokémon GO.");
    return { search: terms.join("&"), exact: false, gaps };
  }

  function rowProbe(row) {
    const cells = row?.cells || [];
    const identity = String(cells[0]?.querySelector("strong")?.textContent || "").trim();
    return {
      dex: Number(identity.match(/^#(\d+)/)?.[1] || 0),
      name: identity.replace(/^#\d+\s+/, "").replace(/\s+(Male|Female|Genderless)$/i, "").trim(),
      form: String(cells[0]?.querySelector("small")?.textContent || "").trim(),
      cp: Number(String(cells[1]?.querySelector("strong")?.textContent || "").replace(/[^0-9.-]/g, "")),
      iv: Number(String(cells[2]?.querySelector("strong")?.textContent || "").replace(/[^0-9.-]/g, "")),
    };
  }

  function matchRowRecord(row, records) {
    const probe = rowProbe(row);
    let candidates = records.filter((record) => Number(record.pokemon_number) === probe.dex && Number(record.cp) === probe.cp && String(record.name || "") === probe.name);
    if (probe.form) candidates = candidates.filter((record) => String(record.form || "") === probe.form);
    if (Number.isFinite(probe.iv)) {
      const exact = candidates.filter((record) => record.ivs?.average_percent != null && Math.abs(Number(record.ivs.average_percent) - probe.iv) < 0.02);
      if (exact.length) candidates = exact;
    }
    return candidates.length === 1 ? candidates[0] : null;
  }

  function makeDialog(documentObject, id, label) {
    let dialog = documentObject.getElementById(id);
    if (dialog) return dialog;
    dialog = el(documentObject, "dialog", "workflow-dialog");
    dialog.id = id;
    dialog.setAttribute("aria-label", label);
    const shell = el(documentObject, "div", "workflow-dialog-shell");
    const header = el(documentObject, "header", "workflow-dialog-header");
    header.append(el(documentObject, "h2", "", label));
    const close = el(documentObject, "button", "", "Close"); close.type = "button"; close.addEventListener("click", () => dialog.close());
    header.append(close);
    shell.append(header, el(documentObject, "div", "workflow-dialog-body"));
    dialog.append(shell); documentObject.body.append(dialog); return dialog;
  }

  function renderDecision(documentObject, card) {
    const wrap = el(documentObject, "div", "decision-card");
    wrap.dataset.state = card.status || "observe";
    const lead = el(documentObject, "section", "decision-lead");
    lead.append(el(documentObject, "p", "workflow-eyebrow", `#${String(card.pokemon_number || "?").padStart(4, "0")} · CP ${card.cp ?? "?"}`), el(documentObject, "h3", "", card.recommendation));
    wrap.append(lead);
    const listSection = (heading, values, className = "") => {
      const section = el(documentObject, "section", className); section.append(el(documentObject, "h4", "", heading));
      const list = el(documentObject, "ul"); (values || []).forEach((value) => list.append(el(documentObject, "li", "", value))); section.append(list); return section;
    };
    wrap.append(listSection("Why", card.why));
    wrap.append(listSection("What could change this", card.what_could_change_this, "workflow-detail"));
    if ((card.irreversible_actions_blocked || []).length) wrap.append(listSection("Irreversible actions currently blocked", card.irreversible_actions_blocked.map((value) => String(value).replaceAll("_", " ")), "workflow-warning"));
    const next = el(documentObject, "section", "decision-next"); next.append(el(documentObject, "h4", "", "Exact next step"));
    const link = el(documentObject, "a", "", card.exact_next_step?.label || "Open workflow"); link.href = card.exact_next_step?.route || `index.html?record=${encodeURIComponent(card.record_id)}`; next.append(link);
    const pack = el(documentObject, "a", "", "Action Pack"); pack.href = card.action_pack_route; next.append(pack); wrap.append(next);
    const evidence = el(documentObject, "details", "workflow-expert"); evidence.dataset.guidanceMin = "detailed"; evidence.append(el(documentObject, "summary", "", "Evidence and source layers"));
    const evidenceList = el(documentObject, "ul"); (card.evidence || []).forEach((item) => evidenceList.append(el(documentObject, "li", "", `${item.layer}: ${item.resource}`))); evidence.append(evidenceList); wrap.append(evidence);
    return wrap;
  }

  async function installDecisions(root) {
    const body = root.document.getElementById("pokemon-body");
    if (!body) return;
    let pokemon;
    try {
      pokemon = await root.fetch("data/pokemon.json").then((response) => {
        if (!response.ok) throw new Error(`Collection records returned HTTP ${response.status}`);
        return response.json();
      });
    } catch { return; }
    const records = pokemon.records || [];
    let decisionMap = null;
    let decisionPromise = null;
    const loadDecisions = async () => {
      if (decisionMap) return decisionMap;
      if (!decisionPromise) {
        decisionPromise = root.fetch("data/decisions/records.json").then((response) => {
          if (!response.ok) throw new Error(`Decision records returned HTTP ${response.status}`);
          return response.json();
        }).then((payload) => new Map((payload.cards || []).map((card) => [card.record_id, card])));
      }
      try {
        decisionMap = await decisionPromise;
        return decisionMap;
      } catch (error) {
        decisionPromise = null;
        throw error;
      }
    };
    const dialog = makeDialog(root.document, "workflow-decision-dialog", "What should I do with this Pokémon?");
    const openCard = async (recordId) => {
      const target = dialog.querySelector(".workflow-dialog-body");
      target.replaceChildren(el(root.document, "p", "ds-notice", "Loading exact decision…"));
      dialog.showModal();
      try {
        const byId = await loadDecisions();
        const card = byId.get(recordId);
        if (!card) {
          target.replaceChildren(el(root.document, "p", "ds-notice", "No exact decision is available for this record."));
          return;
        }
        target.replaceChildren(renderDecision(root.document, card));
      } catch {
        target.replaceChildren(el(root.document, "p", "ds-notice", "Decision details could not be loaded. The collection remains usable."));
      }
    };
    const rememberRow = (row) => { const record = matchRowRecord(row, records); root.__workflowLastRecordId = record?.identity?.record_id || null; return record; };
    const decorate = () => {
      [...body.querySelectorAll("tr")].forEach((row) => {
        let actions = row.querySelector(".row-companion-actions");
        if (!actions) { actions = el(root.document, "span", "row-workflow-actions"); row.lastElementChild?.append(actions); }
        if (!actions.querySelector("[data-workflow-decision]")) {
          const button = el(root.document, "button", "", "Decision"); button.type = "button"; button.dataset.workflowDecision = "row";
          button.addEventListener("click", (event) => { event.stopPropagation(); const record = rememberRow(row); if (record) void openCard(record.identity.record_id); }); actions.append(button);
        }
      });
      root.document.querySelectorAll(".pokemon-card").forEach((card) => {
        const actions = card.querySelector(".pokemon-card-actions"); if (!actions || actions.querySelector("[data-workflow-decision]")) return;
        const button = el(root.document, "button", "", "Decision"); button.type = "button"; button.dataset.workflowDecision = "card";
        button.addEventListener("click", (event) => { event.stopPropagation(); const row = body.querySelectorAll("tr")[Number(card.dataset.rowIndex)]; const record = rememberRow(row); if (record) void openCard(record.identity.record_id); }); actions.append(button);
      });
    };
    root.document.addEventListener("click", (event) => {
      const row = event.target.closest?.("#pokemon-body tr"); if (row) rememberRow(row);
      const mobile = event.target.closest?.(".pokemon-card"); if (mobile) { const rowForCard = body.querySelectorAll("tr")[Number(mobile.dataset.rowIndex)]; if (rowForCard) rememberRow(rowForCard); }
    }, true);
    const detail = root.document.querySelector("dialog.companion-dialog");
    if (detail) {
      new MutationObserver(() => {
        if (!detail.open || !root.__workflowLastRecordId || detail.querySelector("[data-detail-decision]")) return;
        const button = el(root.document, "button", "detail-decision-button", "Decision"); button.type = "button"; button.dataset.detailDecision = "true"; button.addEventListener("click", () => void openCard(root.__workflowLastRecordId));
        detail.querySelector(".companion-dialog-body")?.prepend(button);
      }).observe(detail, { attributes: true, childList: true, subtree: true });
    }
    decorate(); new MutationObserver(decorate).observe(body.parentElement || body, { childList: true, subtree: true });
  }

  function localPlanningSummary(storage) {
    return LOCAL_PLANNING_KEYS.map((key) => {
      let raw = null; try { raw = storage?.getItem(key); } catch { raw = null; }
      if (!raw) return { key, state: "absent", itemCount: 0 };
      const value = safeJson(raw, null); if (!value) return { key, state: "invalid-json", itemCount: null };
      const candidate = value.views || value.goals || value.annotations || value.records || value.items;
      return { key, state: "present", version: value.version ?? value.schema_version ?? null, itemCount: Array.isArray(candidate) ? candidate.length : null };
    });
  }

  async function installTimeline(root) {
    const mount = root.document.getElementById("change-timeline-root"); if (!mount) return;
    try {
      const payload = await root.fetch("data/change-timeline.json").then((r) => r.json()); mount.replaceChildren();
      const controls = el(root.document, "div", "timeline-filters ds-toolbar");
      const lanes = Object.entries(payload.lanes || {});
      const enabled = new Set(lanes.map(([name]) => name));
      const render = () => {
        mount.querySelector(".timeline-content")?.remove(); const content = el(root.document, "div", "timeline-content");
        for (const [name, lane] of lanes) {
          if (!enabled.has(name)) continue;
          const section = el(root.document, "section", "workflow-section timeline-lane"); section.append(el(root.document, "h2", "", name.replaceAll("-", " ")));
          let entries = lane.entries || [];
          if (name === "local-planning") {
            entries = localPlanningSummary(root.localStorage).filter((item) => item.state !== "absent").map((item) => ({ title: item.key.split(":").slice(-2, -1)[0] || "Local planning", summary: `Local state ${item.state}; version ${item.version ?? "unknown"}; item count ${item.itemCount ?? "unknown"}. Private contents are not displayed.` }));
          }
          if (lane.status === "history-unavailable") section.append(el(root.document, "p", "ds-empty", "Collection history is unavailable. This is different from having no meaningful changes."));
          else if (!entries.length) section.append(el(root.document, "p", "ds-empty", "No meaningful changes in this lane."));
          for (const entry of entries) {
            const article = el(root.document, "article", "timeline-entry ds-card"); article.append(el(root.document, "h3", "", entry.title), el(root.document, "p", "", entry.summary));
            if (entry.authority || entry.date) article.append(el(root.document, "small", "", [entry.authority, entry.date].filter(Boolean).join(" · ")));
            if (entry.route) { const link = el(root.document, "a", "", "Open affected item"); link.href = entry.route; article.append(link); }
            if (entry.source_reference) { const source = el(root.document, "a", "", "Source"); source.href = entry.source_reference; source.target = "_blank"; source.rel = "noopener noreferrer"; article.append(source); }
            section.append(article);
          }
          content.append(section);
        }
        mount.append(content);
      };
      for (const [name] of lanes) {
        const label = el(root.document, "label", "timeline-filter"); const input = el(root.document, "input"); input.type = "checkbox"; input.checked = true;
        input.addEventListener("change", () => { input.checked ? enabled.add(name) : enabled.delete(name); render(); }); label.append(input, root.document.createTextNode(` ${name.replaceAll("-", " ")}`)); controls.append(label);
      }
      mount.append(controls); render();
      try { root.localStorage?.setItem(LAST_SEEN_KEY, JSON.stringify({ build_id: payload.build_id, seen_at: new Date().toISOString() })); } catch { /* optional */ }
    } catch { mount.replaceChildren(el(root.document, "p", "ds-notice", "The change timeline could not be loaded.")); }
  }

  async function copyText(root, text, status) {
    try { await root.navigator.clipboard.writeText(text); status.textContent = "Copied."; }
    catch {
      const area = el(root.document, "textarea"); area.value = text; root.document.body.append(area); area.select();
      try { root.document.execCommand("copy"); status.textContent = "Copied."; } catch { status.textContent = "Copy failed. Select the text manually."; }
      area.remove();
    }
  }

  async function installActionPacks(root) {
    const mount = root.document.getElementById("action-packs-root"); if (!mount) return;
    try {
      const [payload, pokemon] = await Promise.all([root.fetch("data/action-packs/index.json").then((r) => r.json()), root.fetch("data/pokemon.json").then((r) => r.json())]);
      const params = new URL(root.location.href).searchParams; const wanted = params.get("pack"); const recordIds = [...params.getAll("record"), ...(params.get("records") || "").split(",")].filter(Boolean);
      const byId = new Map((pokemon.records || []).map((record) => [record.identity?.record_id, record])); mount.replaceChildren();
      for (const raw of payload.packs || []) {
        if (wanted && raw.id !== wanted) continue;
        const pack = { ...raw, batches: [...(raw.batches || [])], manual_review_record_ids: [...(raw.manual_review_record_ids || [])] };
        if (recordIds.length && ["locate-exact", "rescan-incomplete", "duplicate-review", "evolution-review", "pvp-party", "raid-max-party"].includes(pack.id)) {
          pack.batches = recordIds.flatMap((recordId) => {
            const record = byId.get(recordId); if (!record) return [];
            const result = narrowRecordSearch(record); return [{ record_ids: [recordId], search: result.search, exact: false, explanation: "Narrow locator for this canonical record. Verify manually.", representational_gaps: result.gaps }];
          }); pack.manual_review_record_ids = recordIds.filter((id) => byId.has(id));
        }
        const section = el(root.document, "section", "workflow-section action-pack ds-card"); section.dataset.status = pack.status; section.append(el(root.document, "h2", "", pack.title), el(root.document, "p", "", pack.description));
        const warning = el(root.document, "p", "ds-notice workflow-warning", pack.warning); warning.dataset.kind = "warning"; section.append(warning);
        section.append(el(root.document, "p", "", `Status: ${pack.status} · Suggested temporary tag: ${pack.suggested_tag}`));
        if (!pack.batches.length) section.append(el(root.document, "p", "ds-empty", pack.status === "unavailable" ? "No fresh evidence currently activates this pack." : "No exact records are currently selected for this pack."));
        pack.batches.forEach((batch, index) => {
          const article = el(root.document, "article", "action-batch"); article.append(el(root.document, "h3", "", `Locator ${index + 1}`));
          const code = el(root.document, "code", "action-search", batch.search || "No safe locator generated"); article.append(code, el(root.document, "p", "", batch.explanation));
          const status = el(root.document, "span", "copy-status"); if (batch.search) { const button = el(root.document, "button", "", "Copy search"); button.type = "button"; button.addEventListener("click", () => copyText(root, batch.search, status)); article.append(button, status); }
          if ((batch.representational_gaps || []).length) { const gaps = el(root.document, "ul", "representational-gaps"); batch.representational_gaps.forEach((gap) => gaps.append(el(root.document, "li", "", gap))); article.append(el(root.document, "strong", "", "Manual verification required"), gaps); }
          section.append(article);
        });
        const steps = el(root.document, "ol", "workflow-steps"); (pack.steps || []).forEach((step) => steps.append(el(root.document, "li", "", step))); section.append(el(root.document, "h3", "", "In-game checklist"), steps);
        mount.append(section);
      }
    } catch { mount.replaceChildren(el(root.document, "p", "ds-notice", "Action Packs could not be loaded.")); }
  }

  function githubUploadUrl(locationObject) {
    const host = String(locationObject?.hostname || ""); const match = host.match(/^([a-z0-9-]+)\.github\.io$/i); if (!match) return null;
    const repository = String(locationObject.pathname || "").split("/").filter(Boolean)[0]; if (!repository) return null;
    return `https://github.com/${match[1]}/${repository}/upload/main/exports`;
  }

  function renderPreflight(root, mount, analysis) {
    const section = el(root.document, "section", "workflow-section preflight-result ds-card"); section.dataset.state = analysis.accepted ? "accepted" : "rejected";
    section.append(el(root.document, "h3", "", analysis.accepted ? "Production preflight: accepted" : "Production preflight: blocked"));
    section.append(el(root.document, "p", "", `${analysis.rowCount} rows · ${analysis.duplicateRows} probable repeated row(s) · local export is ${analysis.timestampOrder} than the active build timestamp.`));
    section.append(el(root.document, "p", "", `Comparison: ${analysis.comparison.matched} matched, ${analysis.comparison.new} appear new, ${analysis.comparison.ambiguous} ambiguous.`));
    const issueList = (heading, items) => { if (!items.length) return; section.append(el(root.document, "h4", "", heading)); const list = el(root.document, "ul"); items.slice(0, 40).forEach((item) => list.append(el(root.document, "li", "", `${item.row ? `Row ${item.row}, ` : ""}${item.column ? `${item.column}: ` : ""}${item.message}`))); section.append(list); };
    issueList("Blocking errors", analysis.errors); issueList("Warnings", analysis.warnings);
    if (analysis.columns.unknown.length) section.append(el(root.document, "p", "", `Unknown future columns preserved as metadata: ${analysis.columns.unknown.join(", ")}`));
    if (analysis.accepted) {
      const upload = githubUploadUrl(root.location); if (upload) { const link = el(root.document, "a", "workflow-upload-link", "Open repository exports/ upload"); link.href = upload; link.target = "_blank"; link.rel = "noopener noreferrer"; section.append(link); }
      else section.append(el(root.document, "p", "", "Preflight passed. Commit this CSV under the repository exports/ folder, then let the normal deployment workflow validate and publish it."));
    }
    mount.append(section);
  }

  async function installScanInbox(root) {
    const mount = root.document.getElementById("scan-inbox-root"); if (!mount) return;
    try {
      const [inbox, contract, pokemon, manifest] = await Promise.all([root.fetch("data/scan-inbox.json").then((r) => r.json()), root.fetch("data/preflight-contract.json").then((r) => r.json()), root.fetch("data/pokemon.json").then((r) => r.json()), root.fetch("data/build-manifest.json").then((r) => r.json())]);
      mount.replaceChildren(); const targetId = new URL(root.location.href).searchParams.get("record");
      const queueWrap = el(root.document, "div", "scan-queues");
      for (const [name, items] of Object.entries(inbox.queues || {})) {
        const selected = targetId ? items.filter((item) => item.record_id === targetId) : items;
        if (targetId && !selected.length) continue;
        const section = el(root.document, "section", "workflow-section scan-queue"); section.append(el(root.document, "h2", "", `${name.replaceAll("-", " ")} (${selected.length})`));
        if (!selected.length) section.append(el(root.document, "p", "ds-empty", "No records in this queue."));
        selected.slice(0, name === "healthy" ? 25 : 100).forEach((item) => {
          const article = el(root.document, "article", "scan-item ds-card"); article.append(el(root.document, "h3", "", item.name || "Ambiguous record group")); if (item.reason) article.append(el(root.document, "p", "", String(item.reason).replaceAll("_", " ")));
          if (item.steps?.length) { const list = el(root.document, "ol"); item.steps.forEach((step) => list.append(el(root.document, "li", "", step))); article.append(list); }
          if (item.record_route) { const link = el(root.document, "a", "", "Open exact record"); link.href = item.record_route; article.append(link); }
          if (item.action_pack_route) { const link = el(root.document, "a", "", "Rescan Action Pack"); link.href = item.action_pack_route; article.append(link); } section.append(article);
        }); queueWrap.append(section);
      }
      mount.append(queueWrap);
      const preflight = el(root.document, "section", "workflow-section preflight ds-card"); preflight.append(el(root.document, "h2", "", "Local Poke Genie CSV preflight"), el(root.document, "p", "", "Choose or drop a CSV. File bytes stay in this browser and are never sent by this preflight workflow."));
      const input = el(root.document, "input"); input.type = "file"; input.accept = ".csv,text/csv"; input.setAttribute("aria-label", "Choose Poke Genie CSV");
      const drop = el(root.document, "div", "preflight-drop", "Drop a Poke Genie CSV here, or use the file picker."); drop.tabIndex = 0; preflight.append(input, drop);
      const resultMount = el(root.document, "div", "preflight-results"); preflight.append(resultMount); mount.prepend(preflight);
      const handle = async (file) => { if (!file) return; resultMount.replaceChildren(el(root.document, "p", "", "Parsing locally…")); try { const text = await file.text(); const analysis = analyzePreflight(file.name, text, contract, { records: pokemon.records || [], export_timestamp: manifest.export_timestamp }); resultMount.replaceChildren(); renderPreflight(root, resultMount, analysis); } catch (error) { resultMount.replaceChildren(el(root.document, "p", "ds-notice", error?.message || "Preflight failed.")); } };
      input.addEventListener("change", () => handle(input.files?.[0]));
      for (const eventName of ["dragenter", "dragover"]) drop.addEventListener(eventName, (event) => { event.preventDefault(); drop.dataset.drag = "true"; });
      for (const eventName of ["dragleave", "drop"]) drop.addEventListener(eventName, (event) => { event.preventDefault(); delete drop.dataset.drag; });
      drop.addEventListener("drop", (event) => handle(event.dataTransfer?.files?.[0]));
      preflight.append(el(root.document, "p", "workflow-muted", `Progressive file/share handlers are optional. Standard file selection is always supported. Active export: ${manifest.export_timestamp}.`));
    } catch { mount.replaceChildren(el(root.document, "p", "ds-notice", "Scan Inbox or preflight contracts could not be loaded.")); }
  }

  function install(root) {
    installDecisions(root); installTimeline(root); installActionPacks(root); installScanInbox(root);
  }

  return { LAST_SEEN_KEY, parseCsv, validateFilename, analyzePreflight, narrowRecordSearch, githubUploadUrl, install };
});
