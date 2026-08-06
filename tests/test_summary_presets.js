"use strict";

const assert = require("assert");
const Presets = require("../site/dashboard.js").SummaryPresets;

class FakeEvent {
  constructor(type, options = {}) {
    this.type = type;
    Object.assign(this, options);
  }
}

function element(value = "") {
  return {
    value,
    textContent: value,
    events: [],
    clicks: 0,
    dispatchEvent(event) { this.events.push(event); },
    click() { this.clicks += 1; },
  };
}

function fixture() {
  const elements = {
    "page-size": element("100"),
    "reset-filters": element(),
    "total-count": element("4,571"),
    "species-count": element("798"),
    "hundo-count": element("31"),
    "shadow-count": element("196"),
    "lucky-count": element("9"),
    "highest-cp": element("4,274"),
    "summary-shortcut-status": element(),
    "hundo-filter": element("any"),
    "status-filter": element("any"),
    "lucky-filter": element("any"),
    "cp-min": element(""),
    "cp-max": element(""),
  };
  const nameHeader = element();
  const cpHeader = element();
  const documentObject = {
    getElementById(id) { return elements[id] || null; },
    querySelector(selector) {
      if (selector === '[data-sort-key="name"]') return nameHeader;
      if (selector === '[data-sort-key="cp"]') return cpHeader;
      return null;
    },
  };
  const root = { Event: FakeEvent, MouseEvent: FakeEvent };
  return { elements, nameHeader, cpHeader, documentObject, root };
}

assert.strictEqual(Presets.numericText({ textContent: "4,274 max CP" }), 4274);

{
  const { elements, documentObject, root } = fixture();
  assert.strictEqual(Presets.applySummaryPreset(documentObject, root, "hundos"), true);
  assert.strictEqual(elements["hundo-filter"].value, "yes");
  assert.strictEqual(elements["hundo-filter"].events.at(-1).type, "input");
  assert.match(elements["summary-shortcut-status"].textContent, /31 hundos/);
}

{
  const { elements, documentObject, root } = fixture();
  Presets.applySummaryPreset(documentObject, root, "max-cp");
  assert.strictEqual(elements["cp-min"].value, "4274");
  assert.strictEqual(elements["cp-max"].value, "4274");
  assert.strictEqual(elements["cp-max"].events.at(-1).type, "input");
}

{
  const { nameHeader, cpHeader, documentObject, root } = fixture();
  Presets.applySummaryPreset(documentObject, root, "species");
  assert.strictEqual(nameHeader.clicks, 1);
  assert.strictEqual(cpHeader.events.at(-1).shiftKey, true);
}

console.log("Summary shortcut preset tests passed.");
