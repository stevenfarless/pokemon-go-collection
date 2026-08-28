"use strict";

const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const css = fs.readFileSync(path.resolve(__dirname, "..", "site", "design-system.css"), "utf8");
for (const token of ["--ds-surface", "--ds-text", "--ds-focus", "--ds-success", "--ds-warning", "--ds-danger", "--ds-target-min", "--ds-target-comfort"]) assert(css.includes(token));
assert(css.includes("prefers-color-scheme:dark"));
assert(css.includes("prefers-reduced-motion:reduce"));
assert(css.includes("forced-colors:active"));
for (const pattern of [".ds-card", ".ds-pill", ".ds-notice", ".ds-segmented", ".ds-source-chip", ".ds-danger-confirm", ".ds-evidence", ".ds-evidence-body", "data-evidence-kind"]) assert(css.includes(pattern));
console.log("design system tests passed");
