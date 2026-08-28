"use strict";

(function exposeOpportunitySpecialLabs(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionOpportunitySpecialLabs = api;
  if (root?.document) {
    const start = () => api.install(root);
    if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  const OPPORTUNITY_KEY = "pokemon-go-collection:opportunity-finder:v1";
  const SPECIAL_KEY = "pokemon-go-collection:special-mechanics:v1";
  const BACKUP_PRODUCT = "pokemon-go-collection:opportunity-special-labs";
  const VERSION = 1;
  const OBJECTIVES = new Set(["missing-first", "roster-gaps", "owned-count"]);
  const TRI = new Set(["unknown", "yes", "no"]);

  const escapeHtml = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  function safeJson(raw, fallback) {
    try { return JSON.parse(raw); } catch { return fallback; }
  }

  function normalizeOpportunityState(raw) {
    const hidden = Array.isArray(raw?.hidden_opportunity_ids) ? raw.hidden_opportunity_ids.map(String).filter(Boolean) : [];
    const hiddenSpecies = Array.isArray(raw?.hidden_species_ids) ? raw.hidden_species_ids.map(String).filter(Boolean) : [];
    const objective = OBJECTIVES.has(String(raw?.objective)) ? String(raw.objective) : "missing-first";
    return {
      version: VERSION,
      objective,
      hidden_opportunity_ids: [...new Set(hidden)],
      hidden_species_ids: [...new Set(hiddenSpecies)],
      show_hidden: Boolean(raw?.show_hidden),
    };
  }

  function normalizeSpecialState(raw) {
    const records = {};
    if (raw?.records && typeof raw.records === "object" && !Array.isArray(raw.records)) {
      for (const [id, entry] of Object.entries(raw.records)) {
        records[String(id)] = {
          fused: TRI.has(String(entry?.fused)) ? String(entry.fused) : "unknown",
          note: String(entry?.note || "").slice(0, 300),
        };
      }
    }
    const resources = {};
    if (raw?.resources && typeof raw.resources === "object" && !Array.isArray(raw.resources)) {
      for (const [key, value] of Object.entries(raw.resources)) {
        if (value === null || value === undefined || value === "") resources[String(key)] = null;
        else {
          const parsed = Number(value);
          if (Number.isFinite(parsed) && parsed >= 0) resources[String(key)] = Math.floor(parsed);
        }
      }
    }
    return { version: VERSION, records, resources };
  }

  function loadState(storage, key, normalizer) {
    return normalizer(safeJson(storage?.getItem(key), {}));
  }

  function saveState(storage, key, value, normalizer) {
    const normalized = normalizer(value);
    storage?.setItem(key, JSON.stringify(normalized));
    return normalized;
  }

  function opportunityComparator(objective) {
    return (left, right) => {
      const groupOrder = { ending_soon: 0, right_now: 1, this_week: 2, later: 3 };
      const base = (groupOrder[left.group] ?? 9) - (groupOrder[right.group] ?? 9);
      if (base) return base;
      const lp = left.personalization || {}, rp = right.personalization || {};
      if (objective === "roster-gaps") {
        const diff = Number((rp.weak_roster_types || []).length) - Number((lp.weak_roster_types || []).length);
        if (diff) return diff;
      } else if (objective === "owned-count") {
        const diff = Number(left.owned_count || 0) - Number(right.owned_count || 0);
        if (diff) return diff;
      } else {
        const missingSpecies = Number(Boolean(rp.missing_species)) - Number(Boolean(lp.missing_species));
        if (missingSpecies) return missingSpecies;
        const missingForm = Number(Boolean(rp.missing_form)) - Number(Boolean(lp.missing_form));
        if (missingForm) return missingForm;
      }
      return Number(left.dex || 0) - Number(right.dex || 0)
        || String(left.channel || "").localeCompare(String(right.channel || ""))
        || String(left.id || "").localeCompare(String(right.id || ""));
    };
  }

  function sortOpportunities(items, objective = "missing-first") {
    const resolved = OBJECTIVES.has(String(objective)) ? String(objective) : "missing-first";
    return [...(Array.isArray(items) ? items : [])].sort(opportunityComparator(resolved));
  }

  function adventureEffectScenario(effect, increments) {
    const count = Math.max(0, Math.floor(Number(increments) || 0));
    const minutes = Number(effect?.duration_increment_minutes);
    const dust = Number(effect?.cost_per_increment?.stardust);
    const candy = Number(effect?.cost_per_increment?.candy);
    if (!count || !Number.isFinite(minutes) || minutes <= 0 || !Number.isFinite(dust) || !Number.isFinite(candy)) {
      return { status: "unavailable", increments: count, duration_minutes: null, stardust: null, candy: null };
    }
    return {
      status: "known",
      increments: count,
      duration_minutes: minutes * count,
      stardust: dust * count,
      candy: candy * count,
    };
  }

  function buildBackup(opportunity, special) {
    return {
      product: BACKUP_PRODUCT,
      backup_version: VERSION,
      exported_at: new Date().toISOString(),
      namespaces: {
        opportunity: normalizeOpportunityState(opportunity),
        special: normalizeSpecialState(special),
      },
    };
  }

  function validateBackup(raw) {
    if (!raw || raw.product !== BACKUP_PRODUCT || Number(raw.backup_version) !== VERSION || !raw.namespaces) {
      throw new Error("Unsupported Opportunity/Special Labs backup.");
    }
    return {
      opportunity: normalizeOpportunityState(raw.namespaces.opportunity || {}),
      special: normalizeSpecialState(raw.namespaces.special || {}),
    };
  }

  async function fetchJson(root, path) {
    const response = await root.fetch(path);
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return response.json();
  }

  function downloadJson(root, filename, payload) {
    const blob = new root.Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
    const url = root.URL.createObjectURL(blob);
    const anchor = root.document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    root.URL.revokeObjectURL(url);
  }

  async function readJsonFile(file) {
    if (typeof file?.text === "function") return JSON.parse(await file.text());
    throw new Error("This browser cannot read the selected file.");
  }

  function restrictionsText(item) {
    if (item?.restrictions?.state !== "qualified") return "Restrictions: not specified by source";
    return `Restrictions: ${Object.entries(item.restrictions.details || {}).map(([key, value]) => `${key}=${JSON.stringify(value)}`).join(", ")}`;
  }

  function sourceText(item) {
    const source = item?.source || {};
    return `${source.authority || source.classification || "Source"} · ${source.provider || "unknown provider"} · current as of ${source.dataset_timestamp || "unknown"}`;
  }

  function windowText(item) {
    const window = item?.window || {};
    if (!window.start && !window.end) return "Window: source did not publish a machine-readable start/end";
    return `Window: ${window.start || "already started"} → ${window.end || "no end supplied"} (${window.timezone || "timezone unknown"})`;
  }

  function renderOpportunity(root, payload) {
    const mount = root.document.getElementById("opportunity-finder-root");
    if (!mount) return;
    let state = loadState(root.localStorage, OPPORTUNITY_KEY, normalizeOpportunityState);
    const groups = [
      ["ending_soon", "Ending soon"],
      ["right_now", "Right now"],
      ["this_week", "This week"],
      ["later", "Later"],
    ];

    const render = () => {
      const hidden = new Set(state.hidden_opportunity_ids);
      const hiddenSpecies = new Set(state.hidden_species_ids);
      const sorted = sortOpportunities(payload.opportunities || [], state.objective);
      const visible = sorted.filter((item) => state.show_hidden || (!hidden.has(String(item.id)) && !hiddenSpecies.has(String(item.species_id))));
      const sections = groups.map(([key, label]) => {
        const items = visible.filter((item) => item.group === key);
        if (!items.length) return `<section><h2>${escapeHtml(label)}</h2><p class="lab-note">No visible verified opportunities in this group.</p></section>`;
        return `<section><h2>${escapeHtml(label)}</h2><div class="opportunity-grid">${items.map((item) => {
          const reasons = (item.personalization?.reasons || []).join(", ") || "currently featured";
          const rate = item.encounter_rate?.state === "source-provided" ? JSON.stringify(item.encounter_rate.value) : "unknown";
          return `<article class="lab-card">
            <h3>${escapeHtml(item.display_name)} <small>#${escapeHtml(item.dex)}</small></h3>
            <p><strong>${escapeHtml(item.channel)}</strong> · ${escapeHtml(reasons)}</p>
            <p>${escapeHtml(windowText(item))}</p>
            <p>${escapeHtml(sourceText(item))}</p>
            <p>${escapeHtml(restrictionsText(item))}</p>
            <p>Encounter rate: <strong>${escapeHtml(rate)}</strong> · Join: ${escapeHtml(item.join_state)}</p>
            <p>Owned copies: ${Number(item.owned_count || 0)} · <a href="${escapeHtml(item.reference)}">Open species reference</a></p>
            <p class="lab-actions"><button type="button" data-hide-opportunity="${escapeHtml(item.id)}">Hide this path</button>
            <button type="button" data-hide-species="${escapeHtml(item.species_id)}">Hide this target</button></p>
          </article>`;
        }).join("")}</div></section>`;
      }).join("");

      const noPath = (payload.no_verified_current_path || []).filter((item) => state.show_hidden || !hiddenSpecies.has(String(item.species_id)));
      mount.innerHTML = `<section class="lab-controls">
        <label>Priority objective <select id="opportunity-objective">
          <option value="missing-first">Missing species/forms first</option>
          <option value="roster-gaps">Weak roster types first</option>
          <option value="owned-count">Fewest owned copies first</option>
        </select></label>
        <label><input id="opportunity-show-hidden" type="checkbox"> Show hidden</label>
        <button id="opportunity-reset-hidden" type="button">Reset hidden items</button>
        <button id="opportunity-export" type="button">Export local preferences</button>
        <label class="file-control">Import preferences <input id="opportunity-import" type="file" accept="application/json,.json"></label>
      </section>
      <p class="lab-note">Only build-verified fresh snapshots are actionable. Unknown encounter rates are never treated as zero or guaranteed, and source restrictions stay visible.</p>
      ${sections}
      <section><h2>No verified current path</h2>${noPath.length ? `<ul>${noPath.map((item) => `<li><a href="${escapeHtml(item.reference)}">${escapeHtml(item.display_name || `#${item.dex}`)}</a> · ${escapeHtml(item.reason)}</li>`).join("")}</ul>` : '<p class="lab-note">No visible missing targets are currently in this group.</p>'}</section>`;
      const objective = root.document.getElementById("opportunity-objective");
      if (objective) objective.value = state.objective;
      const showHidden = root.document.getElementById("opportunity-show-hidden");
      if (showHidden) showHidden.checked = state.show_hidden;
      mount.querySelectorAll("[data-hide-opportunity]").forEach((button) => button.addEventListener("click", () => {
        state.hidden_opportunity_ids.push(button.dataset.hideOpportunity);
        state = saveState(root.localStorage, OPPORTUNITY_KEY, state, normalizeOpportunityState);
        render();
      }));
      mount.querySelectorAll("[data-hide-species]").forEach((button) => button.addEventListener("click", () => {
        state.hidden_species_ids.push(button.dataset.hideSpecies);
        state = saveState(root.localStorage, OPPORTUNITY_KEY, state, normalizeOpportunityState);
        render();
      }));
      objective?.addEventListener("change", () => {
        state.objective = objective.value;
        state = saveState(root.localStorage, OPPORTUNITY_KEY, state, normalizeOpportunityState);
        render();
      });
      showHidden?.addEventListener("change", () => {
        state.show_hidden = showHidden.checked;
        state = saveState(root.localStorage, OPPORTUNITY_KEY, state, normalizeOpportunityState);
        render();
      });
      root.document.getElementById("opportunity-reset-hidden")?.addEventListener("click", () => {
        state.hidden_opportunity_ids = [];
        state.hidden_species_ids = [];
        state = saveState(root.localStorage, OPPORTUNITY_KEY, state, normalizeOpportunityState);
        render();
      });
      root.document.getElementById("opportunity-export")?.addEventListener("click", () => {
        const special = loadState(root.localStorage, SPECIAL_KEY, normalizeSpecialState);
        downloadJson(root, "pokemon-go-opportunity-special-labs.json", buildBackup(state, special));
      });
      root.document.getElementById("opportunity-import")?.addEventListener("change", async (event) => {
        try {
          const imported = validateBackup(await readJsonFile(event.target.files?.[0]));
          state = saveState(root.localStorage, OPPORTUNITY_KEY, imported.opportunity, normalizeOpportunityState);
          saveState(root.localStorage, SPECIAL_KEY, imported.special, normalizeSpecialState);
          render();
        } catch (error) {
          root.alert(`Import failed: ${error.message || error}`);
        }
      });
    };
    render();
  }

  function effectCard(effect) {
    const owned = effect.owned_candidates || [];
    const usable = owned.filter((item) => item.required_move_owned);
    return `<article class="lab-card">
      <h3>${escapeHtml(effect.display_name)}</h3>
      <p>${escapeHtml(effect.effect_summary)}</p>
      <p>Required: ${escapeHtml(effect.pokemon?.name)} with <strong>${escapeHtml(effect.required_move)}</strong>. TM learnable in reviewed contract: <strong>${effect.tm_learnable ? "yes" : "no"}</strong>.</p>
      <p>Per ${Number(effect.duration_increment_minutes || 0)} min: ${Number(effect.cost_per_increment?.stardust || 0).toLocaleString()} Stardust + ${Number(effect.cost_per_increment?.candy || 0)} Candy.</p>
      <p>Exact owned candidates: ${owned.length}; with required move: <strong>${usable.length}</strong>.</p>
      ${owned.length ? `<ul>${owned.map((item) => `<li>${escapeHtml(item.name)} · CP ${escapeHtml(item.cp ?? "?")} · ${item.required_move_owned ? "required move present" : "required move not observed"} · <code>${escapeHtml(item.record_id)}</code></li>`).join("")}</ul>` : '<p class="lab-note">No exact owned candidate is present in the canonical collection.</p>'}
      <label>Scenario increments <input type="number" min="1" max="240" value="1" data-effect-count="${escapeHtml(effect.id)}"></label>
      <button type="button" data-calc-effect="${escapeHtml(effect.id)}">Calculate activation scenario</button>
      <p data-effect-result="${escapeHtml(effect.id)}" class="lab-note"></p>
    </article>`;
  }

  function fusionCard(recipe) {
    const base = recipe.owned_prerequisites?.base || [];
    const partner = recipe.owned_prerequisites?.partner || [];
    const energy = recipe.energy || {};
    const candy = recipe.candy || [];
    const energyCost = energy.amount == null ? "amount not in reviewed generic source; verify in Pokémon GO" : String(energy.amount);
    const candyCost = candy.map((item) => `${item.name}: ${item.amount == null ? "verify current amount" : item.amount}`).join("; ");
    return `<article class="lab-card">
      <h3>${escapeHtml(recipe.display_name)}</h3>
      <p>Base: ${escapeHtml(recipe.base?.name)} (${base.length} owned) · Partner: ${escapeHtml(recipe.partner?.name)} (${partner.length} owned).</p>
      <p>Exact owned pair available: <strong>${recipe.owned_prerequisites?.exact_owned_pair_available ? "yes" : "no"}</strong>.</p>
      <p>Energy: ${escapeHtml(energy.kind)} · ${escapeHtml(energyCost)}. Candy: ${escapeHtml(candyCost)}.</p>
      <p>Separation has zero Candy/Fusion Energy cost in the reviewed official rule. Fused Pokémon cannot be traded or transferred while fused.</p>
      <p class="lab-note">${escapeHtml(recipe.resource_readiness?.rule)}</p>
      ${base.map((item) => `<label>${escapeHtml(item.name)} <code>${escapeHtml(item.record_id)}</code> fused state
        <select data-fused-record="${escapeHtml(item.record_id)}"><option value="unknown">Unknown</option><option value="yes">Yes</option><option value="no">No</option></select></label>`).join("")}
    </article>`;
  }

  function renderSpecial(root, payload) {
    const mount = root.document.getElementById("special-mechanics-root");
    if (!mount) return;
    let state = loadState(root.localStorage, SPECIAL_KEY, normalizeSpecialState);
    const fusion = (payload.mechanics || []).find((item) => item.kind === "fusion");
    const adventure = (payload.mechanics || []).find((item) => item.kind === "adventure-effect");
    mount.innerHTML = `<section class="lab-controls">
      <button id="special-export" type="button">Export local special state</button>
      <label class="file-control">Import local state <input id="special-import" type="file" accept="application/json,.json"></label>
      <button id="special-clear" type="button">Clear local special state</button>
    </section>
    <p class="lab-note">Registry ${escapeHtml(payload.registry?.dataset_version)} reviewed ${escapeHtml(payload.registry?.reviewed_at)}. Unknown special state and resource balances remain unknown, never inferred from species ownership.</p>
    <section><h2>Fusion</h2>${(fusion?.recipes || []).map((recipe) => fusionCard(recipe)).join("") || '<p class="lab-note">No reviewed Fusion recipes are available.</p>'}</section>
    <section><h2>Adventure Effects</h2>
      <p class="lab-note">Only one Adventure Effect can be active at a time in the reviewed rule. An Adventure Effect can coexist with Mega/Primal bonuses. The modeled effects below require the exact special move already observed on an owned record.</p>
      <div class="opportunity-grid">${(adventure?.effects || []).map(effectCard).join("") || '<p class="lab-note">No modeled Adventure Effects are available.</p>'}</div>
      ${(adventure?.unmodeled_official_examples || []).length ? `<p class="lab-note">Officially listed but not cost-modeled here: ${escapeHtml(adventure.unmodeled_official_examples.join(", "))}. The lab refuses to invent their costs.</p>` : ""}
    </section>
    <section><h2>Decision handoff</h2><p><a href="${escapeHtml(payload.handoffs?.resource_optimizer)}">Compare against Resource Optimizer</a> · <a href="${escapeHtml(payload.handoffs?.move_lab)}">Open Move Lab</a> · <a href="${escapeHtml(payload.handoffs?.decision_card)}">Open collection decision workspace</a></p></section>`;

    mount.querySelectorAll("[data-fused-record]").forEach((select) => {
      const id = String(select.dataset.fusedRecord || "");
      select.value = state.records[id]?.fused || "unknown";
      select.addEventListener("change", () => {
        state.records[id] = { ...(state.records[id] || {}), fused: select.value, note: state.records[id]?.note || "" };
        state = saveState(root.localStorage, SPECIAL_KEY, state, normalizeSpecialState);
      });
    });
    mount.querySelectorAll("[data-calc-effect]").forEach((button) => button.addEventListener("click", () => {
      const id = String(button.dataset.calcEffect || "");
      const effect = (adventure?.effects || []).find((item) => String(item.id) === id);
      const count = mount.querySelector(`[data-effect-count="${id}"]`)?.value;
      const result = adventureEffectScenario(effect, count);
      const target = mount.querySelector(`[data-effect-result="${id}"]`);
      if (!target) return;
      target.textContent = result.status === "known"
        ? `${result.duration_minutes} minutes costs ${result.stardust.toLocaleString()} Stardust and ${result.candy} Candy. Compare this opportunity cost before activating.`
        : "Scenario unavailable until a positive increment count and reviewed cost are present.";
    }));
    root.document.getElementById("special-export")?.addEventListener("click", () => {
      const opportunity = loadState(root.localStorage, OPPORTUNITY_KEY, normalizeOpportunityState);
      downloadJson(root, "pokemon-go-opportunity-special-labs.json", buildBackup(opportunity, state));
    });
    root.document.getElementById("special-import")?.addEventListener("change", async (event) => {
      try {
        const imported = validateBackup(await readJsonFile(event.target.files?.[0]));
        saveState(root.localStorage, OPPORTUNITY_KEY, imported.opportunity, normalizeOpportunityState);
        state = saveState(root.localStorage, SPECIAL_KEY, imported.special, normalizeSpecialState);
        renderSpecial(root, payload);
      } catch (error) {
        root.alert(`Import failed: ${error.message || error}`);
      }
    });
    root.document.getElementById("special-clear")?.addEventListener("click", () => {
      if (!root.confirm("Clear browser-local Special Mechanics state?")) return;
      root.localStorage.removeItem(SPECIAL_KEY);
      state = normalizeSpecialState({});
      renderSpecial(root, payload);
    });
  }

  async function install(root) {
    const opportunityMount = root.document?.getElementById("opportunity-finder-root");
    const specialMount = root.document?.getElementById("special-mechanics-root");
    if (!opportunityMount && !specialMount) return false;
    try {
      if (opportunityMount) renderOpportunity(root, await fetchJson(root, "data/opportunity-finder.json"));
      if (specialMount) renderSpecial(root, await fetchJson(root, "data/special-mechanics-lab.json"));
      return true;
    } catch (error) {
      const target = opportunityMount || specialMount;
      if (target) target.innerHTML = `<p role="alert">This lab could not load safely: ${escapeHtml(error.message || error)}</p>`;
      return false;
    }
  }

  return {
    OPPORTUNITY_KEY,
    SPECIAL_KEY,
    VERSION,
    normalizeOpportunityState,
    normalizeSpecialState,
    sortOpportunities,
    adventureEffectScenario,
    buildBackup,
    validateBackup,
    install,
  };
});
