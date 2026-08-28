"use strict";

const assert = require("assert");
const Labs = require("../site/trade-resource-labs.js");

function canonical(id, dex, name, form = "", cp = 100) {
  return { identity: { record_id: id }, pokemon_number: dex, name, form, cp, ivs: { average_percent: 80 }, status: {}, pvp: {} };
}

{
  const parsed = { rows: [
    { rowNumber: 2, values: { Name: "Eevee", "Pokemon Number": "133", CP: "500", Form: "" } },
    { rowNumber: 3, values: { Name: "Eevee", "Pokemon Number": "133", CP: "510", Form: "" } },
  ] };
  const guest = Labs.guestRecordsFromParsed(parsed);
  assert.equal(guest.length, 2);
  assert.equal(guest[0].guest_id, "guest-row-1");
  assert(guest[0].collector_unknown.includes("shiny"));
}

{
  const a = [
    canonical("a-keeper", 25, "Pikachu", "", 900),
    canonical("a-review", 25, "Pikachu", "", 500),
  ];
  const b = [
    { guest_id: "guest-row-1", pokemon_number: 133, name: "Eevee", form: "", cp: 500 },
    { guest_id: "guest-row-2", pokemon_number: 133, name: "Eevee", form: "", cp: 510 },
  ];
  const result = Labs.buildTradeMatcher(a, b, { entries: [] }, {});
  assert.equal(result.possible_mutual_wins.length, 1);
  assert.equal(result.possible_mutual_wins[0].a_gives.candidates[0].record_id, "a-review");
  assert.equal(result.possible_mutual_wins[0].a_gives.candidates[0].safe_to_trade, false);
  assert.equal(result.possible_mutual_wins[0].b_gives.candidates[0].safe_to_trade, false);
  assert(result.possible_mutual_wins[0].b_gives.candidates[0].collector_unknown.includes("background"));
  assert.equal(result.possible_mutual_wins[0].lucky_guaranteed, false);
  assert.equal(result.possible_mutual_wins[0].exact_stardust_cost, null);
  const markdown = Labs.shortlistMarkdown(result);
  assert(markdown.includes("Pikachu"));
  assert(!markdown.includes("guest-row-1"));
}

{
  const enrichment = { records: { protected: { shiny: "yes", reserved_trade: "yes" } } };
  const reasons = Labs.canonicalProtectionReasons(canonical("protected", 1, "Bulbasaur"), enrichment);
  assert(reasons.includes("user-confirmed shiny"));
  assert(reasons.includes("reserved for trade"));
}

{
  const vault = Labs.sanitizeVault({
    version: 1,
    balances: { stardust: { amount: 1000, reserve: 200 }, rare_candy_xl: { amount: null, reserve: 0 } },
    commitments: [{ id: "c1", name: "Reserve build", resource: "stardust", amount: 300, active: true }],
    plans: [
      { id: "p1", name: "First", priority: 10, selected: true, costs: { stardust: 400 } },
      { id: "p2", name: "Second", priority: 5, selected: true, costs: { stardust: 300 } },
      { id: "p3", name: "XL idea", priority: 1, selected: true, costs: { rare_candy_xl: 5 } },
    ],
    history: [],
  });
  const evaluated = Labs.evaluateVault(vault);
  assert.equal(evaluated.plan_results[0].state, "feasible");
  assert.equal(evaluated.plan_results[1].state, "blocked");
  assert.equal(evaluated.plan_results[2].state, "unknown");
  assert.equal(evaluated.unknown_is_zero, false);
  assert(evaluated.conflicts.some((item) => item.kind === "plan-overdraw"));
  assert(evaluated.plan_results[2].scarce_resource_warnings.includes("rare_candy_xl"));
}

{
  const migrated = Labs.migrateLegacyBudget(Labs.blankVault(), { dust: 12345, candy: 999 });
  assert.equal(migrated.balances.stardust.amount, 12345);
  assert.equal(migrated.balances.species_candy, undefined);
  let snap = Labs.blankVault();
  snap.balances.stardust = { amount: 10, reserve: 0, expires_at: "", note: "" };
  for (let i = 0; i < 20; i += 1) snap = Labs.snapshotVault(snap, `2026-08-${String(i + 1).padStart(2, "0")}T00:00:00Z`);
  assert.equal(snap.history.length, Labs.HISTORY_LIMIT);
}

{
  const values = new Map();
  const storage = {
    getItem(key) { return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { values.set(key, String(value)); },
    removeItem(key) { values.delete(key); },
  };
  const localApi = {
    buildUnifiedBackup() { return { product: "pokemon-go-collection-local-data", backup_version: 1, namespaces: {} }; },
    validateUnifiedBackup(raw) { return { envelope: raw, preview: { added: [], replaced: [], absent: [], ignored: ["resource_vault"] } }; },
    restoreUnifiedBackup() { values.set("base-restored", "yes"); return {}; },
  };
  const vault = Labs.blankVault();
  vault.balances.stardust = { amount: 777, reserve: 100, expires_at: "", note: "" };
  storage.setItem(Labs.RESOURCE_KEY, JSON.stringify(vault));
  const backup = Labs.buildUnifiedBackupWithVault(localApi, storage);
  assert.equal(backup.namespaces.resource_vault.present, true);
  assert.equal(backup.namespaces.resource_vault.data.balances.stardust.amount, 777);
  const validated = Labs.validateUnifiedBackupWithVault(localApi, backup, storage, []);
  assert(validated.preview.replaced.includes("resource_vault"));
  values.delete(Labs.RESOURCE_KEY);
  Labs.restoreUnifiedBackupWithVault(localApi, storage, backup, []);
  assert.equal(JSON.parse(storage.getItem(Labs.RESOURCE_KEY)).balances.stardust.amount, 777);
}

console.log("trade matcher and resource vault tests passed");
