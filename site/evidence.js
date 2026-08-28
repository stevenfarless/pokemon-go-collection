"use strict";

(function exposeEvidence(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionEvidence = api;
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const VERSION = "1.0.0";
  const KINDS = Object.freeze({
    "canonical-owned": { label: "Owned fact", authority: "Poke Genie / canonical collection", marker: "Owned" },
    "official-current": { label: "Official current fact", authority: "Official", marker: "Official" },
    "verified-community": { label: "Verified community data", authority: "Verified community data", marker: "Community" },
    simulation: { label: "Simulation result", authority: "Simulation result", marker: "Simulation" },
    calculated: { label: "Calculated result", authority: "Deterministic calculation", marker: "Calculated" },
    "browser-local": { label: "User-confirmed local fact", authority: "Browser-local user confirmation", marker: "Local" },
    reported: { label: "Reported information", authority: "Reported", marker: "Reported" },
    datamined: { label: "Datamined information", authority: "Datamined", marker: "Datamined" },
    outdated: { label: "Outdated evidence", authority: "Outdated", marker: "Outdated" },
    unknown: { label: "Unknown / unsupported", authority: "Unknown", marker: "Unknown" },
  });
  const FRESHNESS = new Set(["fresh", "stale", "expired", "not-applicable", "unknown"]);
  const CONFIDENCE = new Set(["high", "medium", "low", "unknown", "not-applicable"]);
  const PREREQUISITES = new Set(["satisfied", "missing", "stale", "unsupported", "unknown"]);

  function object(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function strings(value) {
    return Array.isArray(value) ? value.map((item) => String(item || "").trim()).filter(Boolean) : [];
  }

  function normalize(raw) {
    const value = object(raw);
    const kind = Object.prototype.hasOwnProperty.call(KINDS, value.kind) ? value.kind : "unknown";
    const defaults = KINDS[kind];
    const rawFreshness = object(value.freshness);
    const freshnessState = FRESHNESS.has(rawFreshness.state)
      ? rawFreshness.state
      : (["canonical-owned", "simulation", "calculated", "browser-local"].includes(kind) ? "not-applicable" : "unknown");
    const rawConfidence = object(value.confidence);
    const confidenceState = CONFIDENCE.has(rawConfidence.state)
      ? rawConfidence.state
      : (["canonical-owned", "official-current", "browser-local"].includes(kind) ? "not-applicable" : "unknown");
    const prerequisites = Array.isArray(value.prerequisites) ? value.prerequisites.flatMap((item) => {
      if (!item || typeof item !== "object" || Array.isArray(item)) return [];
      const state = PREREQUISITES.has(item.state) ? item.state : "unknown";
      return [{
        name: String(item.name || "prerequisite"),
        state,
        reason: item.reason == null ? null : String(item.reason),
        remediation: item.remediation == null ? null : String(item.remediation),
      }];
    }) : [];
    return {
      schema_version: VERSION,
      kind,
      label: String(value.label || defaults.label),
      authority: String(value.authority || defaults.authority),
      freshness: {
        state: freshnessState,
        checked_at: rawFreshness.checked_at || null,
        dataset_timestamp: rawFreshness.dataset_timestamp || null,
        valid_until: rawFreshness.valid_until || null,
        reason: rawFreshness.reason || null,
      },
      confidence: { state: confidenceState, reason: rawConfidence.reason || null },
      source: object(value.source),
      assumptions: strings(value.assumptions),
      rule_trace: strings(value.rule_trace),
      prerequisites,
      uncertainty: strings(value.uncertainty),
    };
  }

  function fromLegacy(raw) {
    const value = object(raw);
    if (value.evidence && typeof value.evidence === "object") return normalize(value.evidence);
    const layer = String(value.evidence_layer || value.classification || value.authority || "").toLocaleLowerCase();
    let kind = "unknown";
    if (layer.includes("owned") || layer.includes("poke genie") || layer.includes("collection fact")) kind = "canonical-owned";
    else if (layer.includes("official")) kind = "official-current";
    else if (layer.includes("verified community")) kind = "verified-community";
    else if (layer.includes("simulation")) kind = "simulation";
    else if (layer.includes("calculated") || layer.includes("derived") || layer.includes("reasoning")) kind = "calculated";
    else if (layer.includes("browser-local") || layer.includes("user-confirmed")) kind = "browser-local";
    else if (layer.includes("reported")) kind = "reported";
    else if (layer.includes("datamined")) kind = "datamined";
    else if (layer.includes("stale") || layer.includes("expired") || layer.includes("outdated")) kind = "outdated";
    const freshness = object(value.freshness);
    const state = freshness.state || (value.freshness_state || (kind === "outdated" ? "stale" : undefined));
    return normalize({
      kind,
      authority: value.authority || value.classification,
      freshness: { ...freshness, state },
      confidence: typeof value.confidence === "string" ? { state: value.confidence } : object(value.confidence),
      source: {
        url: value.source_reference,
        provider: value.provider,
        dataset_timestamp: value.dataset_timestamp,
        version: value.data_version,
        model_version: value.model_version,
      },
      assumptions: value.assumptions,
      rule_trace: value.rule_trace,
      prerequisites: value.prerequisites,
      uncertainty: value.uncertainty,
    });
  }

  function freshnessText(evidence) {
    const state = normalize(evidence).freshness.state;
    if (state === "not-applicable") return "Freshness not applicable";
    if (state === "fresh") return "Fresh";
    if (state === "stale") return "Stale";
    if (state === "expired") return "Expired";
    return "Freshness unknown";
  }

  function confidenceText(evidence) {
    const state = normalize(evidence).confidence.state;
    if (state === "not-applicable") return "Confidence not applicable";
    if (state === "high") return "High confidence";
    if (state === "medium") return "Medium confidence";
    if (state === "low") return "Low confidence";
    return "Confidence unknown";
  }

  function summaryText(raw) {
    const evidence = normalize(raw);
    const pieces = [KINDS[evidence.kind].marker];
    if (evidence.freshness.state !== "not-applicable") pieces.push(freshnessText(evidence));
    if (evidence.confidence.state !== "not-applicable") pieces.push(confidenceText(evidence));
    return pieces.join(" · ");
  }

  function blockedPrerequisites(raw) {
    return normalize(raw).prerequisites.filter((item) => item.state !== "satisfied");
  }

  function explainUnavailable(raw) {
    const evidence = normalize(raw);
    const blocked = blockedPrerequisites(evidence);
    if (blocked.length) {
      const first = blocked[0];
      return {
        reason: first.reason || `${first.name} is ${first.state}.`,
        remediation: first.remediation || "Review the evidence details before acting.",
      };
    }
    if (evidence.uncertainty.length) return { reason: evidence.uncertainty[0], remediation: "Review the evidence details before acting." };
    return { reason: "Required evidence is unavailable or unsupported.", remediation: "Provide or refresh the missing prerequisite." };
  }

  function formatDate(value) {
    if (!value) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    try { return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date); }
    catch { return String(value); }
  }

  function addRow(documentObject, list, label, value) {
    if (value == null || value === "") return;
    const dt = documentObject.createElement("dt");
    dt.textContent = label;
    const dd = documentObject.createElement("dd");
    dd.textContent = String(value);
    list.append(dt, dd);
  }

  function addList(documentObject, parent, heading, values) {
    if (!values?.length) return;
    const section = documentObject.createElement("section");
    section.className = "ds-evidence-section";
    const title = documentObject.createElement("h4");
    title.textContent = heading;
    const list = documentObject.createElement("ul");
    for (const value of values) {
      const item = documentObject.createElement("li");
      item.textContent = String(value);
      list.append(item);
    }
    section.append(title, list);
    parent.append(section);
  }

  function render(documentObject, raw, options = {}) {
    const evidence = normalize(raw);
    const details = documentObject.createElement("details");
    details.className = "ds-evidence";
    details.dataset.evidenceKind = evidence.kind;
    details.dataset.freshness = evidence.freshness.state;
    details.dataset.confidence = evidence.confidence.state;

    const summary = documentObject.createElement("summary");
    summary.className = "ds-evidence-summary";
    const chip = documentObject.createElement("span");
    chip.className = "ds-source-chip ds-evidence-chip";
    chip.dataset.evidenceKind = evidence.kind;
    chip.textContent = options.compact === false ? evidence.label : summaryText(evidence);
    chip.setAttribute("aria-label", `Evidence: ${summaryText(evidence)}. ${evidence.authority}.`);
    summary.append(chip);
    details.append(summary);

    const body = documentObject.createElement("div");
    body.className = "ds-evidence-body";
    const dl = documentObject.createElement("dl");
    dl.className = "ds-evidence-meta";
    addRow(documentObject, dl, "Evidence type", evidence.label);
    addRow(documentObject, dl, "Authority", evidence.authority);
    addRow(documentObject, dl, "Freshness", freshnessText(evidence));
    if (evidence.freshness.reason) addRow(documentObject, dl, "Freshness reason", evidence.freshness.reason);
    addRow(documentObject, dl, "Confidence", confidenceText(evidence));
    if (evidence.confidence.reason) addRow(documentObject, dl, "Confidence reason", evidence.confidence.reason);
    addRow(documentObject, dl, "Dataset time", formatDate(evidence.freshness.dataset_timestamp || evidence.source.dataset_timestamp));
    addRow(documentObject, dl, "Valid until", formatDate(evidence.freshness.valid_until));
    addRow(documentObject, dl, "Retrieved", formatDate(evidence.source.retrieved_at));
    addRow(documentObject, dl, "Reviewed", formatDate(evidence.source.reviewed_at));
    addRow(documentObject, dl, "Version", evidence.source.version);
    addRow(documentObject, dl, "Model version", evidence.source.model_version);
    body.append(dl);

    if (evidence.source.url && /^https?:\/\//i.test(String(evidence.source.url))) {
      const source = documentObject.createElement("a");
      source.className = "ds-evidence-source-link";
      source.href = String(evidence.source.url);
      source.target = "_blank";
      source.rel = "noopener noreferrer";
      source.textContent = evidence.source.title ? `Source: ${evidence.source.title}` : "Open source";
      body.append(source);
    }

    addList(documentObject, body, "Assumptions", evidence.assumptions);
    addList(documentObject, body, "Rule trace", evidence.rule_trace);
    addList(documentObject, body, "Uncertainty", evidence.uncertainty);

    if (evidence.prerequisites.length) {
      const section = documentObject.createElement("section");
      section.className = "ds-evidence-section";
      const title = documentObject.createElement("h4");
      title.textContent = "Prerequisites";
      section.append(title);
      const list = documentObject.createElement("ul");
      for (const prerequisite of evidence.prerequisites) {
        const item = documentObject.createElement("li");
        item.dataset.prerequisiteState = prerequisite.state;
        const status = prerequisite.state === "satisfied" ? "Ready" : prerequisite.state[0].toUpperCase() + prerequisite.state.slice(1);
        item.textContent = `${status}: ${prerequisite.name}`;
        if (prerequisite.reason) item.append(documentObject.createTextNode(`. ${prerequisite.reason}`));
        if (prerequisite.remediation && prerequisite.state !== "satisfied") item.append(documentObject.createTextNode(` Next: ${prerequisite.remediation}`));
        list.append(item);
      }
      section.append(list);
      body.append(section);
    }

    details.append(body);
    return details;
  }

  function append(documentObject, parent, raw, options = {}) {
    if (!parent) return null;
    const node = render(documentObject, raw, options);
    parent.append(node);
    return node;
  }

  function install(root) {
    const documentObject = root?.document;
    if (!documentObject) return;
    documentObject.querySelectorAll("[data-evidence-json]").forEach((node) => {
      if (node.dataset.evidenceInstalled === "true") return;
      try {
        const evidence = JSON.parse(node.dataset.evidenceJson || "{}");
        node.replaceChildren(render(documentObject, evidence));
        node.dataset.evidenceInstalled = "true";
      } catch {
        node.textContent = "Evidence details unavailable";
        node.setAttribute("role", "status");
      }
    });
  }

  return {
    VERSION,
    KINDS,
    normalize,
    fromLegacy,
    freshnessText,
    confidenceText,
    summaryText,
    blockedPrerequisites,
    explainUnavailable,
    render,
    append,
    install,
  };
});
