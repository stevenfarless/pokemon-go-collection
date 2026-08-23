"use strict";

const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const source = fs.readFileSync(path.resolve(__dirname, "..", "site", "i18n.js"), "utf8");
assert(source.includes("CATALOG_VERSION"));
assert(source.includes("en-XA"));
assert(source.includes("Intl.DateTimeFormat"));
assert(source.includes("Intl.RelativeTimeFormat"));
assert(source.includes("Intl.Collator"));
assert(source.includes("pokemon-go-collection:timezone:v1"));
assert(source.includes("pokemon-go-collection:locale:v1"));
assert(!source.includes("pokemon_number === \""));
console.log("i18n architecture tests passed");
