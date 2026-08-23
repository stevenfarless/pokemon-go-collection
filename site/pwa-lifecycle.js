"use strict";

(function exposePwaLifecycle(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionPwaLifecycle = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  function editableSection(element) {
    return element?.closest?.("#annotations,#enrichment,#collection-goals,#resource-optimizer,#local-data-backup") || null;
  }

  function createStatusUi(documentObject) {
    let panel = documentObject.getElementById("pwa-lifecycle-status");
    if (panel) return panel;
    panel = documentObject.createElement("aside");
    panel.id = "pwa-lifecycle-status";
    panel.className = "pwa-lifecycle-status";
    panel.setAttribute("role", "status");
    panel.setAttribute("aria-live", "polite");
    const message = documentObject.createElement("span");
    message.dataset.pwaMessage = "true";
    const install = documentObject.createElement("button");
    install.type = "button"; install.dataset.pwaInstall = "true"; install.textContent = "Install"; install.hidden = true;
    const update = documentObject.createElement("button");
    update.type = "button"; update.dataset.pwaUpdate = "true"; update.textContent = "Apply update"; update.hidden = true;
    const reload = documentObject.createElement("button");
    reload.type = "button"; reload.dataset.pwaReload = "true"; reload.textContent = "Reload"; reload.hidden = true;
    panel.append(message, install, update, reload);
    documentObject.body.append(panel);
    return panel;
  }

  function install(root) {
    const documentObject = root.document;
    const panel = createStatusUi(documentObject);
    const message = panel.querySelector("[data-pwa-message]");
    const installButton = panel.querySelector("[data-pwa-install]");
    const updateButton = panel.querySelector("[data-pwa-update]");
    const reloadButton = panel.querySelector("[data-pwa-reload]");
    const dirty = new Set();
    let deferredInstall = null;
    let registration = null;
    let waitingWorker = null;

    const show = (text) => { if (message) message.textContent = String(text || ""); panel.hidden = false; };
    const dirtyCount = () => dirty.size;
    const markClean = (section) => { if (section) dirty.delete(section); };

    documentObject.addEventListener("input", (event) => {
      const section = editableSection(event.target);
      if (section) dirty.add(section);
    }, true);
    documentObject.addEventListener("change", (event) => {
      const section = editableSection(event.target);
      if (section && event.target?.type !== "file") dirty.add(section);
    }, true);
    documentObject.addEventListener("click", (event) => {
      const button = event.target?.closest?.("button");
      if (!button) return;
      if (/^(save-|add-goal|clear-|apply-local-data-restore|run-optimizer)/.test(button.id || "")) markClean(editableSection(button));
    }, true);

    root.addEventListener?.("beforeinstallprompt", (event) => {
      event.preventDefault();
      deferredInstall = event;
      installButton.hidden = false;
      show("This browser can install the collection for standalone use.");
    });
    installButton.addEventListener("click", async () => {
      if (!deferredInstall) return;
      deferredInstall.prompt();
      try { await deferredInstall.userChoice; } catch { /* browser controls prompt outcome */ }
      deferredInstall = null;
      installButton.hidden = true;
    });
    root.addEventListener?.("appinstalled", () => { installButton.hidden = true; show("Collection installed."); });

    const exposeWaiting = (worker) => {
      waitingWorker = worker;
      updateButton.hidden = false;
      show("A newer collection build is ready. Apply it when local edits are saved.");
    };

    updateButton.addEventListener("click", () => {
      if (dirtyCount()) {
        show(`Save or finish ${dirtyCount()} local edit area${dirtyCount() === 1 ? "" : "s"} before applying the update.`);
        return;
      }
      const worker = registration?.waiting || waitingWorker;
      if (!worker) { show("No waiting update is available."); return; }
      worker.postMessage({ type: "SKIP_WAITING" });
      show("Applying the cached update. Reload will remain under your control.");
    });

    reloadButton.addEventListener("click", () => {
      if (dirtyCount()) { show("Finish local edits before reloading."); return; }
      root.location.reload();
    });

    root.addEventListener?.("offline", () => show("Offline. Cached resources remain available where previously stored."));
    root.addEventListener?.("online", () => show("Online. Checking for an updated build."));

    if (!("serviceWorker" in (root.navigator || {}))) {
      show("PWA installation and offline control are unavailable in this browser. Ordinary navigation still works.");
      return { supported: false, dirty };
    }

    root.navigator.serviceWorker.addEventListener("controllerchange", () => {
      updateButton.hidden = true;
      reloadButton.hidden = false;
      show("Update applied. Reload when convenient to use the new build.");
    });

    root.navigator.serviceWorker.register("sw.js").then((value) => {
      registration = value;
      if (registration.waiting) exposeWaiting(registration.waiting);
      registration.addEventListener("updatefound", () => {
        const installing = registration.installing;
        installing?.addEventListener("statechange", () => {
          if (installing.state === "installed" && root.navigator.serviceWorker.controller) exposeWaiting(registration.waiting || installing);
        });
      });
      if (!root.navigator.onLine) show("Offline. Using the installed collection cache where available.");
    }).catch((error) => show(`Offline support could not initialize: ${error?.message || error}`));

    return { supported: true, dirty, get registration() { return registration; } };
  }

  async function share(root, payload) {
    if (typeof root?.navigator?.share === "function") {
      try { await root.navigator.share(payload); return { method: "share", ok: true }; } catch (error) { return { method: "share", ok: false, error }; }
    }
    const text = String(payload?.text || payload?.url || "");
    if (text && typeof root?.navigator?.clipboard?.writeText === "function") {
      try { await root.navigator.clipboard.writeText(text); return { method: "clipboard", ok: true }; } catch (error) { return { method: "clipboard", ok: false, error }; }
    }
    return { method: "none", ok: false };
  }

  return { editableSection, createStatusUi, install, share };
});
