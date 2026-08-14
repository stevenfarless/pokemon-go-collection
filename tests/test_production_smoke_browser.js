"use strict";

const assert = require("assert");
const {
  isIgnorableRequestFailure,
  runWithRetry,
} = require("../scripts/production_smoke_browser.js");

function failedRequest(url, errorText) {
  return {
    url: () => url,
    failure: () => ({ errorText }),
  };
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
      isIgnorableRequestFailure(failedRequest(baseUrl, "net::ERR_ABORTED"), baseUrl),
      true,
      "the exact same-origin collection root abort seen after Pages deployment should be ignored",
    );
    assert.equal(
      isIgnorableRequestFailure(failedRequest(`${baseUrl}?verify=abc`, "net::ERR_ABORTED"), baseUrl),
      true,
      "query parameters do not change the collection-root path",
    );
    assert.equal(
      isIgnorableRequestFailure(failedRequest(`${baseUrl}data/pokemon.json`, "net::ERR_ABORTED"), baseUrl),
      false,
      "aborted canonical data requests remain fatal",
    );
    assert.equal(
      isIgnorableRequestFailure(failedRequest(baseUrl, "net::ERR_CONNECTION_RESET"), baseUrl),
      false,
      "real root-page network failures remain fatal",
    );
    assert.equal(
      isIgnorableRequestFailure(
        failedRequest("https://example.com/pokemon-go-collection/", "net::ERR_ABORTED"),
        baseUrl,
      ),
      false,
      "cross-origin aborts remain fatal",
    );
  }

  console.log("production browser smoke retry and request-failure tests passed");
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
