"use strict";

(function exposeAdvancedSearchCompatibility(root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.CollectionAdvancedSearchCompatibility = api;
  if (root?.document) api.prepare(root);
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  function isSimpleTypoCandidate(query) {
    const text = String(query || "").trim();
    return /^[a-z][a-z'’]{3,19}$/i.test(text);
  }

  function shouldUseAdvancedFallback(compiled) {
    if (!compiled) return false;
    if (compiled.extendedTerms?.length) return true;
    if (compiled.naturalReasons?.length) return true;
    if (compiled.invalid?.length) return false;
    return isSimpleTypoCandidate(compiled.plainQuery);
  }

  function prepare(root) {
    const advanced = root.CollectionAdvancedSearch;
    const engine = root.CollectionFilterEngine;
    const baseSearch = root.CollectionDashboard?.QualifiedSearch;
    if (!advanced || !engine || !baseSearch || advanced.__compatPrepared) return null;

    // dashboard.js has already installed its qualified-search and WeakMap text cache
    // before this deferred script runs. Capture that exact path so ordinary queries
    // retain their previous semantics and performance metrics.
    const cachedMatchesRecord = engine.matchesRecord;
    const originalInstall = advanced.install;

    advanced.install = function installWithCompatibility(targetRoot) {
      const installed = originalInstall(targetRoot);
      const advancedMatchesRecord = engine.matchesRecord;
      if (!installed || advancedMatchesRecord === cachedMatchesRecord) return installed;

      engine.matchesRecord = function matchesRecordExactFirst(record, filters = {}) {
        const query = String(filters.query || "").trim();
        if (!query) return cachedMatchesRecord(record, filters);

        // Preserve the pre-existing exact/qualified path first. This keeps malformed
        // qualified terms ordinary text, keeps URL behavior stable, and exercises the
        // existing search-text cache. Advanced matching is a bounded fallback only.
        if (cachedMatchesRecord(record, filters)) return true;

        const compiled = advanced.compileQuery(query, baseSearch, new Set());
        if (!shouldUseAdvancedFallback(compiled)) return false;
        return advancedMatchesRecord(record, filters);
      };
      Object.defineProperty(engine, "__advancedSearchCompatibilityInstalled", { value: true, configurable: true });
      return installed;
    };
    Object.defineProperty(advanced, "__compatPrepared", { value: true, configurable: true });
    return { cachedMatchesRecord, originalInstall };
  }

  return {
    isSimpleTypoCandidate,
    shouldUseAdvancedFallback,
    prepare,
  };
});
