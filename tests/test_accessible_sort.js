"use strict";

const assert = require("node:assert/strict");
const accessibility = require("../site/accessibility.js");

function fakeHeader(initial = null) {
  const attributes = new Map();
  if (initial) attributes.set("aria-sort", initial);
  return {
    hasAttribute(name) { return attributes.has(name); },
    setAttribute(name, value) { attributes.set(name, value); },
    getAttribute(name) { return attributes.get(name) ?? null; },
  };
}

function fakeButton(header) {
  const attributes = new Map([["aria-label", "CP, sort priority 1, descending"]]);
  return {
    removeAttribute(name) { attributes.delete(name); },
    setAttribute(name, value) { attributes.set(name, value); },
    getAttribute(name) { return attributes.get(name) ?? null; },
    closest(selector) { return selector === "th" ? header : null; },
  };
}

const header = fakeHeader("descending");
const button = fakeButton(header);
accessibility.normalizeSortHeader(button, "sort-instructions");
assert.equal(button.getAttribute("aria-label"), null);
assert.equal(button.getAttribute("aria-describedby"), "sort-instructions");
assert.equal(header.getAttribute("aria-sort"), "descending");

const unsortedHeader = fakeHeader();
const unsortedButton = fakeButton(unsortedHeader);
accessibility.normalizeSortHeader(unsortedButton, "sort-instructions");
assert.equal(unsortedHeader.getAttribute("aria-sort"), "none");

console.log("Accessible sort-header tests passed");
