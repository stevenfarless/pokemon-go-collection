"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(path.resolve(__dirname, "..", "site", "sw.js"), "utf8");

assert.match(source, /FIELD_PACK_RESOURCE_LIMIT = 256/);
assert.match(source, /INSTALL_FIELD_PACK/);
assert.match(source, /REMOVE_FIELD_PACK/);
assert.match(source, /LIST_FIELD_PACKS/);
assert.match(source, /same-origin resources only/);
assert.match(source, /Probe requests cannot be included in a field pack/);
assert.match(source, /await cache\.addAll\(resources\)/);
assert.match(source, /Field pack verification failed/);
assert.match(source, /await caches\.delete\(cacheName\)/);
assert.match(source, /previous complete pack is retained until the replacement has fully cached/);
assert.match(source, /const fieldPack = await caches\.match\(event\.request, \{ ignoreSearch: true \}\)/);

const installIndex = source.indexOf("await cache.addAll(resources)");
const oldPackDeleteIndex = source.indexOf("filter((key) => key.startsWith(fieldPackCachePrefix(id)) && key !== cacheName)");
assert.ok(installIndex >= 0 && oldPackDeleteIndex > installIndex, "old pack cleanup must happen only after replacement caching");

console.log("offline field pack tests passed");
