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
  const CRITICAL_RESOURCES = [
    "data/pokemon.json",
    "data/collection-summary.json",
    "data/data-health.json",
    "data/external/index.json",
  ];
  const FRESH_STATES = new Set(["fresh", "current", "valid"]);

  async function fetchJson(root, path, options = {}) {
    try {
      const response = await root.fetch(path, options);
      if (!response.ok) return { ok: false, status: response.status, data: null };
      return { ok: true, status: response.status, data: await response.json() };
    } catch (error) {
      return { ok: false, status: 0, data: null, error: String(error?.message || error) };
    }
  }

  function buildIdOf(payload) {
    return payload?.build_id || payload?.manifest?.build_id || payload?.metadata?.build_id || null;
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
    if (!("serviceWorker" in (root.navigator || {}))) return { supported: false, controlled: false, build_id: null, waiting: false, active: false };
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

  async function criticalResourceStatus(root, expectedBuildId) {
    return Promise.all(CRITICAL_RESOURCES.map(async (path) => {
      const result = await fetchJson(root, path);
      const resourceBuildId = result.ok ? buildIdOf(result.data) : null;
      return {
        path,
        reachable: result.ok,
        status: result.status,
        build_id: resourceBuildId,
        matches_active_build: resourceBuildId && expectedBuildId ? resourceBuildId === expectedBuildId : null,
      };
    }));
  }

  function collectIssues(report) {
    const issues = [];
    const add = (severity, code, message, action) => issues.push({ severity, code, message, action });
    const online = report.connectivity?.online !== false;

    if (online && !report.connectivity?.manifest_reachable) {
      add("error", "manifest-unreachable", "The current build manifest could not be reached from the network.", "Retry the self-test after checking connectivity. Keep cached data until a coherent current build is available.");
    }
    if (!report.connectivity?.cached_manifest_available) {
      add("error", "manifest-unavailable", "No current or cached build manifest is available.", "Reconnect and reload the application so a complete build can be retrieved.");
    }
    if (report.build?.consistent === false) {
      add("error", "service-worker-build-mismatch", `The controlling service worker (${report.build.service_worker_build_id || "unknown"}) does not match build ${report.build.build_id || "unknown"}.`, "Use the normal app update/reload flow. Do not clear site data unless safer update recovery fails.");
    }
    if (report.service_worker?.waiting) {
      add("warning", "service-worker-update-waiting", "A newer service worker is installed and waiting to activate.", "Finish or save local edits, then use the normal update/reload flow.");
    } else if (report.service_worker?.supported && !report.service_worker?.controlled) {
      add("warning", "service-worker-uncontrolled", "This page is not currently controlled by the service worker.", "Reload once while online. If control is still absent, inspect the service-worker detail before changing stored data.");
    }

    for (const resource of report.critical_resources || []) {
      if (online && !resource.reachable) {
        add("error", "critical-resource-unreachable", `${resource.path} is unavailable.`, "Retry while online. Keep the last coherent cached build rather than replacing it with partial data.");
      } else if (resource.matches_active_build === false) {
        add("error", "critical-resource-build-mismatch", `${resource.path} belongs to build ${resource.build_id || "unknown"}, not ${report.build?.build_id || "the active build"}.`, "Reload through the normal update path so all resources come from one build.");
      }
    }

    const blockers = report.data_health?.blockers || [];
    if (blockers.length) {
      add("error", "data-health-blockers", `Data health reports ${blockers.length} blocker(s).`, "Review Data Health and repair the source/export problem before making consequential collection decisions.");
    }

    const stale = (report.external_freshness?.categories || []).filter((item) => !FRESH_STATES.has(String(item.freshness || "unknown").toLowerCase()));
    if (stale.length) {
      add("warning", "external-data-stale", `${stale.length} current-game data category or categories are stale, expired, unavailable, or unknown.`, "Treat affected current-game advice as unavailable until the reviewed external-data refresh succeeds.");
    }

    if (report.storage?.write?.ok === false) {
      add("error", "storage-write-failed", "Browser-local state could not be written safely.", "Export or preserve a local backup first, then check browser storage/quota settings before editing local plans.");
    }
    for (const namespace of report.storage?.namespaces || []) {
      if (namespace.status === "corrupt") {
        add("error", "local-namespace-corrupt", `${namespace.name} local state is corrupt.`, namespace.recoverable ? `Recover ${namespace.name} from its last-known-good snapshot, then rerun the self-test.` : `Export unaffected local state and repair ${namespace.name} without clearing unrelated site data.`);
      } else if (Number(namespace.unresolved || 0) > 0) {
        add("warning", "local-namespace-unresolved", `${namespace.name} has ${namespace.unresolved} unresolved mapping(s).`, "Review unresolved mappings before relying on that local planning data for exact-record actions.");
      }
    }
    if (report.storage?.state === "needs-attention" && !issues.some((item) => item.code.startsWith("storage-") || item.code.startsWith("local-namespace"))) {
      add("error", "storage-needs-attention", "Browser-local storage health needs attention.", "Open Storage Health details and preserve a backup before attempting repair.");
    } else if (report.storage?.state === "limited") {
      add("warning", "storage-limited", "Browser-local storage is operating with limited durability or capability.", "Keep recent local backups and review persistence/quota information.");
    }
    return issues;
  }

  function classify(report) {
    if (report.connectivity?.online === false) return "Offline";
    const issues = report.issues || collectIssues(report);
    if (issues.some((item) => item.severity === "error")) return "Needs attention";
    if (issues.some((item) => item.severity === "warning")) return "Limited";
    return "Healthy";
  }

  function assess(report) {
    const evaluated = { ...report };
    evaluated.issues = collectIssues(evaluated);
    evaluated.summary = classify(evaluated);
    return evaluated;
  }

  async function run(root) {
    const manifestNetwork = await fetchJson(root, `data/build-manifest.json?diagnostics=${Date.now()}`, { cache: "no-store", credentials: "same-origin" });
    const manifestCached = manifestNetwork.ok ? manifestNetwork : await fetchJson(root, "data/build-manifest.json");
    const health = await fetchJson(root, "data/data-health.json");
    const external = await fetchJson(root, "data/external/index.json");
    const worker = await serviceWorkerStatus(root);
    const storage = root.CollectionStorageHealth ? await root.CollectionStorageHealth.healthReport(root) : null;
    const buildId = manifestCached.data?.build_id || null;
    const criticalResources = await criticalResourceStatus(root, buildId);
    return assess({
      generated_at: new Date().toISOString(),
      summary: "",
      connectivity: { online: root.navigator?.onLine !== false, manifest_reachable: manifestNetwork.ok, cached_manifest_available: manifestCached.ok },
      build: {
        build_id: buildId,
        source_file: manifestCached.data?.source_file || null,
        export_timestamp: manifestCached.data?.export_timestamp || null,
        service_worker_build_id: worker.build_id,
        consistent: worker.build_id && buildId ? worker.build_id === buildId : null,
      },
      service_worker: worker,
      critical_resources: criticalResources,
      data_health: health.ok ? { available: true, schema_version: health.data?.schema_version || null, state: health.data?.state || health.data?.status || null, blockers: health.data?.blockers || [] } : { available: false, blockers: [] },
      external_freshness: external.ok ? {
        available: true,
        build_id: external.data?.build_id || null,
        categories: (external.data?.snapshots || []).map((item) => ({ category: item.data_category, freshness: item.freshness?.state || item.freshness_state || "unknown", provider: item.provider?.name || item.provider || null })),
      } : { available: false, categories: [] },
      storage,
      capabilities: capabilities(root),
    });
  }

  function diagnosticText(report) {
    const safe = {
      generated_at: report.generated_at,
      summary: report.summary,
      issues: report.issues || collectIssues(report),
      connectivity: report.connectivity,
      build: report.build,
      service_worker: report.service_worker,
      critical_resources: report.critical_resources,
      data_health: report.data_health,
      external_freshness: report.external_freshness,
      storage: report.storage ? {
        state: report.storage.state,
        write: report.storage.write,
        storage_manager: report.storage.storage_manager,
        last_backup_at: report.storage.last_backup_at,
        namespaces: (report.storage.namespaces || []).map((item) => ({ name: item.name, schema_version: item.schema_version, status: item.status, bytes: item.bytes, unresolved: item.unresolved, recoverable: item.recoverable })),
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
      addRow(documentObject, list, "Critical resources", `${(report.critical_resources || []).filter((item) => item.reachable).length}/${(report.critical_resources || []).length} reachable`);
      addRow(documentObject, list, "Storage", report.storage?.state || "unavailable");
      addRow(documentObject, list, "Last local backup", report.storage?.last_backup_at || "unknown");
      if (report.storage?.storage_manager?.quota) addRow(documentObject, list, "Approximate storage", `${report.storage.storage_manager.usage || 0} / ${report.storage.storage_manager.quota} bytes`);
      recovery.replaceChildren();
      for (const issue of report.issues || []) {
        const note = documentObject.createElement("p");
        const strong = documentObject.createElement("strong"); strong.textContent = `${issue.message} `;
        note.append(strong, documentObject.createTextNode(issue.action));
        recovery.append(note);
      }
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

  return { CRITICAL_RESOURCES, fetchJson, buildIdOf, queryWorkerBuild, serviceWorkerStatus, capabilities, criticalResourceStatus, collectIssues, classify, assess, run, diagnosticText, install };
});
