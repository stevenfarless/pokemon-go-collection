"use strict";
const assert = require("node:assert/strict");
const Security = require("../site/security.js");

assert.equal(Security.safeUrl("javascript:alert(1)", "https://example.test/"), null);
assert.equal(Security.safeUrl("data:text/html,<script>alert(1)</script>", "https://example.test/"), null);
assert.equal(Security.safeUrl("/collection?q=%3Cimg%20src=x%20onerror=alert(1)%3E", "https://example.test/").startsWith("https://example.test/"), true);
assert.deepEqual(Security.safeJsonParse('{"note":"<img src=x onerror=alert(1)>"}').value, { note: "<img src=x onerror=alert(1)>" });
assert.equal(Security.safeJsonParse("{broken").ok, false);
console.log("security boundary tests passed");
