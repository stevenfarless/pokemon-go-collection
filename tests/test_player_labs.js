"use strict";

const assert = require("node:assert/strict");
const Labs = require("../site/player-labs.js");

function memoryStorage() {
  const values = new Map();
  return { getItem: (key) => values.has(key) ? values.get(key) : null, setItem: (key, value) => values.set(key, String(value)), removeItem: (key) => values.delete(key) };
}

{
  assert.equal(Labs.unicodeLength("abc"), 3);
  assert.equal(Labs.unicodeLength("A😀B"), 3);
  assert.equal(Labs.fixedWidth(9, 3), "009");
  assert.equal(Labs.fixedWidth(100, 3), "100");
}

{
  const record = { ivs: { total: 42, average_percent: 93.3, attack: 15, defense: 14, stamina: 13 }, pvp: { great: { rank_percent: 97.2, rank_number: 42 } }, level: { minimum: 20, maximum: 20 }, moves: { fast: "Vine Whip", charged: "Sludge Bomb" }, status: { shadow_purified: "normal", favorite: true } };
  const rendered = Labs.renderTemplate("{iv45}-{iv1000}-{greatRank}", record, {}, 20);
  assert.equal(rendered.text, "42-0933-0042");
  assert.equal(rendered.overLimit, false);
  const tooLong = Labs.renderTemplate("abcdefghijkl😀", record, {}, 12);
  assert.equal(tooLong.length, 13);
  assert.equal(tooLong.overLimit, true);
}

{
  const storage = memoryStorage();
  Labs.saveLabState(storage, "naming_presets", { version: 1, presets: [{ id: "x", name: "X", template: "{iv45}" }], verified_symbols: ["★"] });
  Labs.saveLabState(storage, "gap_goals", { version: 1, exclusions: [1, 1, 2], goals: {} });
  const base = { product: "pokemon-go-collection-local-data", backup_version: 1, namespaces: {} };
  const extended = Labs.extendUnifiedBackup(base, storage);
  assert.equal(extended.namespaces.naming_presets.present, true);
  assert.equal(extended.namespaces.gap_goals.data.exclusions.length, 2);
  const preview = Labs.validateLabBackup(extended, memoryStorage()).preview;
  assert(preview.added.includes("naming_presets"));
}

{
  assert.throws(() => Labs.validateEliteTmVault({ version: 1, entries: [{ id: "x", record_id: "r", desired_move: "" }] }));
  assert.deepEqual(Labs.validateRosterLocks({ version: 1, by_type: { fire: ["a", "a", "b"] } }).by_type.fire, ["a", "b"]);
}

console.log("player labs unit tests passed");
