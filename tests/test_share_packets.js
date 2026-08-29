"use strict";

const assert = require("assert");
const Packets = require("../site/share-packets.js");

{
  const packet = Packets.buildPacket({
    packet_type: "pokemon-decision",
    build_id: "abcdef123456",
    collection_generated_at: "2026-08-29T05:49:46Z",
    title: "Review Mewtwo investment",
    record_ids: ["record-1"],
    claims: [{ text: "Owned candidate", evidence: { authority: "Poke Genie", freshness: "current", ignored: "drop" } }],
    assumptions: ["No Elite TM planned"],
    unknowns: ["Current raid relevance unknown"],
    context: { friend_code: "1234", private_note: "secret", record_id: "record-1", cp: 4000 },
  }, { generatedAt: "2026-08-29T08:00:00Z" });
  assert.equal(packet.schema_version, "1.0.0");
  assert.equal(packet.build.id, "abcdef123456");
  assert.equal(packet.generated_at, "2026-08-29T08:00:00Z");
  assert.equal(packet.context.friend_code, undefined);
  assert.equal(packet.context.private_note, undefined);
  assert.equal(packet.context.record_id, "record-1");
  assert.equal(packet.privacy.full_collection_included, false);
  assert.deepEqual(packet.claims[0].evidence, { authority: "Poke Genie", freshness: "current" });
  assert.equal(Packets.validatePacket(packet).valid, true);
}

{
  const context = { collection: Array.from({ length: 50 }, (_, index) => ({ record_id: `r${index}` })), location: "private", useful: true };
  const packet = Packets.buildPacket({ packet_type: "diagnostic", build_id: "abcdef123456", context }, { generatedAt: "2026-08-29T08:00:00Z" });
  assert.equal(packet.context.collection, "[omitted 50 collection records]");
  assert.equal(packet.context.location, undefined);
  assert.equal(packet.context.useful, true);
}

{
  const packet = Packets.buildPacket({ packet_type: "trade-shortlist", build_id: "abcdef123456", record_ids: Array.from({ length: 20 }, (_, index) => `r${index}`), claims: "A gives X\nB gives Y" }, { generatedAt: "2026-08-29T08:00:00Z" });
  assert.equal(packet.subject.record_ids.length, Packets.LIMITS.record_ids);
  assert(Packets.toMarkdown(packet).includes("Full collection excluded"));
  assert(Packets.toMachineJson(packet).includes('"schema_version": "1.0.0"'));
  assert(Packets.toPrintableHtml(packet).includes("<!doctype html>"));
}

{
  const packet = Packets.buildPacket({ packet_type: "resource-plan", build_id: "abcdef123456", context: { friend_code: "1234" } }, { generatedAt: "2026-08-29T08:00:00Z", includeSensitive: true });
  assert.equal(packet.context.friend_code, "1234");
  assert.equal(packet.privacy.sensitive_fields_included, true);
}

assert.throws(() => Packets.buildPacket({ packet_type: "unknown", build_id: "abcdef123456" }), /Unsupported packet type/);
assert.throws(() => Packets.buildPacket({ packet_type: "team" }), /build ID is required/);

console.log("share packet tests passed");
