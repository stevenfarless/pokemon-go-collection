"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const {
  isConnectivityProbeResponse,
  runWithRetry,
} = require("../scripts/production_smoke_browser.js");

function response(url) {
  return { url: () => url };
}

(async () => {
  {
    let calls = 0;
    const pauses = [];
    const result = await runWithRetry(async () => {
      calls += 1;
      if (calls === 1) throw new Error("HTTP 503: transient Pages propagation");
      return "passed";
    }, {
      attempts: 3,
      delayMs: 17,
      sleep: async (ms) => pauses.push(ms),
    });
    assert.equal(result, "passed");
    assert.equal(calls, 2);
    assert.deepEqual(pauses, [17]);
  }

  {
    let calls = 0;
    await assert.rejects(
      () => runWithRetry(async () => {
        calls += 1;
        throw new Error("impossible search returned collection rows");
      }, {
        attempts: 3,
        delayMs: 0,
        sleep: async () => {},
      }),
      /failed after 3 attempts: impossible search returned collection rows/,
    );
    assert.equal(calls, 3);
  }

  {
    let calls = 0;
    await assert.rejects(
      () => runWithRetry(async () => {
        calls += 1;
        throw new Error("fatal browser errors: pageerror: real bug");
      }, {
        attempts: 2,
        delayMs: 0,
        sleep: async () => {},
      }),
      /failed after 2 attempts: fatal browser errors/,
    );
    assert.equal(calls, 2);
  }

  {
    const baseUrl = "https://stevenfarless.github.io/pokemon-go-collection/";
    assert.equal(
      isConnectivityProbeResponse(response(`${baseUrl}data/build-manifest.json?connectivity=123`)),
      true,
      "the cache-busting build-manifest request is the connectivity probe",
    );
    assert.equal(
      isConnectivityProbeResponse(response(`${baseUrl}data/build-manifest.json?smoke=123`)),
      false,
      "ordinary smoke manifest fetches must not be mistaken for the connectivity probe",
    );
    assert.equal(
      isConnectivityProbeResponse(response(`${baseUrl}data/pokemon.json?connectivity=123`)),
      false,
      "only the build manifest is accepted as a connectivity probe",
    );
    assert.equal(isConnectivityProbeResponse(response("not a url")), false);
  }

  {
    const smokeSource = fs.readFileSync(path.join(__dirname, "..", "scripts", "production_smoke_browser.js"), "utf8");
    assert.equal(smokeSource.includes("isIgnorableRequestFailure"), false, "production smoke must not retain a root-request abort exception");
    assert(smokeSource.includes('page.on("requestfailed"'), "request failures must remain deployment-fatal");
    assert(smokeSource.includes("offline banner visible during healthy online load"), "healthy online state must be explicitly verified");
  }

  console.log("production browser smoke retry and connectivity tests passed");
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
