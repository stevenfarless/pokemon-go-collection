"use strict";

const assert = require("assert");
const { runWithRetry } = require("../scripts/production_smoke_browser.js");

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

  console.log("production browser smoke retry tests passed");
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
