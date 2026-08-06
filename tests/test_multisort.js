"use strict";

const assert = require("node:assert/strict");
const {
  normalizeSorts,
  parseSortParam,
  serializeSorts,
  sortRecordsByCriteria,
} = require("../site/app.js");

function record(name, cp, iv, attack, defense, stamina, scan, pvpPercent, pvpRank) {
  return {
    name,
    form: "",
    pokemon_number: 1,
    cp,
    hp: 100,
    ivs: {
      average_percent: iv,
      attack,
      defense,
      stamina,
    },
    level: { minimum: 20 },
    dates: { catch: "2026-01-01", scan },
    pvp: {
      great: { rank_percent: pvpPercent, rank_number: pvpRank },
    },
  };
}

assert.deepEqual(
  parseSortParam("iv-desc"),
  [
    { field: "iv", direction: "desc" },
    { field: "cp", direction: "desc" },
  ],
);

assert.deepEqual(
  parseSortParam("cp:desc,iv:desc,name:asc"),
  [
    { field: "cp", direction: "desc" },
    { field: "iv", direction: "desc" },
    { field: "name", direction: "asc" },
  ],
);

assert.equal(
  serializeSorts([
    { field: "cp", direction: "desc" },
    { field: "iv", direction: "desc" },
  ]),
  "cp:desc,iv:desc",
);

assert.deepEqual(
  normalizeSorts([
    { field: "cp", direction: "desc" },
    { field: "cp", direction: "asc" },
    { field: "unknown", direction: "asc" },
  ]),
  [{ field: "cp", direction: "desc" }],
);

const records = [
  record("C", 2000, 95, 15, 14, 14, "2026-08-01", 99, 20),
  record("B", 2000, 98, 15, 15, 14, "2026-08-02", 98, 30),
  record("A", 2000, 98, 15, 15, 14, "2026-08-03", 98, 10),
  record("D", 1500, 100, 15, 15, 15, "2026-08-04", null, null),
];

assert.deepEqual(
  sortRecordsByCriteria(
    records,
    [
      { field: "cp", direction: "desc" },
      { field: "iv", direction: "desc" },
      { field: "name", direction: "asc" },
    ],
    "great",
  ).map(({ name }) => name),
  ["A", "B", "C", "D"],
);

assert.deepEqual(
  sortRecordsByCriteria(
    records,
    [
      { field: "pvp", direction: "desc" },
      { field: "pvp-rank", direction: "asc" },
    ],
    "great",
  ).map(({ name }) => name),
  ["C", "A", "B", "D"],
);

assert.deepEqual(
  sortRecordsByCriteria(
    records,
    [{ field: "scan", direction: "asc" }],
    "great",
  ).map(({ name }) => name),
  ["C", "B", "A", "D"],
);

console.log("Multi-column sorting tests passed.");
