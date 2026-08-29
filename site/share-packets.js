"use strict";

(function exposeSharePackets(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionSharePackets = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const SCHEMA_VERSION = "1.0.0";
  const PACKET_TYPES = Object.freeze([
    "pokemon-decision", "comparison", "team", "event-plan", "resource-plan",
    "rescan-request", "trade-shortlist", "diagnostic",
  ]);
  const LIMITS = Object.freeze({ record_ids: 12, claims: 24, assumptions: 24, unknowns: 24, links: 12 });
  const SENSITIVE_KEYS = new Set([
    "friend_code", "trainer_id", "trainer_name", "nickname", "private_note", "private_notes",
    "latitude", "longitude", "location", "precise_location", "address", "source_index",
    "scan_date", "original_scan_date", "catch_date",
  ]);
  const COLLECTION_KEYS = new Set(["collection", "pokemon", "records", "all_records", "full_collection"]);

  const normalizeKey = (key) => String(key ?? "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  const escapeHtml = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  const cleanText = (value) => String(value ?? "").trim();
  const boundedStrings = (value, limit) => {
    const source = Array.isArray(value) ? value : cleanText(value).split(/\r?\n|,/);
    return source.map(cleanText).filter(Boolean).slice(0, limit);
  };

  function stable(value) {
    if (Array.isArray(value)) return value.map(stable);
    if (!value || typeof value !== "object") return value;
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])]));
  }

  function redactSensitive(value, { includeSensitive = false, depth = 0 } = {}) {
    if (depth > 8) return "[depth-limited]";
    if (Array.isArray(value)) return value.slice(0, 50).map((item) => redactSensitive(item, { includeSensitive, depth: depth + 1 }));
    if (!value || typeof value !== "object") return value;
    const output = {};
    for (const [key, item] of Object.entries(value)) {
      const normalized = normalizeKey(key);
      if (COLLECTION_KEYS.has(normalized) && Array.isArray(item) && item.length > LIMITS.record_ids) {
        output[key] = `[omitted ${item.length} collection records]`;
        continue;
      }
      if (!includeSensitive && (SENSITIVE_KEYS.has(normalized) || normalized.endsWith("_note") || normalized.endsWith("_notes"))) continue;
      output[key] = redactSensitive(item, { includeSensitive, depth: depth + 1 });
    }
    return output;
  }

  function normalizeEvidence(value) {
    if (!value || typeof value !== "object") return null;
    const allowed = ["kind", "authority", "freshness", "confidence", "status", "source", "source_url", "reviewed_at", "retrieved_at", "dataset_version", "model", "version", "rule_id"];
    const output = {};
    for (const key of allowed) if (value[key] !== undefined && value[key] !== null && cleanText(value[key]) !== "") output[key] = value[key];
    return Object.keys(output).length ? stable(output) : null;
  }

  function normalizeClaims(value) {
    const source = Array.isArray(value) ? value : boundedStrings(value, LIMITS.claims).map((text) => ({ text }));
    return source.slice(0, LIMITS.claims).map((item) => {
      if (typeof item === "string") return { text: cleanText(item), evidence: null };
      return { text: cleanText(item?.text), evidence: normalizeEvidence(item?.evidence) };
    }).filter((item) => item.text);
  }

  function buildPacket(input = {}, options = {}) {
    const type = cleanText(input.packet_type || input.type);
    if (!PACKET_TYPES.includes(type)) throw new Error(`Unsupported packet type: ${type || "(empty)"}`);
    const buildId = cleanText(input.build_id || input.build?.id);
    if (!buildId) throw new Error("A build ID is required for an auditable packet.");
    const generatedAt = cleanText(options.generatedAt || input.generated_at || new Date().toISOString());
    const packet = {
      schema_version: SCHEMA_VERSION,
      packet_type: type,
      generated_at: generatedAt,
      build: {
        id: buildId,
        collection_generated_at: cleanText(input.collection_generated_at || input.build?.collection_generated_at) || null,
      },
      subject: {
        title: cleanText(input.title) || type,
        record_ids: boundedStrings(input.record_ids || [], LIMITS.record_ids),
      },
      claims: normalizeClaims(input.claims || []),
      assumptions: boundedStrings(input.assumptions || [], LIMITS.assumptions),
      unknowns: boundedStrings(input.unknowns || [], LIMITS.unknowns),
      links: boundedStrings(input.links || [], LIMITS.links),
      context: redactSensitive(input.context || {}, { includeSensitive: Boolean(options.includeSensitive) }),
      privacy: {
        full_collection_included: false,
        sensitive_fields_included: Boolean(options.includeSensitive),
        preview_required_before_share: true,
      },
    };
    return stable(packet);
  }

  function validatePacket(packet) {
    const errors = [];
    if (packet?.schema_version !== SCHEMA_VERSION) errors.push("unsupported schema_version");
    if (!PACKET_TYPES.includes(packet?.packet_type)) errors.push("unsupported packet_type");
    if (!cleanText(packet?.build?.id)) errors.push("missing build.id");
    if ((packet?.subject?.record_ids || []).length > LIMITS.record_ids) errors.push("too many record IDs");
    if ((packet?.claims || []).length > LIMITS.claims) errors.push("too many claims");
    if (packet?.privacy?.full_collection_included !== false) errors.push("full collection must be excluded");
    return { valid: errors.length === 0, errors };
  }

  const toMachineJson = (packet) => JSON.stringify(stable(packet), null, 2) + "\n";

  function toMarkdown(packet) {
    const lines = [`# ${packet.subject.title}`, "", `- Packet type: ${packet.packet_type}`, `- Build: ${packet.build.id}`, `- Generated: ${packet.generated_at}`];
    if (packet.build.collection_generated_at) lines.push(`- Collection generated: ${packet.build.collection_generated_at}`);
    if (packet.subject.record_ids.length) lines.push(`- Exact record IDs: ${packet.subject.record_ids.join(", ")}`);
    const sections = [["Claims", packet.claims.map((item) => item.evidence ? `${item.text} [${Object.values(item.evidence).join("; ")}]` : item.text)], ["Assumptions", packet.assumptions], ["Unknowns", packet.unknowns], ["Links", packet.links]];
    for (const [title, values] of sections) if (values.length) lines.push("", `## ${title}`, ...values.map((value) => `- ${value}`));
    if (Object.keys(packet.context || {}).length) lines.push("", "## Bounded context", "```json", JSON.stringify(packet.context, null, 2), "```");
    lines.push("", "Privacy: full collection excluded; review this preview before sharing.");
    return lines.join("\n") + "\n";
  }

  function toPrintableHtml(packet) {
    const list = (title, values) => values.length ? `<section><h2>${escapeHtml(title)}</h2><ul>${values.map((value) => `<li>${escapeHtml(typeof value === "string" ? value : value.text)}</li>`).join("")}</ul></section>` : "";
    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escapeHtml(packet.subject.title)}</title></head><body><main><h1>${escapeHtml(packet.subject.title)}</h1><p>Packet: ${escapeHtml(packet.packet_type)} · Build ${escapeHtml(packet.build.id)} · Generated ${escapeHtml(packet.generated_at)}</p>${list("Claims", packet.claims)}${list("Assumptions", packet.assumptions)}${list("Unknowns", packet.unknowns)}${list("Links", packet.links)}<p>Full collection excluded. Review before sharing.</p></main></body></html>`;
  }

  function render(packet, format) {
    if (format === "json") return toMachineJson(packet);
    if (format === "html") return toPrintableHtml(packet);
    return toMarkdown(packet);
  }

  function install(root) {
    const doc = root.document;
    if (!doc || doc.getElementById("share-packets")) return;
    const main = doc.getElementById("planning-app");
    if (!main) return;
    const nav = main.querySelector(".planner-section-nav");
    if (nav) {
      const link = doc.createElement("a"); link.href = "#share-packets"; link.textContent = "Share packets"; nav.append(link);
    }
    const section = doc.createElement("section");
    section.id = "share-packets"; section.className = "planner-card"; section.setAttribute("aria-labelledby", "share-packets-heading");
    section.innerHTML = `<header><div><p class="eyebrow">#153</p><h2 id="share-packets-heading">Privacy-safe Share & Decision Packets</h2></div><p id="share-packet-status" class="planner-status" role="status" aria-live="polite"></p></header><p class="planner-note">Build a bounded packet without exposing the full collection. Sensitive context is excluded by default and the exact payload is previewed before copy, download, or Web Share.</p><div class="planner-controls"><label>Packet type<select id="share-packet-type">${PACKET_TYPES.map((value) => `<option value="${value}">${value}</option>`).join("")}</select></label><label class="wide-control">Title<input id="share-packet-title" maxlength="160" placeholder="What decision are you sharing?"></label><label class="wide-control">Exact record IDs<textarea id="share-packet-records" rows="2" placeholder="One per line or comma-separated"></textarea></label><label class="wide-control">Claims<textarea id="share-packet-claims" rows="4" placeholder="One supported claim per line"></textarea></label><label>Format<select id="share-packet-format"><option value="markdown">Markdown/text</option><option value="json">Machine JSON</option><option value="html">Printable HTML</option></select></label><label><input id="share-packet-sensitive" type="checkbox"> Include sensitive custom context</label><button id="share-packet-generate" type="button">Generate preview</button><button id="share-packet-copy" type="button" disabled>Copy preview</button><button id="share-packet-download" type="button" disabled>Download preview</button><button id="share-packet-share" type="button" disabled>Share preview</button></div><label class="wide-control">Assumptions<textarea id="share-packet-assumptions" rows="2"></textarea></label><label class="wide-control">Unknowns<textarea id="share-packet-unknowns" rows="2"></textarea></label><label class="wide-control">Bounded context JSON<textarea id="share-packet-context" rows="5" placeholder='{"evidence":{"authority":"Official"}}'></textarea></label><pre id="share-packet-preview" class="planner-results" tabindex="0" aria-label="Exact share packet preview">Generate a preview before sharing.</pre>`;
    main.append(section);
    const byId = (id) => doc.getElementById(id);
    const status = byId("share-packet-status"); const preview = byId("share-packet-preview");
    let manifest = null; let currentPacket = null; let currentText = "";
    root.fetch?.("data/build-manifest.json", { cache: "no-store" }).then((response) => response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`))).then((value) => { manifest = value; status.textContent = `Ready · build ${value.build_id || "unknown"}`; }).catch(() => { status.textContent = "Manifest unavailable. Packet generation is blocked until the active build ID can be verified."; });
    const generate = () => {
      try {
        if (!manifest?.build_id) throw new Error("Active build manifest is unavailable.");
        let context = {}; const raw = byId("share-packet-context").value.trim(); if (raw) context = JSON.parse(raw);
        currentPacket = buildPacket({ packet_type: byId("share-packet-type").value, title: byId("share-packet-title").value, record_ids: byId("share-packet-records").value, claims: byId("share-packet-claims").value, assumptions: byId("share-packet-assumptions").value, unknowns: byId("share-packet-unknowns").value, context, build_id: manifest.build_id, collection_generated_at: manifest.generated_at || null }, { includeSensitive: byId("share-packet-sensitive").checked });
        currentText = render(currentPacket, byId("share-packet-format").value); preview.textContent = currentText;
        for (const id of ["share-packet-copy", "share-packet-download"]) byId(id).disabled = false;
        byId("share-packet-share").disabled = !(root.navigator?.share);
        status.textContent = "Preview generated. Review the exact payload before sharing.";
      } catch (error) { currentPacket = null; currentText = ""; preview.textContent = `Unable to generate packet: ${error.message}`; status.textContent = "Packet generation blocked."; }
    };
    byId("share-packet-generate").addEventListener("click", generate);
    byId("share-packet-format").addEventListener("change", () => { if (currentPacket) { currentText = render(currentPacket, byId("share-packet-format").value); preview.textContent = currentText; } });
    byId("share-packet-copy").addEventListener("click", async () => { await root.navigator?.clipboard?.writeText(currentText); status.textContent = "Preview copied."; });
    byId("share-packet-download").addEventListener("click", () => { const format = byId("share-packet-format").value; const extension = format === "json" ? "json" : format === "html" ? "html" : "md"; const url = root.URL.createObjectURL(new Blob([currentText], { type: "text/plain;charset=utf-8" })); const anchor = doc.createElement("a"); anchor.href = url; anchor.download = `pokemon-go-decision-packet.${extension}`; anchor.click(); root.URL.revokeObjectURL(url); });
    byId("share-packet-share").addEventListener("click", async () => { if (root.navigator?.share) await root.navigator.share({ title: currentPacket?.subject?.title || "Pokémon GO decision packet", text: currentText }); });
  }

  return { SCHEMA_VERSION, PACKET_TYPES, LIMITS, redactSensitive, buildPacket, validatePacket, toMachineJson, toMarkdown, toPrintableHtml, render, install };
});
