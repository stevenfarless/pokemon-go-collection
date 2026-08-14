"use strict";

(function exposeAdvancedSearch(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionAdvancedSearch = api;
  if (root?.document) {
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", () => api.install(root), { once: true });
    else api.install(root);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const EXTENDED_FIELDS = new Set(["type", "family", "dex", "attack", "defense", "stamina", "hp", "mega"]);
  const POKEMON_TYPES = new Set([
    "bug", "dark", "dragon", "electric", "fairy", "fighting", "fire", "flying", "ghost",
    "grass", "ground", "ice", "normal", "poison", "psychic", "rock", "steel", "water",
  ]);
  const UNSUPPORTED_CONCEPTS = new Set(["shiny", "shinies", "costume", "costumes", "background", "backgrounds", "dynamax", "gigantamax"]);

  const normalize = (value) => String(value ?? "").trim().toLocaleLowerCase();
  const slug = (value) => normalize(value).replace(/[’']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  function levenshtein(left, right) {
    const a = normalize(left);
    const b = normalize(right);
    if (a === b) return 0;
    if (!a.length) return b.length;
    if (!b.length) return a.length;
    let previous = Array.from({ length: b.length + 1 }, (_, index) => index);
    for (let i = 1; i <= a.length; i += 1) {
      const current = [i];
      for (let j = 1; j <= b.length; j += 1) {
        current[j] = Math.min(
          current[j - 1] + 1,
          previous[j] + 1,
          previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
        );
      }
      previous = current;
    }
    return previous[b.length];
  }

  function fuzzyThreshold(term) {
    const length = normalize(term).length;
    if (length <= 3) return 0;
    if (length <= 5) return 1;
    if (length <= 9) return 2;
    return 3;
  }

  function fuzzyTokenMatch(term, candidates) {
    const wanted = normalize(term);
    if (!wanted) return true;
    const threshold = fuzzyThreshold(wanted);
    return candidates.some((candidate) => {
      const value = normalize(candidate);
      if (!value) return false;
      if (value.includes(wanted) || wanted.includes(value)) return true;
      return threshold > 0 && levenshtein(wanted, value) <= threshold;
    });
  }

  function tokenCandidates(record) {
    const values = [
      record?.name,
      record?.form,
      record?.moves?.fast,
      record?.moves?.charged,
      record?.moves?.charged_second,
      record?.status?.shadow_purified,
      record?.gender,
      record?.pvp?.great?.evolution_name,
      record?.pvp?.ultra?.evolution_name,
      record?.pvp?.little?.evolution_name,
    ].filter(Boolean);
    const tokens = [];
    for (const value of values) {
      const normalized = normalize(value);
      tokens.push(normalized);
      tokens.push(...normalized.split(/[^a-z0-9]+/).filter(Boolean));
    }
    return [...new Set(tokens)];
  }

  function fuzzyPlainMatches(record, query, appEngine) {
    const parsed = appEngine.parseSearchQuery(query || "");
    if (!parsed.positive.length && !parsed.negative.length) return true;
    const haystack = appEngine.recordSearchText(record);
    const tokens = tokenCandidates(record);
    const positive = parsed.positive.every((term) => {
      if (haystack.includes(term)) return true;
      if (term.includes(" ")) return false;
      return fuzzyTokenMatch(term, tokens);
    });
    if (!positive) return false;
    return parsed.negative.every((term) => !haystack.includes(term));
  }

  function normalizeTypeWord(value) {
    let text = normalize(value);
    if (text.endsWith("s") && POKEMON_TYPES.has(text.slice(0, -1))) text = text.slice(0, -1);
    return POKEMON_TYPES.has(text) ? text : null;
  }

  function compileNaturalLanguage(query, speciesNames = new Set()) {
    const original = String(query || "").trim();
    let working = original;
    const terms = [];
    const unsupported = [];
    const reasons = [];

    const structuredSignal = /\b(?:under|below|over|above|at least|up to)\s+\d+(?:\.\d+)?\s*(?:cp|iv|level)\b/i.test(working)
      || /\b(?:great|ultra|little)\s+league\b/i.test(working)
      || [...POKEMON_TYPES].some((type) => new RegExp(`\\b${type}s\\b`, "i").test(working));

    working = working.replace(/\b(great|ultra|little)\s+league\b/gi, (_match, league) => {
      terms.push(`pvp:${normalize(league)}`);
      reasons.push(`${league} League`);
      return " ";
    });

    working = working.replace(/\b(under|below|over|above|at least|up to)\s+(\d+(?:\.\d+)?)\s*(cp|iv|level)\b/gi, (_match, operator, rawNumber, field) => {
      const number = Number(rawNumber);
      const normalizedField = normalize(field);
      let value;
      if (["under", "below"].includes(normalize(operator))) {
        const maximum = normalizedField === "cp" ? Math.max(0, Math.ceil(number) - 1) : Math.max(0, number - 0.01);
        value = `0-${maximum}`;
      } else if (["over", "above"].includes(normalize(operator))) {
        const minimum = normalizedField === "cp" ? Math.floor(number) + 1 : number + 0.01;
        value = `${minimum}+`;
      } else if (normalize(operator) === "up to") {
        value = `0-${number}`;
      } else {
        value = `${number}+`;
      }
      terms.push(`${normalizedField}:${value}`);
      reasons.push(`${operator} ${rawNumber} ${field}`);
      return " ";
    });

    for (const type of POKEMON_TYPES) {
      const expression = new RegExp(`\\b${type}s\\b`, "gi");
      working = working.replace(expression, () => {
        terms.push(`type:${type}`);
        reasons.push(`${type} type`);
        return " ";
      });
    }

    if (structuredSignal) {
      const statusPatterns = [
        ["shadow", "shadow"], ["shadows", "shadow"], ["purified", "purified"],
        ["lucky", "lucky"], ["luckies", "lucky"], ["hundo", "hundo"], ["hundos", "hundo"],
        ["nundo", "nundo"], ["nundos", "nundo"],
      ];
      for (const [word, status] of statusPatterns) {
        const expression = new RegExp(`\\b${word}\\b`, "gi");
        if (expression.test(working)) {
          working = working.replace(expression, " ");
          terms.push(`status:${status}`);
          reasons.push(`${status} status`);
        }
      }
    }

    for (const concept of UNSUPPORTED_CONCEPTS) {
      if (new RegExp(`\\b${concept}\\b`, "i").test(working)) unsupported.push(concept.replace(/s$/, ""));
    }

    const cleanedWords = working.replace(/\s+/g, " ").trim().split(" ").filter(Boolean);
    if (cleanedWords.length === 1 && speciesNames.has(normalize(cleanedWords[0]))) {
      terms.push(`name:${cleanedWords[0]}`);
      reasons.push(`species ${cleanedWords[0]}`);
      working = "";
    }

    const plain = working.replace(/\s+/g, " ").trim();
    return {
      original,
      terms: [...new Set(terms)],
      plain,
      unsupported: [...new Set(unsupported)],
      reasons,
      changed: terms.length > 0 || plain !== original,
    };
  }

  function parseExtendedPlain(plainQuery, baseSearch) {
    const extended = [];
    const plainParts = [];
    const invalid = [];
    const expression = /(-?)(?:([a-z][a-z-]*):(?:"([^"]*)"|(\S+))|"([^"]+)"|(\S+))/gi;
    let match;
    while ((match = expression.exec(String(plainQuery || ""))) !== null) {
      const negated = match[1] === "-";
      const field = normalize(match[2]);
      const fieldValue = match[3] ?? match[4];
      const quotedPlain = match[5];
      const barePlain = match[6];
      if (field && EXTENDED_FIELDS.has(field)) {
        const value = String(fieldValue || "").trim();
        let valid = Boolean(value);
        if (["dex", "attack", "defense", "stamina", "hp"].includes(field)) {
          const limits = field === "dex" || field === "hp"
            ? { minimum: 0, integer: true }
            : { minimum: 0, maximum: 15, integer: true };
          valid = Boolean(baseSearch.parseNumericConstraint(value, limits));
        } else if (field === "type") valid = Boolean(normalizeTypeWord(value));
        else if (field === "mega") valid = ["yes", "no", "true", "false"].includes(normalize(value));
        if (valid) extended.push({ field, value, negated });
        else {
          invalid.push(match[0]);
          plainParts.push(match[0]);
        }
      } else if (quotedPlain !== undefined) {
        plainParts.push(`${negated ? "-" : ""}"${quotedPlain}"`);
      } else if (barePlain) {
        plainParts.push(`${negated ? "-" : ""}${barePlain}`);
      } else if (field) {
        plainParts.push(match[0]);
      }
    }
    return { extended, plainQuery: plainParts.join(" "), invalid };
  }

  function buildKnowledgeIndex(payload) {
    const byDex = new Map();
    const speciesNames = new Set();
    for (const entry of payload?.entries || []) {
      const dex = Number(entry.dex);
      if (!byDex.has(dex)) byDex.set(dex, []);
      byDex.get(dex).push(entry);
      speciesNames.add(normalize(entry.display_name));
      const base = normalize(String(entry.display_name || "").replace(/\s*\([^)]*\)\s*$/, ""));
      if (base) speciesNames.add(base);
    }
    return { byDex, speciesNames, datasetVersion: payload?.dataset_version || null };
  }

  function knowledgeEntriesFor(record, knowledge) {
    const entries = knowledge?.byDex?.get(Number(record?.pokemon_number)) || [];
    if (entries.length <= 1) return entries;
    const form = slug(record?.form || "normal") || "normal";
    const exact = entries.filter((entry) => slug(entry.form_key || "normal") === form || (entry.form_aliases || []).some((alias) => slug(alias) === form));
    return exact.length ? exact : entries.filter((entry) => !entry.transformation_kind);
  }

  function matchesExtendedTerm(record, term, baseSearch, knowledge) {
    const value = normalize(term.value);
    let matched = false;
    if (["dex", "attack", "defense", "stamina", "hp"].includes(term.field)) {
      const constraint = baseSearch.parseNumericConstraint(value, {
        minimum: 0,
        maximum: ["attack", "defense", "stamina"].includes(term.field) ? 15 : undefined,
        integer: true,
      });
      const actual = term.field === "dex" ? record?.pokemon_number
        : term.field === "hp" ? record?.hp
          : record?.ivs?.[term.field];
      matched = constraint ? Number(actual) >= constraint.minimum && (constraint.maximum === null || Number(actual) <= constraint.maximum) : false;
    } else {
      const entries = knowledgeEntriesFor(record, knowledge);
      if (term.field === "type") {
        const type = normalizeTypeWord(value);
        matched = Boolean(type) && entries.some((entry) => (entry.types || []).map(normalize).includes(type));
      } else if (term.field === "family") {
        const wanted = slug(value);
        matched = entries.some((entry) => slug(entry.family_id || "") === wanted || slug(entry.display_name || "") === wanted || slug(entry.species_id || "") === wanted);
      } else if (term.field === "mega") {
        const wanted = ["yes", "true"].includes(value);
        const transformationEntries = knowledge?.byDex?.get(Number(record?.pokemon_number)) || [];
        const eligible = transformationEntries.some((entry) => ["mega", "primal"].includes(normalize(entry.transformation_kind)));
        matched = eligible === wanted;
      }
    }
    return term.negated ? !matched : matched;
  }

  function serializeBaseTerms(terms) {
    return terms.map((term) => {
      const value = /\s/.test(term.value) ? `"${term.value.replaceAll('"', '')}"` : term.value;
      return `${term.negated ? "-" : ""}${term.field}:${value}`;
    }).join(" ");
  }

  function compileQuery(query, baseSearch, speciesNames = new Set()) {
    const natural = compileNaturalLanguage(query, speciesNames);
    const expanded = [...natural.terms, natural.plain].filter(Boolean).join(" ");
    const base = baseSearch.parseQualifiedQuery(expanded);
    const extended = parseExtendedPlain(base.plainQuery, baseSearch);
    const structuredQuery = [serializeBaseTerms(base.qualified), ...extended.extended.map((term) => `${term.negated ? "-" : ""}${term.field}:${term.value}`), extended.plainQuery]
      .filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
    return {
      original: String(query || ""),
      baseTerms: base.qualified,
      extendedTerms: extended.extended,
      plainQuery: extended.plainQuery,
      invalid: [...base.invalid, ...extended.invalid],
      unsupported: natural.unsupported,
      structuredQuery,
      naturalReasons: natural.reasons,
      requiresKnowledge: extended.extended.some((term) => ["type", "family", "mega"].includes(term.field)),
    };
  }

  function enhanceHelp(documentObject) {
    const card = documentObject.querySelector(".search-help-card");
    if (!card || card.querySelector("[data-advanced-search-help]")) return;
    const wrapper = documentObject.createElement("div");
    wrapper.dataset.advancedSearchHelp = "true";
    wrapper.innerHTML = '<p><strong>Structured collection search:</strong> <code>type:dragon</code> <code>family:eevee</code> <code>dex:25</code> <code>attack:15</code> <code>hp:100+</code> <code>mega:yes</code>.</p><p>Common typos use local fuzzy matching. Shortcuts such as <code>shadow dragons under 1500 cp</code> are compiled into inspectable structured terms. Unsupported concepts are reported instead of guessed.</p>';
    card.append(wrapper);
  }

  function ensureInterpretationElement(documentObject, root) {
    let element = documentObject.getElementById("search-interpretation");
    if (element) return element;
    element = documentObject.createElement("p");
    element.id = "search-interpretation";
    element.className = "insight-note";
    element.hidden = true;
    const status = documentObject.getElementById("search-syntax-status");
    status?.insertAdjacentElement("afterend", element);
    element.addEventListener("click", (event) => {
      const button = event.target.closest?.("button[data-use-structured]");
      if (!button) return;
      const search = documentObject.getElementById("search");
      if (!search) return;
      search.value = button.dataset.useStructured || "";
      search.dispatchEvent(new root.Event("input", { bubbles: true }));
      search.focus();
    });
    return element;
  }

  function renderInterpretation(documentObject, root, compiled, loadingKnowledge = false) {
    const element = ensureInterpretationElement(documentObject, root);
    const notes = [];
    if (loadingKnowledge) notes.push("Loading the versioned species index for this query.");
    if (compiled.naturalReasons.length) notes.push(`Interpreted: ${compiled.structuredQuery || compiled.original}.`);
    if (compiled.invalid.length) notes.push(`Malformed structured terms remain ordinary text: ${compiled.invalid.join(", ")}.`);
    if (compiled.unsupported.length) notes.push(`Unsupported by the current normalized collection: ${compiled.unsupported.join(", ")}.`);
    if (!notes.length) {
      element.hidden = true;
      element.textContent = "";
      return;
    }
    element.hidden = false;
    element.textContent = `${notes.join(" ")} `;
    if (compiled.naturalReasons.length && compiled.structuredQuery && compiled.structuredQuery !== compiled.original) {
      const button = documentObject.createElement("button");
      button.type = "button";
      button.dataset.useStructured = compiled.structuredQuery;
      button.textContent = "Use structured query";
      element.append(button);
    }
  }

  function install(root) {
    const engine = root.CollectionFilterEngine;
    const baseSearch = root.CollectionDashboard?.QualifiedSearch;
    const appEngine = root.CollectionFilterEngine;
    if (!engine || !baseSearch || engine.__advancedSearchInstalled) return null;

    const originalMatchesRecord = engine.matchesRecord;
    let knowledge = null;
    let knowledgePromise = null;
    let lastQuery = null;
    let lastCompiled = null;

    const ensureKnowledge = () => {
      if (knowledge) return Promise.resolve(knowledge);
      if (!knowledgePromise) {
        knowledgePromise = root.fetch("data/knowledge/species-index.json")
          .then((response) => {
            if (!response.ok) throw new Error("Species search index could not be loaded");
            return response.json();
          })
          .then((payload) => {
            knowledge = buildKnowledgeIndex(payload);
            const search = root.document?.getElementById("search");
            if (search?.value) search.dispatchEvent(new root.Event("input", { bubbles: true }));
            return knowledge;
          })
          .catch(() => {
            knowledge = { byDex: new Map(), speciesNames: new Set(), datasetVersion: null, unavailable: true };
            return knowledge;
          });
      }
      return knowledgePromise;
    };

    engine.matchesRecord = function matchesRecordWithAdvancedSearch(record, filters = {}) {
      const query = String(filters.query || "").trim();
      if (query !== lastQuery) {
        lastQuery = query;
        lastCompiled = compileQuery(query, baseSearch, knowledge?.speciesNames || new Set());
        if (lastCompiled.requiresKnowledge && !knowledge) ensureKnowledge();
        if (root.document) root.queueMicrotask?.(() => renderInterpretation(root.document, root, lastCompiled, lastCompiled.requiresKnowledge && !knowledge));
      }
      const compiled = lastCompiled || compileQuery(query, baseSearch, knowledge?.speciesNames || new Set());
      if (compiled.requiresKnowledge && !knowledge) return false;
      if (!compiled.extendedTerms.every((term) => matchesExtendedTerm(record, term, baseSearch, knowledge))) return false;
      if (!fuzzyPlainMatches(record, compiled.plainQuery, appEngine)) return false;
      const baseQuery = serializeBaseTerms(compiled.baseTerms);
      return originalMatchesRecord(record, { ...filters, query: baseQuery });
    };
    Object.defineProperty(engine, "__advancedSearchInstalled", { value: true, configurable: true });

    if (root.document) {
      enhanceHelp(root.document);
      ensureInterpretationElement(root.document, root);
      const search = root.document.getElementById("search");
      if (search?.value) {
        const compiled = compileQuery(search.value, baseSearch, knowledge?.speciesNames || new Set());
        renderInterpretation(root.document, root, compiled, compiled.requiresKnowledge && !knowledge);
        if (compiled.requiresKnowledge) ensureKnowledge();
      }
    }
    return { originalMatchesRecord, ensureKnowledge };
  }

  return {
    EXTENDED_FIELDS,
    POKEMON_TYPES,
    UNSUPPORTED_CONCEPTS,
    levenshtein,
    fuzzyThreshold,
    fuzzyTokenMatch,
    fuzzyPlainMatches,
    compileNaturalLanguage,
    parseExtendedPlain,
    buildKnowledgeIndex,
    matchesExtendedTerm,
    compileQuery,
    install,
  };
});
