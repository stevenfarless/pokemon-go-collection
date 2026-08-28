"use strict";

const assert = require("node:assert");
const Evidence = require("../site/evidence.js");

{
  const official = Evidence.normalize({
    kind: "official-current",
    freshness: { state: "fresh" },
    source: { url: "https://example.test/event" },
  });
  const simulation = Evidence.normalize({
    kind: "simulation",
    confidence: { state: "medium" },
    source: { model_version: "raid-model-1" },
  });
  assert.strictEqual(official.kind, "official-current");
  assert.match(Evidence.summaryText(official), /Official/);
  assert.match(Evidence.summaryText(official), /Fresh/);
  assert.strictEqual(simulation.kind, "simulation");
  assert.match(Evidence.summaryText(simulation), /Simulation/);
  assert.doesNotMatch(Evidence.summaryText(simulation), /Official/);
}

{
  const stale = Evidence.fromLegacy({
    evidence_layer: "Official · stale",
  });
  assert.strictEqual(stale.kind, "official-current");
  assert.strictEqual(stale.freshness.state, "stale");
  assert.match(Evidence.summaryText(stale), /Stale/);
}

{
  const blocked = Evidence.normalize({
    kind: "unknown",
    prerequisites: [{
      name: "current mechanic",
      state: "unsupported",
      reason: "No reviewed mechanic is available.",
      remediation: "Wait for reviewed mechanics data.",
    }],
  });
  const explanation = Evidence.explainUnavailable(blocked);
  assert.strictEqual(blocked.kind, "unknown");
  assert.strictEqual(explanation.reason, "No reviewed mechanic is available.");
  assert.strictEqual(explanation.remediation, "Wait for reviewed mechanics data.");
  assert.notStrictEqual(blocked.kind, false);
  assert.notStrictEqual(blocked.kind, 0);
}

{
  const calculated = Evidence.fromLegacy({
    evidence_layer: "Calculated from owned collection facts",
    confidence: "high",
  });
  assert.strictEqual(calculated.kind, "calculated");
  assert.strictEqual(calculated.freshness.state, "not-applicable");
}

console.log("evidence contract tests passed");
