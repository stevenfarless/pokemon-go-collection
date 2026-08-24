"use strict";

const assert = require("node:assert");
const Product = require("../site/product-experience.js");

assert.equal(Product.normalizeGuidance("EXPERT"), "expert");
assert.equal(Product.normalizeGuidance("unknown"), "essential");

const now = Date.parse("2026-08-23T12:00:00Z");
assert.equal(Product.runtimeFresh({
  dataset_timestamp: "2026-08-23T10:00:00Z",
  freshness: { state: "fresh", max_age_hours: 6 },
  validity: { valid_until: "2026-08-23T18:00:00Z" },
}, now), true);
assert.equal(Product.runtimeFresh({
  dataset_timestamp: "2026-08-22T10:00:00Z",
  freshness: { state: "fresh", max_age_hours: 6 },
  validity: {},
}, now), false);
assert.equal(Product.runtimeFresh({
  dataset_timestamp: "2026-08-23T10:00:00Z",
  freshness: { state: "stale", max_age_hours: 6 },
  validity: {},
}, now), false);

const exact = { title: "Pikachu", subtitle: "CP 500", terms: ["25", "electric"], domain: "owned-record" };
const partial = { title: "Pikachu family", subtitle: "Reference", terms: ["electric"], domain: "family" };
assert(Product.scoreSearchItem(exact, "pikachu") > Product.scoreSearchItem(partial, "pikachu"));
assert.equal(Product.scoreSearchItem(exact, "mewtwo"), 0);

assert.equal(Product.factMatchesSpecies({ species_id: "PIKACHU", reward: "x" }, "PIKACHU", 25), true);
assert.equal(Product.factMatchesSpecies({ boss_dexes: [25, 26] }, "PIKACHU", 25), true);
assert.equal(Product.factMatchesSpecies({ dex: 26 }, "PIKACHU", 25), false);

const params = new URL("https://example.invalid/reference.html?type=Electric&search=pika").searchParams;
assert.equal(Product.matchesReferenceQuery({ display_name: "Pikachu", types: ["Electric"], form_aliases: [] }, params), true);
assert.equal(Product.matchesReferenceQuery({ display_name: "Raichu", types: ["Electric"], form_aliases: [] }, params), false);

assert.equal(Product.GUIDANCE_KEY, "pokemon-go-collection:guidance:v1");
assert.equal(Product.TODAY_STATE_KEY, "pokemon-go-collection:today-dismissals:v1");
assert(Product.GLOSSARY["PvP rank"].includes("not a current-meta ranking"));

console.log("product experience tests passed");
