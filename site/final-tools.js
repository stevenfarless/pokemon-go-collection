"use strict";

(function exposeFinalTools(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionFinalTools = api;
  if (root?.document) {
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", () => api.install(root), { once: true });
    else api.install(root);
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const ANNOTATION_KEY = "pokemon-go-collection:annotations:v2";
  const ANNOTATION_VERSION = 2;
  const LABELS = Object.freeze([
    "Keep", "Transfer review", "Trade", "Build later", "Elite TM candidate",
    "Remove Frustration", "Rescan", "Evolve during event",
  ]);
  const UNSUPPORTED_VALUE_FACTS = Object.freeze([
    "shiny", "costume", "background", "location background", "legacy move", "dynamax", "gigantamax",
  ]);
  const HIGH_PVP_PERCENTILE = 98;
  const STALE_SCAN_DAYS = 30;

  const normalize = (value) => String(value ?? "").trim().toLocaleLowerCase();
  const slug = (value) => normalize(value).replace(/[’']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "normal";
  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  const recordId = (record) => String(record?.identity?.record_id || record?.record_id || "");

  function annotationCompatibility(record) {
    return {
      pokemon_number: Number(record?.pokemon_number || 0),
      name: String(record?.name || ""),
      form: String(record?.form || ""),
      gender: String(record?.gender || ""),
      original_scan: String(record?.dates?.original_scan || ""),
      catch_date: String(record?.dates?.catch || ""),
    };
  }

  function blankAnnotationPayload() {
    return { version: ANNOTATION_VERSION, records: {}, unresolved: [] };
  }

  function sanitizeAnnotation(raw) {
    const labels = [...new Set((Array.isArray(raw?.labels) ? raw.labels : []).map(String).filter((label) => LABELS.includes(label)))];
    return {
      labels,
      note: String(raw?.note || "").slice(0, 1000),
      compatibility: raw?.compatibility && typeof raw.compatibility === "object" ? { ...raw.compatibility } : null,
      updated_at: String(raw?.updated_at || ""),
    };
  }

  function compatibilityMatches(record, compatibility) {
    if (!compatibility || typeof compatibility !== "object") return false;
    const current = annotationCompatibility(record);
    const keys = ["pokemon_number", "name", "form", "gender", "original_scan", "catch_date"];
    const supplied = keys.filter((key) => compatibility[key] !== null && compatibility[key] !== undefined && String(compatibility[key]) !== "");
    if (!supplied.length) return false;
    return supplied.every((key) => normalize(current[key]) === normalize(compatibility[key]));
  }

  function migrateAnnotations(raw, records = []) {
    const currentById = new Map(records.map((record) => [recordId(record), record]).filter(([id]) => id));
    const result = blankAnnotationPayload();
    if (!raw || typeof raw !== "object") return result;

    const sourceEntries = [];
    if (Number(raw.version) === ANNOTATION_VERSION && raw.records && typeof raw.records === "object") {
      for (const [id, value] of Object.entries(raw.records)) sourceEntries.push({ id, value });
    } else if (Number(raw.version) === 1 && Array.isArray(raw.annotations)) {
      for (const value of raw.annotations) sourceEntries.push({ id: String(value?.record_id || ""), value });
    } else if (!raw.version && raw.records && typeof raw.records === "object") {
      for (const [id, value] of Object.entries(raw.records)) sourceEntries.push({ id, value });
    } else {
      return result;
    }

    for (const entry of sourceEntries) {
      const annotation = sanitizeAnnotation(entry.value);
      const directId = String(entry.id || entry.value?.record_id || "");
      if (directId && currentById.has(directId)) {
        annotation.compatibility ||= annotationCompatibility(currentById.get(directId));
        result.records[directId] = annotation;
        continue;
      }
      const compatibility = annotation.compatibility || entry.value?.compatibility || null;
      const matches = records.filter((record) => compatibilityMatches(record, compatibility));
      if (matches.length === 1) {
        const id = recordId(matches[0]);
        annotation.compatibility = annotationCompatibility(matches[0]);
        result.records[id] = annotation;
      } else {
        result.unresolved.push({
          previous_record_id: directId || null,
          compatibility,
          annotation,
          state: matches.length > 1 ? "ambiguous" : "orphaned",
          candidate_record_ids: matches.map(recordId),
        });
      }
    }
    return result;
  }

  function loadAnnotations(storage, records = []) {
    try {
      const text = storage?.getItem(ANNOTATION_KEY);
      return text ? migrateAnnotations(JSON.parse(text), records) : blankAnnotationPayload();
    } catch {
      return blankAnnotationPayload();
    }
  }

  function saveAnnotations(storage, payload) {
    try {
      const normalized = blankAnnotationPayload();
      for (const [id, value] of Object.entries(payload?.records || {})) if (id) normalized.records[id] = sanitizeAnnotation(value);
      normalized.unresolved = Array.isArray(payload?.unresolved) ? payload.unresolved : [];
      storage?.setItem(ANNOTATION_KEY, JSON.stringify(normalized));
      return true;
    } catch {
      return false;
    }
  }

  function setAnnotation(payload, record, labels, note, timestamp = new Date().toISOString()) {
    const id = recordId(record);
    if (!id) throw new Error("Canonical record ID is required for local annotations");
    const next = {
      version: ANNOTATION_VERSION,
      records: { ...(payload?.records || {}) },
      unresolved: [...(payload?.unresolved || [])],
    };
    const clean = sanitizeAnnotation({ labels, note, compatibility: annotationCompatibility(record), updated_at: timestamp });
    if (!clean.labels.length && !clean.note) delete next.records[id];
    else next.records[id] = clean;
    return next;
  }

  function annotationBackup(payload) {
    return JSON.stringify({
      product: "pokemon-go-collection-local-annotations",
      schema_version: ANNOTATION_VERSION,
      exported_at: new Date().toISOString(),
      annotations: payload,
    }, null, 2);
  }

  function annotationFromBackup(raw, records) {
    if (!raw || raw.product !== "pokemon-go-collection-local-annotations") throw new Error("This is not a collection annotation backup");
    return migrateAnnotations(raw.annotations, records);
  }

  function isIncomplete(record) {
    return [record?.ivs?.average_percent, record?.ivs?.attack, record?.ivs?.defense, record?.ivs?.stamina,
      record?.level?.minimum, record?.moves?.fast, record?.moves?.charged].some((value) => value === null || value === undefined || value === "");
  }

  function scanAgeDays(record, referenceTimestamp) {
    const scan = Date.parse(record?.dates?.scan || "");
    const reference = Date.parse(referenceTimestamp || "");
    if (!Number.isFinite(scan) || !Number.isFinite(reference)) return null;
    return Math.max(0, Math.floor((reference - scan) / 86400000));
  }

  function protectionReasons(record, referenceTimestamp) {
    const reasons = [];
    if (record?.ivs?.is_hundo) reasons.push("hundo");
    if (record?.ivs?.is_nundo) reasons.push("nundo");
    if (record?.status?.favorite) reasons.push("favorite");
    if (record?.status?.lucky) reasons.push("lucky");
    if (["shadow", "purified"].includes(normalize(record?.status?.shadow_purified))) reasons.push(normalize(record.status.shadow_purified));
    if (record?.moves?.charged_second) reasons.push("second_charged_move");
    if (slug(record?.form) !== "normal") reasons.push("unusual_form");
    if (["great", "ultra", "little"].some((league) => Number(record?.pvp?.[league]?.rank_percent || 0) >= HIGH_PVP_PERCENTILE)) reasons.push("strong_pvp_candidate");
    if (isIncomplete(record)) reasons.push("incomplete_scan");
    const age = scanAgeDays(record, referenceTimestamp);
    if (age !== null && age > STALE_SCAN_DAYS) reasons.push("stale_scan");
    return [...new Set(reasons)];
  }

  function duplicateGroupKey(record) {
    return [
      Number(record?.pokemon_number || 0),
      slug(record?.form),
      normalize(record?.status?.shadow_purified || "normal") || "normal",
      record?.status?.lucky ? "lucky" : "not-lucky",
    ].join(":");
  }

  function pvpBest(record, league) {
    const value = Number(record?.pvp?.[league]?.rank_percent);
    return Number.isFinite(value) ? value : null;
  }

  function cheapestPvpCost(record) {
    const candidates = ["great", "ultra", "little"].map((league) => record?.pvp?.[league]).filter(Boolean)
      .filter((item) => item.dust_cost !== null && item.dust_cost !== undefined && item.candy_cost !== null && item.candy_cost !== undefined);
    if (!candidates.length) return null;
    return candidates.map((item) => ({ dust: Number(item.dust_cost), candy: Number(item.candy_cost) }))
      .sort((a, b) => a.dust - b.dust || a.candy - b.candy)[0];
  }

  function duplicateReview(records, referenceTimestamp) {
    const groups = new Map();
    for (const record of records || []) {
      if (!recordId(record)) continue;
      const key = duplicateGroupKey(record);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(record);
    }
    const output = [];
    for (const [key, members] of groups) {
      if (members.length < 2) continue;
      const reviewed = members.map((record) => ({
        record_id: recordId(record), pokemon_number: record.pokemon_number, name: record.name, form: record.form,
        cp: record.cp, level: record.level, ivs: record.ivs, status: record.status, moves: record.moves,
        pvp: { great: pvpBest(record, "great"), ultra: pvpBest(record, "ultra"), little: pvpBest(record, "little") },
        cheapest_pvp_cost: cheapestPvpCost(record),
        protection_reasons: protectionReasons(record, referenceTimestamp),
        scan_age_days: scanAgeDays(record, referenceTimestamp),
        action: "review_only",
      }));
      const maxIv = Math.max(...reviewed.map((item) => Number(item.ivs?.average_percent ?? -1)));
      const maxCp = Math.max(...reviewed.map((item) => Number(item.cp ?? -1)));
      for (const item of reviewed) {
        item.highlights = [];
        if (Number(item.ivs?.average_percent ?? -1) === maxIv) item.highlights.push("highest_iv_in_group");
        if (Number(item.cp ?? -1) === maxCp) item.highlights.push("highest_cp_in_group");
        for (const league of ["great", "ultra", "little"]) {
          const best = Math.max(...reviewed.map((candidate) => Number(candidate.pvp[league] ?? -1)));
          if (best >= 0 && Number(item.pvp[league] ?? -1) === best) item.highlights.push(`best_${league}_pvp_in_group`);
        }
      }
      output.push({
        group_key: key,
        pokemon_number: members[0].pokemon_number,
        name: members[0].name,
        form: members[0].form,
        supported_status_boundary: { shadow_purified: members[0].status?.shadow_purified || "normal", lucky: Boolean(members[0].status?.lucky) },
        record_count: reviewed.length,
        records: reviewed,
        unsupported_value_warning: `Review cannot verify ${UNSUPPORTED_VALUE_FACTS.join(", ")} from the current normalized source contract.`,
        automatic_transfer_safe: false,
      });
    }
    return output.sort((a, b) => b.record_count - a.record_count || Number(a.pokemon_number) - Number(b.pokemon_number) || a.group_key.localeCompare(b.group_key));
  }

  function normalizeEventFact(fact, index = 0) {
    const title = String(fact?.title || fact?.name || `Event ${index + 1}`);
    return {
      event_id: String(fact?.event_id || fact?.id || slug(title)),
      title,
      starts_at: fact?.starts_at || fact?.start || null,
      ends_at: fact?.ends_at || fact?.end || null,
      timezone: fact?.timezone || null,
      featured_dex: Array.isArray(fact?.featured_dex) ? fact.featured_dex.map(Number).filter(Number.isFinite) : [],
      evolution_targets: Array.isArray(fact?.evolution_targets) ? fact.evolution_targets : [],
      raid_targets: Array.isArray(fact?.raid_targets) ? fact.raid_targets : [],
      pvp_targets: Array.isArray(fact?.pvp_targets) ? fact.pvp_targets : [],
      mega_types: Array.isArray(fact?.mega_types) ? fact.mega_types.map(normalize) : [],
      before: Array.isArray(fact?.before) ? fact.before.map(String) : [],
      during: Array.isArray(fact?.during) ? fact.during.map(String) : [],
      after: Array.isArray(fact?.after) ? fact.after.map(String) : [],
      exclusive_windows: Array.isArray(fact?.exclusive_windows) ? fact.exclusive_windows : [],
    };
  }

  function eventSearchString(records) {
    const names = [...new Set((records || []).map((record) => String(record?.name || "").trim()).filter(Boolean))];
    return {
      text: names.join(","),
      exactness: "species-name OR search only",
      warning: "This helper selects species names and cannot distinguish exact owned records, forms, IVs, moves, or local annotations. Review the exact record IDs shown by the planner.",
    };
  }

  function eventPlan(snapshot, records, knowledgeIndex, now = new Date()) {
    if (!snapshot || snapshot.data_category !== "events") return { status: "unavailable", reason: "No event snapshot is available through the #69 external-data layer." };
    if (snapshot?.freshness?.state !== "fresh") return { status: "unavailable", reason: `Event snapshot freshness is ${snapshot?.freshness?.state || "unavailable"}; stale event instructions are blocked.` };
    const facts = Array.isArray(snapshot.facts) ? snapshot.facts : [];
    if (!facts.length) return { status: "unavailable", reason: "The fresh event snapshot contains no event facts." };
    const current = now instanceof Date ? now : new Date(now);
    const active = facts.map(normalizeEventFact).filter((fact) => {
      const start = fact.starts_at ? new Date(fact.starts_at) : null;
      const end = fact.ends_at ? new Date(fact.ends_at) : null;
      return (!start || current >= start) && (!end || current <= end);
    });
    const upcoming = facts.map(normalizeEventFact).filter((fact) => fact.starts_at && current < new Date(fact.starts_at)).sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at));
    const selected = active[0] || upcoming[0];
    if (!selected) return { status: "unavailable", reason: "No active or upcoming event remains in the fresh snapshot." };

    const featured = new Set(selected.featured_dex.map(Number));
    const owned = (records || []).filter((record) => featured.has(Number(record.pokemon_number)));
    const byDex = new Map((records || []).map((record) => [Number(record.pokemon_number), true]));
    const missingFeatured = selected.featured_dex.filter((dex) => !byDex.has(Number(dex)));
    const before = [...selected.before];
    const during = [...selected.during];
    const after = [...selected.after];
    if (owned.length) before.push(`Review ${owned.length} exact owned featured records before spending or transferring.`);
    if (selected.evolution_targets.length) before.push(`Reserve candidates for ${selected.evolution_targets.length} sourced evolution target/window entries.`);
    if (selected.raid_targets.length) during.push(`Review ${selected.raid_targets.length} sourced raid targets against collection gaps.`);
    if (selected.pvp_targets.length) during.push(`Review sourced PvP targets against owned candidate feeds; current-meta strength is not inferred here.`);
    if (missingFeatured.length) during.push(`${missingFeatured.length} featured Pokédex targets are not represented in the current owned collection.`);
    if (selected.exclusive_windows.length) after.push("Check every sourced exclusive window before its stated end time; the planner does not extend event deadlines.");

    return {
      status: "available",
      event: selected,
      phase: active.length ? "active" : "upcoming",
      source: {
        provider: snapshot.provider,
        source_reference: snapshot.source_reference,
        classification: snapshot.classification,
        dataset_timestamp: snapshot.dataset_timestamp,
        freshness: snapshot.freshness,
      },
      owned_featured: owned.map((record) => ({ record_id: recordId(record), pokemon_number: record.pokemon_number, name: record.name, form: record.form, cp: record.cp })),
      missing_featured_dex: missingFeatured,
      search: eventSearchString(owned),
      sections: { before, during, after },
      limitations: [
        "Only fields explicitly present in the freshness-checked event snapshot are treated as event facts.",
        "Unsupported collection attributes such as shiny, costume, background, Dynamax/Gigantamax, and trade history remain unknown unless a future source contract adds them.",
        "Species-name Pokémon GO search helpers cannot uniquely select exact canonical record IDs.",
      ],
      knowledge_dataset_version: knowledgeIndex?.datasetVersion || null,
    };
  }

  async function fetchJson(root, path) {
    const response = await root.fetch(path);
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return response.json();
  }

  function download(root, filename, text) {
    const blob = new root.Blob([text], { type: "application/json" });
    const url = root.URL.createObjectURL(blob);
    const anchor = root.document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    root.URL.revokeObjectURL(url);
  }

  function annotationFilter(records, payload, label) {
    if (!label || label === "all") return records;
    return records.filter((record) => payload.records[recordId(record)]?.labels?.includes(label));
  }

  function renderAnnotations(root, records, payload, selectedLabel = "all") {
    const container = root.document.getElementById("annotation-results");
    if (!container) return;
    const filtered = annotationFilter(records, payload, selectedLabel);
    const annotated = filtered.filter((record) => payload.records[recordId(record)]);
    const cards = annotated.slice(0, 100).map((record) => {
      const id = recordId(record);
      const item = payload.records[id];
      return `<article class="annotation-card" data-record-id="${escapeHtml(id)}"><header><strong>#${record.pokemon_number} ${escapeHtml(record.name)}${record.form ? ` · ${escapeHtml(record.form)}` : ""}</strong><small>${escapeHtml(id)}</small></header><p>${escapeHtml(item.labels.join(" · ") || "No labels")}</p><p>${escapeHtml(item.note || "No note")}</p><button type="button" data-edit-annotation="${escapeHtml(id)}">Edit</button></article>`;
    }).join("");
    const unresolved = payload.unresolved.map((item) => `<li><strong>${escapeHtml(item.state)}</strong> · ${escapeHtml(item.previous_record_id || "legacy annotation")} · ${(item.candidate_record_ids || []).length} candidate matches</li>`).join("");
    container.innerHTML = `<p class="planner-note">${annotated.length.toLocaleString()} annotated owned records match this label. Local annotations remain separate from Poke Genie facts.</p>${cards || "<p>No matching local annotations.</p>"}${payload.unresolved.length ? `<details open><summary>Unresolved annotations (${payload.unresolved.length})</summary><ul>${unresolved}</ul></details>` : ""}`;
  }

  function renderDuplicateReview(root, groups, payload) {
    const container = root.document.getElementById("duplicate-review-results");
    if (!container) return;
    const html = groups.map((group) => `<details class="trade-group"><summary><strong>#${group.pokemon_number} ${escapeHtml(group.name)}${group.form ? ` · ${escapeHtml(group.form)}` : ""}</strong><span>${group.record_count} distinct canonical records</span></summary><p class="planner-warning">${escapeHtml(group.unsupported_value_warning)}</p><ul>${group.records.map((record) => {
      const annotation = payload.records[record.record_id];
      const protection = record.protection_reasons.length ? record.protection_reasons.join(", ") : "none from supported fields";
      const highlights = record.highlights.length ? record.highlights.join(", ") : "none";
      return `<li data-state="${record.protection_reasons.length ? "protected_review" : "review_only"}"><span><strong>${escapeHtml(record.name)}</strong> · CP ${record.cp ?? "?"} · IV ${record.ivs?.average_percent ?? "?"}%</span><span>${escapeHtml(protection)}</span><small>${escapeHtml(record.record_id)} · highlights: ${escapeHtml(highlights)}${annotation ? ` · local: ${escapeHtml(annotation.labels.join("/"))}` : ""}</small></li>`;
    }).join("")}</ul></details>`).join("");
    container.innerHTML = `<p class="planner-note">${groups.length.toLocaleString()} duplicate review groups. These are distinct canonical records after duplicate-scan reconciliation. No row is declared safe to transfer.</p>${html || "<p>No duplicate groups remain after canonical reconciliation and supported status boundaries.</p>"}`;
  }

  function renderEventPlan(root, result) {
    const container = root.document.getElementById("event-planner-results");
    if (!container) return;
    if (result.status !== "available") {
      container.innerHTML = `<p class="planner-warning"><strong>Unavailable:</strong> ${escapeHtml(result.reason)}</p><p class="planner-note">The planner will not reuse stale event instructions.</p>`;
      return;
    }
    const sections = ["before", "during", "after"].map((phase) => `<section><h3>${phase[0].toUpperCase() + phase.slice(1)}</h3><ul>${(result.sections[phase] || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No sourced action for this phase.</li>"}</ul></section>`).join("");
    const owned = result.owned_featured.map((item) => `<li>#${item.pokemon_number} ${escapeHtml(item.name)} · CP ${item.cp ?? "?"}<small>${escapeHtml(item.record_id)}</small></li>`).join("");
    container.innerHTML = `<div class="planner-result-meta"><strong>${escapeHtml(result.event.title)}</strong><span>${escapeHtml(result.phase)} · ${escapeHtml(result.event.starts_at || "start unknown")} → ${escapeHtml(result.event.ends_at || "end unknown")}</span></div><p><strong>Source:</strong> ${escapeHtml(result.source.classification)} · ${escapeHtml(result.source.provider)} · dataset ${escapeHtml(result.source.dataset_timestamp)} · freshness ${escapeHtml(result.source.freshness.state)}</p>${sections}<details><summary>Exact owned featured records (${result.owned_featured.length})</summary><ul class="team-list">${owned || "<li>None.</li>"}</ul></details><p><strong>Pokémon GO helper:</strong> <code>${escapeHtml(result.search.text || "none")}</code></p><p class="planner-warning">${escapeHtml(result.search.warning)}</p><details><summary>Limitations</summary><ul>${result.limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></details>`;
  }

  async function install(root) {
    const duplicateContainer = root.document.getElementById("duplicate-review-results");
    const annotationContainer = root.document.getElementById("annotation-results");
    const eventContainer = root.document.getElementById("event-planner-results");
    if (!duplicateContainer && !annotationContainer && !eventContainer) return;

    let records = [];
    let manifest = {};
    let external = {};
    let knowledge = {};
    try {
      const [pokemon, buildManifest, externalIndex, knowledgePayload] = await Promise.all([
        fetchJson(root, "data/pokemon.json"), fetchJson(root, "data/build-manifest.json"),
        fetchJson(root, "data/external/index.json"), fetchJson(root, "data/knowledge/pokemon-go.json"),
      ]);
      records = pokemon.records || [];
      manifest = buildManifest;
      external = externalIndex;
      knowledge = { datasetVersion: knowledgePayload.dataset_version || null };
    } catch (error) {
      const message = `<p class="planner-warning">Final planning tools could not load canonical resources: ${escapeHtml(error.message)}</p>`;
      if (duplicateContainer) duplicateContainer.innerHTML = message;
      if (annotationContainer) annotationContainer.innerHTML = message;
      if (eventContainer) eventContainer.innerHTML = message;
      return;
    }

    let annotations = loadAnnotations(root.localStorage, records);
    saveAnnotations(root.localStorage, annotations);
    const groups = duplicateReview(records, manifest.export_timestamp || manifest.generated_at_utc);
    renderDuplicateReview(root, groups, annotations);
    renderAnnotations(root, records, annotations, root.document.getElementById("annotation-filter")?.value || "all");

    const recordSelect = root.document.getElementById("annotation-record");
    if (recordSelect) {
      recordSelect.innerHTML = records.map((record) => `<option value="${escapeHtml(recordId(record))}">#${record.pokemon_number} ${escapeHtml(record.name)}${record.form ? ` · ${escapeHtml(record.form)}` : ""} · CP ${record.cp ?? "?"}</option>`).join("");
    }
    const labelBox = root.document.getElementById("annotation-labels");
    if (labelBox) labelBox.innerHTML = LABELS.map((label) => `<label><input type="checkbox" value="${escapeHtml(label)}"> ${escapeHtml(label)}</label>`).join("");
    const filter = root.document.getElementById("annotation-filter");
    if (filter) filter.innerHTML = `<option value="all">All annotations</option>${LABELS.map((label) => `<option value="${escapeHtml(label)}">${escapeHtml(label)}</option>`).join("")}`;

    function populateEditor(id) {
      const current = annotations.records[id] || { labels: [], note: "" };
      if (recordSelect) recordSelect.value = id;
      for (const checkbox of labelBox?.querySelectorAll("input[type=checkbox]") || []) checkbox.checked = current.labels.includes(checkbox.value);
      const note = root.document.getElementById("annotation-note");
      if (note) note.value = current.note || "";
    }
    recordSelect?.addEventListener("change", () => populateEditor(recordSelect.value));
    annotationContainer?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-edit-annotation]");
      if (button) populateEditor(button.dataset.editAnnotation);
    });
    filter?.addEventListener("change", () => renderAnnotations(root, records, annotations, filter.value));
    root.document.getElementById("save-annotation")?.addEventListener("click", () => {
      const id = recordSelect?.value;
      const record = records.find((item) => recordId(item) === id);
      if (!record) return;
      const labels = [...(labelBox?.querySelectorAll("input:checked") || [])].map((input) => input.value);
      const note = root.document.getElementById("annotation-note")?.value || "";
      annotations = setAnnotation(annotations, record, labels, note);
      saveAnnotations(root.localStorage, annotations);
      renderAnnotations(root, records, annotations, filter?.value || "all");
      renderDuplicateReview(root, groups, annotations);
    });
    root.document.getElementById("export-annotations")?.addEventListener("click", () => download(root, "pokemon-go-collection-annotations.json", annotationBackup(annotations)));
    root.document.getElementById("clear-annotations")?.addEventListener("click", () => {
      annotations = blankAnnotationPayload();
      saveAnnotations(root.localStorage, annotations);
      renderAnnotations(root, records, annotations, filter?.value || "all");
      renderDuplicateReview(root, groups, annotations);
      populateEditor(recordSelect?.value || "");
    });
    root.document.getElementById("import-annotations")?.addEventListener("change", async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      try {
        annotations = annotationFromBackup(JSON.parse(await file.text()), records);
        saveAnnotations(root.localStorage, annotations);
        renderAnnotations(root, records, annotations, filter?.value || "all");
        renderDuplicateReview(root, groups, annotations);
      } catch (error) {
        annotationContainer.innerHTML = `<p class="planner-warning">Import failed: ${escapeHtml(error.message)}</p>`;
      }
    });
    if (recordSelect?.value) populateEditor(recordSelect.value);

    let eventSnapshot = null;
    if (Array.isArray(external.snapshots)) {
      eventSnapshot = external.snapshots.find((item) => item.data_category === "events" && item.freshness?.state === "fresh") ||
        external.snapshots.find((item) => item.data_category === "events") || null;
    }
    // Provider indexes may inline facts, or a future provider may publish a static snapshot path.
    if (eventSnapshot?.path) {
      try { eventSnapshot = { ...eventSnapshot, ...(await fetchJson(root, eventSnapshot.path)) }; } catch { /* explicit unavailable below */ }
    }
    renderEventPlan(root, eventPlan(eventSnapshot, records, knowledge, new Date()));
  }

  return {
    ANNOTATION_KEY, ANNOTATION_VERSION, LABELS, blankAnnotationPayload, sanitizeAnnotation,
    annotationCompatibility, compatibilityMatches, migrateAnnotations, loadAnnotations, saveAnnotations,
    setAnnotation, annotationBackup, annotationFromBackup, annotationFilter,
    protectionReasons, duplicateGroupKey, duplicateReview,
    normalizeEventFact, eventSearchString, eventPlan, install,
  };
});
