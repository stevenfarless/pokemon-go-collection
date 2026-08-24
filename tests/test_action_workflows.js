"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const workflows = require("../site/action-workflows.js");

const contract = {
  required_columns: ["Name", "Pokemon Number", "CP"],
  known_columns: ["Name", "Pokemon Number", "CP", "Form", "Atk IV", "Def IV", "Sta IV", "IV Avg", "Level Min", "Level Max", "Lucky", "Favorite", "Shadow/Purified"],
  integer_rules: {
    "Pokemon Number": { minimum: 1, maximum: null, integer: true, required: true },
    CP: { minimum: 1, maximum: null, integer: true, required: true },
    "Atk IV": { minimum: 0, maximum: 15, integer: true, required: false },
    "Def IV": { minimum: 0, maximum: 15, integer: true, required: false },
    "Sta IV": { minimum: 0, maximum: 15, integer: true, required: false },
  },
  number_rules: {
    "IV Avg": { minimum: 0, maximum: 100, integer: false, required: false },
    "Level Min": { minimum: 1, maximum: 51, integer: false, required: false },
    "Level Max": { minimum: 1, maximum: 51, integer: false, required: false },
  },
  status_columns: ["Shadow/Purified"],
  boolean_columns: ["Lucky", "Favorite"],
  true_values: ["1", "true", "yes", "y"],
  false_values: ["0", "false", "no", "n"],
};

{
  const parsed = workflows.parseCsv('Name,CP,Note\r\n"Mr. Mime",1234,"comma, and ""quote"""\r\n');
  assert.equal(parsed.rows.length, 1);
  assert.equal(parsed.rows[0].values.Name, "Mr. Mime");
  assert.equal(parsed.rows[0].values.Note, 'comma, and "quote"');
}

{
  assert.equal(workflows.validateFilename("shared-text-2026-08-23 03_27_00.000.csv").valid, true);
  assert.equal(workflows.validateFilename("shared-text-2026-02-30 03_27_00.000.csv").valid, false);
  assert.equal(workflows.validateFilename("pokemon.csv").valid, false);
}

{
  const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "preflight-cases.json"), "utf8"));
  for (const testCase of fixture.cases) {
    const result = workflows.analyzePreflight(testCase.filename, testCase.csv, contract, { records: [], export_timestamp: "2026-08-23T03:00:00.000" });
    assert.equal(result.accepted, testCase.accepted, testCase.name);
    if (testCase.unknown_columns) assert.deepEqual(result.columns.unknown, testCase.unknown_columns, testCase.name);
    if (testCase.warning_column) assert.ok(result.warnings.some((warning) => warning.column === testCase.warning_column), testCase.name);
  }
}

{
  const current = [{ name: "Pikachu", pokemon_number: 25, cp: 500, form: null }];
  const result = workflows.analyzePreflight("shared-text-2026-08-23 03_27_00.000.csv", "Name,Pokemon Number,CP\nPikachu,25,500\nRaichu,26,1200\n", contract, { records: current, export_timestamp: "2026-08-23T03:00:00.000" });
  assert.equal(result.comparison.matched, 1);
  assert.equal(result.comparison.new, 1);
  assert.equal(result.timestampOrder, "newer");
}

{
  const result = workflows.narrowRecordSearch({
    pokemon_number: 25,
    cp: 500,
    form: "Costume",
    ivs: { attack: 10, defense: 12, stamina: 13, is_hundo: false, is_nundo: false },
    status: { shadow_purified: "shadow", favorite: true, lucky: false },
    moves: { fast: "Thunder Shock", charged: "Wild Charge" },
  });
  assert.equal(result.exact, false);
  assert.match(result.search, /^25&cp500&shadow&favorite&@1Thunder Shock&@2Wild Charge$/);
  assert.ok(result.gaps.some((gap) => gap.includes("Exact non-hundo/nundo IV")));
  assert.ok(result.gaps.some((gap) => gap.includes("Canonical record ID")));
}

{
  assert.equal(
    workflows.githubUploadUrl({ hostname: "stevenfarless.github.io", pathname: "/pokemon-go-collection/scan-inbox.html" }),
    "https://github.com/stevenfarless/pokemon-go-collection/upload/main/exports",
  );
  assert.equal(workflows.githubUploadUrl({ hostname: "localhost", pathname: "/" }), null);
}
