"use strict";
const assert = require("node:assert/strict");
const Pwa = require("../site/pwa-lifecycle.js");

(async () => {
  let copied = "";
  const clipboardRoot = { navigator: { clipboard: { async writeText(value) { copied = value; } } } };
  const clipboardResult = await Pwa.share(clipboardRoot, { text: "safe share" });
  assert.equal(clipboardResult.ok, true);
  assert.equal(clipboardResult.method, "clipboard");
  assert.equal(copied, "safe share");

  let shared = null;
  const shareRoot = { navigator: { async share(payload) { shared = payload; } } };
  const shareResult = await Pwa.share(shareRoot, { title: "Collection", url: "https://example.test/" });
  assert.equal(shareResult.ok, true);
  assert.equal(shareResult.method, "share");
  assert.deepEqual(shared, { title: "Collection", url: "https://example.test/" });

  const unsupported = await Pwa.share({ navigator: {} }, { text: "x" });
  assert.equal(unsupported.ok, false);
  assert.equal(unsupported.method, "none");

  let scheduledDelay = null;
  let scheduledCallback = null;
  const completeRoot = {
    document: { readyState: "complete" },
    setTimeout(callback, delay) {
      scheduledCallback = callback;
      scheduledDelay = delay;
    },
  };
  let registrationStarted = false;
  Pwa.scheduleServiceWorkerRegistration(completeRoot, () => { registrationStarted = true; });
  assert.equal(registrationStarted, false, "service worker work must not compete with initial page startup");
  assert.equal(scheduledDelay, Pwa.SERVICE_WORKER_START_DELAY_MS);
  scheduledCallback();
  assert.equal(registrationStarted, true);

  let loadHandler = null;
  const loadingRoot = {
    document: { readyState: "interactive" },
    addEventListener(type, handler, options) {
      assert.equal(type, "load");
      assert.deepEqual(options, { once: true });
      loadHandler = handler;
    },
    setTimeout(callback, delay) {
      assert.equal(delay, Pwa.SERVICE_WORKER_START_DELAY_MS);
      scheduledCallback = callback;
    },
  };
  Pwa.scheduleServiceWorkerRegistration(loadingRoot, () => { registrationStarted = true; });
  assert.ok(loadHandler, "registration should wait for the page load event");
  registrationStarted = false;
  loadHandler();
  assert.equal(registrationStarted, false);
  scheduledCallback();
  assert.equal(registrationStarted, true);

  console.log("pwa lifecycle tests passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
