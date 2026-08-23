"use strict";

(function exposeDiagnostics(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionDiagnostics = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  async function fetchJson(root, path, options = {}) {
    try {
      const response = await root.fetch(path, options);
      if (!response.ok) return { ok: false, status: response.status, data: null };
      return { ok: true, status: response.status, data: await response.json() };
    } catch (error) {
      return { ok: false, status: 0, data: null, error: String(error?.message || error) };
    }
  }

  async function queryWorkerBuild(root) {
    const controller = root.navigator?.serviceWorker?.controller;
    if (!controller || typeof root.MessageChannel !== "function") return null;
    return new Promise((resolve) => {
      const channel = new root.MessageChannel();
      const timer = root.setTimeout(() => resolve(null), 800);
      channel.port1.onmessage = (event) => { root.clearTimeout(timer); resolve(event.data?.build_id || null); };
      controller.postMessage({ type: "GET_BUILD_ID" }, [channel.port2]);
    });
  }

  async function serviceWorkerStatus(root) {
    if (!("serviceWorker" in (root.navigator || {}))) return { supported: false, controlled: false, build_id: null, waiting: false };
    let registration = null;
    try { registration = await root.navigator.serviceWorker.getRegistration(); } catch { /* limited */ }
    return {
      supported: true,
      controlled: Boolean(root.navigator.serviceWorker.controller),
      build_id: await queryWorkerBuild(root),
      waiting: Boolean(registration?.waiting),
      active: Boolean(registration?.active),
    };
  }

  function capabilities(root) {
    return {
      clipboard: typeof root.navigator?.clipboard?.writeText === "function",
      web_share: typeof root.navigator?.share === "function",
      service_worker: "serviceWorker" in (root.navigator || {}),
      cache_storage: "caches" in root,
      storage_manager: Boolean(root.navigator?.storage),
      storage_persist: typeof root.navigator?.storage?.persist === "function",
      storage_estimate: typeof root.navigator?.storage?.estimate === "function",
      trusted_types: Boolean(root.trustedTypes),
    };
  }

  function classify(report) {
    if (!report.connectivity.online) return "Offline";
    if (!report.connectivity.manifest_reachable || report.storage?.state === "needs-attention" || report.build?.consistent === false) return "Needs attention";
    if (report.storage?.state === "limited" || !report.service_worker.controlled) return "Limited";
    return "Healthy";
  }

  async function run(root) {
    const manifestNetwork = await fetchJson(root, `data/build-manifest.json?diagnostics=${Date.now()}`, { cache: "no-store", credentials: "same-origin" });
    const manifestCached = manifestNetwork.ok ? manifestNetwork : await fetchJson(root, "data/build-manifest.json");
    const health = await fetchJson(root, "data/data-health.json");
    const external = await fetchJson(root, "data/external/index.json");
    const worker = await serviceWorkerStatus(root);
    const storage = root.CollectionStorageHealth ? await root.CollectionStorageHealth.healthReport(root) : null;
    const buildId = manifestCached.data?.build_id || null;
    const report = {
      generated_at: new Date().toISOString(),
      summary: "",
      connectivity: { online: root.navigator?.onLine !== false, manifest_reachable: manifestNetwork.ok, cached_manifest_available: manifestCached.ok },
      build: {
        build_id: buildId,
        source_file: manifestCached.data?.source_file || null,
        export_timestamp: manifestCached.data?.export_timestamp || null,
        service_worker_build_id: worker.build_id,
        consistent: worker.build_id ? worker.build_id === buildId : null,
      },
      service_worker: worker,
      data_health: health.ok ? { available: true, schema_version: health.data?.schema_version || null, state: health.data?.state || health.data?.status || null, blockers: health.data?.blockers || [] } : { available: false },
      external_freshness: external.ok ? {
        available: true,
        build_id: external.data?.build_id || null,
        categories: (external.data?.snapshots || []).map((item) => ({ category: item.data_category, freshness: item.freshness?.state || item.freshness_state || null, provider: item.provider?.name || item.provider || null })),
      } : { available: false },
      storage,
      capabilities: capabilities(root),
    };
    report.summary = classify(report);
    return report;
  }

  function diagnosticText(report) {
    const safe = {
      generated_at: report.generated_at,
      summary: report.summary,
      connectivity: report.connectivity,
      build: report.build,
      service_worker: report.service_worker,
      data_health: report.data_health,
      external_freshness: report.external_freshness,
      storage: report.storage ? {
        state: report.storage.state,
        write: report.storage.write,
        storage_manager: report.storage.storage_manager,
        last_backup_at: report.storage.last_backup_at,
        namespaces: report.storage.namespaces.map((item) => ({ name: item.name, schema_version: item.schema_version, status: item.status, bytes: item.bytes, unresolved: item.unresolved, recoverable: item.recoverable })),
      } : null,
      capabilities: report.capabilities,
    };
    return JSON.stringify(safe, null, 2);
  }

  function addRow(documentObject, list, label, value) {
    const row = documentObject.createElement("li");
    const strong = documentObject.createElement("strong"); strong.textContent = `${label}: `;
    row.append(strong, documentObject.createTextNode(String(value ?? "unknown")));
    list.append(row);
  }

  function install(root) {
    const documentObject = root.document;
    if (documentObject.getElementById("diagnostics-dialog")) return;
    const open = documentObject.createElement("button");
    open.id = "diagnostics-open"; open.type = "button"; open.textContent = "Diagnostics"; open.className = "data-health-action";
    const nav = documentObject.querySelector(".planner-section-nav,.data-menu nav,.tools-nav,.insights-nav") || documentObject.querySelector("header");
    nav?.append(open);

    const dialog = documentObject.createElement("dialog");
    dialog.id = "diagnostics-dialog"; dialog.className = "diagnostics-dialog";
    const heading = documentObject.createElement("h2"); heading.textContent = "Diagnostics and Storage Health";
    const summary = documentObject.createElement("p"); summary.id = "diagnostics-summary"; summary.setAttribute("role", "status"); summary.setAttribute("aria-live", "polite");
    const actions = documentObject.createElement("div"); actions.className = "diagnostics-actions";
    const runButton = documentObject.createElement("button"); runButton.type = "button"; runButton.textContent = "Run self-test";
    const persistButton = documentObject.createElement("button"); persistButton.type = "button"; persistButton.textContent = "Request persistent storage";
    const copyButton = documentObject.createElement("button"); copyButton.type = "button"; copyButton.textContent = "Copy diagnostics"; copyButton.disabled = true;
    const closeButton = documentObject.createElement("button"); closeButton.type = "button"; closeButton.textContent = "Close";
    actions.append(runButton, persistButton, copyButton, closeButton);
    const details = documentObject.createElement("details");
    const detailsSummary = documentObject.createElement("summary"); detailsSummary.textContent = "Technical detail";
    const list = documentObject.createElement("ul"); list.id = "diagnostics-details";
    details.append(detailsSummary, list);
    const recovery = documentObject.createElement("div"); recovery.id = "diagnostics-recovery";
    dialog.append(heading, summary, actions, details, recovery);
    documentObject.body.append(dialog);
    let lastReport = null;

    const render = (report) => {
      lastReport = report;
      summary.textContent = report.summary === "Healthy" ? "Healthy. Build, local storage, and available runtime checks look consistent." : `${report.summary}. Review the technical detail and suggested recovery actions.`;
      list.replaceChildren();
      addRow(documentObject, list, "Build", report.build.build_id);
      addRow(documentObject, list, "Source export", report.build.source_file);
      addRow(documentObject, list, "Network manifest", report.connectivity.manifest_reachable ? "reachable" : "unavailable");
      addRow(documentObject, list, "Service worker", report.service_worker.controlled ? `controlling (${report.service_worker.build_id || "version unknown"})` : "not controlling this page");
      addRow(documentObject, list, "Storage", report.storage?.state || "unavailable");
      addRow(documentObject, list, "Last local backup", report.storage?.last_backup_at || "unknown");
      if (report.storage?.storage_manager?.quota) addRow(documentObject, list, "Approximate storage", `${report.storage.storage_manager.usage || 0} / ${report.storage.storage_manager.quota} bytes`);
      recovery.replaceChildren();
      for (const item of report.storage?.namespaces || []) {
        if (item.status !== "corrupt" || !item.recoverable) continue;
        const button = documentObject.createElement("button");
        button.type = "button"; button.textContent = `Recover ${item.name} from last-known-good snapshot`;
        button.addEventListener("click", async () => {
          const result = root.CollectionStorageHealth.recoverNamespace(root.localStorage, item.name);
          summary.textContent = result.ok ? `${item.name} restored. Run the self-test again.` : `Recovery failed: ${result.error}`;
        });
        recovery.append(button);
      }
      copyButton.disabled = false;
    };

    const execute = async () => { summary.textContent = "Running browser-local self-test…"; render(await run(root)); };
    open.addEventListener("click", () => { dialog.showModal?.(); void execute(); });
    runButton.addEventListener("click", () => void execute());
    closeButton.addEventListener("click", () => dialog.close());
    persistButton.addEventListener("click", async () => {
      if (!root.CollectionStorageHealth) { summary.textContent = "Persistent-storage API is unavailable."; return; }
      const result = await root.CollectionStorageHealth.requestPersistence(root.navigator);
      summary.textContent = !result.supported ? "This browser does not expose a persistent-storage request." : result.granted === true ? "Persistent storage was granted. The browser can still clear data under exceptional conditions." : result.granted === false ? "Persistent storage was not granted. Backups remain the reliable recovery path." : "The persistence request outcome is unavailable.";
    });
    copyButton.addEventListener("click", async () => {
      if (!lastReport) return;
      const text = diagnosticText(lastReport);
      if (typeof root.navigator?.clipboard?.writeText === "function") {
        try { await root.navigator.clipboard.writeText(text); summary.textContent = "Diagnostics copied without collection records or note contents."; return; } catch { /* fallback below */ }
      }
      const area = documentObject.createElement("textarea"); area.value = text; documentObject.body.append(area); area.select(); summary.textContent = "Clipboard permission was unavailable. Diagnostic text is selected for manual copy.";
    });
  }

  return { fetchJson, queryWorkerBuild, serviceWorkerStatus, capabilities, classify, run, diagnosticText, install };
});
