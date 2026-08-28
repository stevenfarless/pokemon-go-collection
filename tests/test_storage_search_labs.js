"use strict";

const assert = require("assert");
const Registry = require("../knowledge/search-operator-registry.json");
const Labs = require("../site/storage-search-labs.js");

function record(id, dex, name, cp, iv = 80, extras = {}) {
  return {
    identity: { record_id: id }, pokemon_number: dex, name, form: "", cp,
    level: { minimum: 20, maximum: 20 },
    ivs: { average_percent: iv, attack: 10, defense: 10, stamina: 10, is_hundo: iv === 100, is_nundo: false },
    moves: { fast: "Tackle", charged: "Body Slam", charged_second: null },
    status: { favorite: false, lucky: false, marked_for_pvp: false, shadow_purified: "normal" },
    dates: { scan: "2026-08-28T00:00:00Z" },
    pvp: { great: { rank_percent: 50 }, ultra: { rank_percent: 50 }, little: { rank_percent: 50 } },
    ...extras,
  };
}

function explicitNoCollectorState() {
  return {
    shiny: "no", costume: "no", background: "no", dynamax: "no", gigantamax: "no",
    reserved_trade: "no", legacy_move_review: "no",
  };
}

{
  assert.equal(Labs.fixtureHealth(Registry), true);
  const broken = JSON.parse(JSON.stringify(Registry));
  broken.semantic_fixtures[0].operators = ["hp"];
  assert.equal(Labs.fixtureHealth(broken), false);
  const gated = Labs.analyzeSearch("shiny", broken);
  assert.equal(gated.valid, true);
  assert.equal(gated.verified_exact, false);
  assert(gated.warnings.some((warning) => warning.includes("semantic fixtures")));
}

{
  const examples = ["cp300", "cp-300", "cp300-", "cp200-300", "distance1000-1200", "dynamax", "gigantamax", "fusion", "hypertraining", "4*", "2defense", "!favorite", "@special", "ultrabeast", "ultra beasts"];
  for (const expression of examples) {
    const result = Labs.analyzeSearch(expression, Registry);
    assert.equal(result.valid, true, expression);
    assert.equal(result.verified_exact, true, expression);
  }
  const combined = Labs.analyzeSearch("electric,@weather", Registry);
  assert.equal(combined.valid, true);
  assert.deepEqual(combined.joins, [","]);
  assert.equal(Labs.analyzeSearch("(shiny|costume)&!favorite", Registry).valid, false);
  assert.equal(Labs.analyzeSearch("cpbanana", Registry).valid, false);
  const bare = Labs.analyzeSearch("Pikachu", Registry);
  assert.equal(bare.valid, true);
  assert.equal(bare.verified_exact, false);
}

{
  const built = Labs.buildToken("cp", "200-300", false, Registry);
  assert.equal(built.ok, true);
  assert.equal(built.token, "cp200-300");
  const negate = Labs.buildToken("shiny", "", true, Registry);
  assert.equal(negate.ok, true);
  assert.equal(negate.token, "!shiny");
  const bad = Labs.buildToken("megalevel", "99", false, Registry);
  assert.equal(bad.ok, false);
}

{
  const values = new Map();
  const storage = {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
  };
  Labs.saveTemplate(storage, "Cleanup", "!favorite&!shiny");
  Labs.saveTemplate(storage, "cleanup", "!favorite&!costume");
  const payload = Labs.loadTemplates(storage);
  assert.equal(payload.templates.length, 1);
  assert.equal(payload.templates[0].expression, "!favorite&!costume");
}

{
  const records = [
    record("keeper", 25, "Pikachu", 1000, 96),
    record("safe-review", 25, "Pikachu", 500, 80),
    record("unknown-review", 25, "Pikachu", 450, 70),
    record("protected-shiny", 25, "Pikachu", 400, 60),
  ];
  const enrichment = {
    keeper: explicitNoCollectorState(),
    "safe-review": explicitNoCollectorState(),
    "protected-shiny": { ...explicitNoCollectorState(), shiny: "yes" },
  };
  const plan = Labs.buildCleanupPlan(records, { slotsNeeded: 1, ivThreshold: 90, aggressiveness: "aggressive" }, {
    enrichment,
    annotations: {},
    decisionById: new Map(),
    referenceTimestamp: "2026-08-28T12:00:00Z",
  });
  const byId = new Map(plan.candidates.map((item) => [item.record_id, item]));
  assert.equal(byId.get("safe-review").tier, "conservative");
  assert.equal(byId.get("unknown-review").tier, "aggressive");
  assert.equal(byId.get("protected-shiny").tier, "protected");
  assert.equal(plan.automatic_transfer_safe, false);
  assert.equal(plan.enough_review_candidates, true);
  assert.equal(plan.group_keepers[0].record_id, "keeper");
}

{
  const candidate = { record_id: "x", pokemon_number: 25, name: "Pikachu", cp: 500, tier: "conservative" };
  const locator = Labs.cleanupLocator(candidate, Registry, 90);
  assert.equal(locator.syntax_verified, true);
  assert.equal(locator.exact_record_selector, false);
  assert(locator.expression.includes("!favorite"));
  assert(locator.expression.includes("!gigantamax"));
  assert(locator.representational_gaps.some((item) => item.includes("canonical record ID")));
  assert(locator.representational_gaps.some((item) => item.includes("90.0%")));
}

{
  const plan = {
    iv_threshold: 90,
    candidates: [
      { record_id: "a", pokemon_number: 1, name: "Bulbasaur", cp: 100, tier: "conservative" },
      { record_id: "b", pokemon_number: 2, name: "Ivysaur", cp: 200, tier: "protected" },
    ],
  };
  const state = { decisions: { a: "approve", b: "approve" } };
  const batches = Labs.buildApprovedBatches(plan, state, Registry);
  assert.equal(batches.length, 1);
  assert.equal(batches[0].record_id, "a");
  assert.equal(batches[0].exact_record_selector, false);
}

console.log("storage cleanup and Pokémon GO search builder tests passed");
