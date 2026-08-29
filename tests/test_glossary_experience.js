"use strict";

const assert = require("node:assert/strict");
const glossary = require("../site/glossary-experience.js");

const entries = [
  {
    id: "iv-percent",
    term: "IV %",
    aliases: ["IV percentage"],
    definition: "A percentage summary of the appraisal IVs.",
    why_it_matters: "Exact IVs preserve the underlying distribution.",
    classification: "collection-derived",
  },
  {
    id: "pvp-rank",
    term: "PvP rank",
    aliases: ["league rank", "Poke Genie rank"],
    definition: "An IV ranking under a specified league cap.",
    why_it_matters: "Matchups and team role can change which copy performs best.",
    classification: "source-derived",
  },
  {
    id: "freshness",
    term: "Freshness",
    aliases: ["current data freshness"],
    definition: "Whether time-sensitive data remains inside its reviewed validity window.",
    why_it_matters: "Expired rotating data cannot support current-game instructions.",
    classification: "evidence-metadata",
  },
];

assert.equal(glossary.GLOSSARY_PATH, "data/knowledge/glossary.json");
assert.equal(glossary.findEntry(entries, "Poke Genie rank")?.id, "pvp-rank");
assert.equal(glossary.findEntry(entries, "iv %")?.id, "iv-percent");
assert.equal(glossary.findEntry(entries, "unknown"), null);

assert.deepEqual(
  glossary.searchEntries(entries, "pvp rank").map((entry) => entry.id),
  ["pvp-rank"],
);
assert.deepEqual(
  glossary.searchEntries(entries, "validity window").map((entry) => entry.id),
  ["freshness"],
);
assert.deepEqual(glossary.searchEntries(entries, ""), []);
assert.deepEqual(glossary.searchEntries(entries, "ranking exact"), []);

{
  const button = { dataset: { shareType: "event-plan", shareSource: "event-calendar.html" }, onclick: null };
  let stored = null;
  const root = {
    document: {
      title: "Event Calendar",
      querySelector: () => button,
      querySelectorAll: () => [{ dataset: { recordId: "owned-1" } }],
    },
    location: { search: "?record_id=owned-2", hash: "#today", href: "" },
    sessionStorage: { setItem: (key, value) => { stored = [key, value]; } },
  };
  assert.equal(glossary.installShareHandoff(root), true);
  button.onclick();
  assert.equal(stored[0], glossary.SHARE_DRAFT_KEY);
  const draft = JSON.parse(stored[1]);
  assert.equal(draft.packet_type, "event-plan");
  assert.deepEqual(draft.record_ids, ["owned-2", "owned-1"]);
  assert.deepEqual(draft.context, { source_page: "event-calendar.html" });
  assert.deepEqual(draft.links, ["event-calendar.html?record_id=owned-2#today"]);
  assert.equal(root.location.href, "tools.html#share-packets");
}

console.log("glossary experience tests passed");
