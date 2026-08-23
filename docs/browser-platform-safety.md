# Browser platform safety and recovery

The static application keeps user-authored notes, enrichment, goals, saved views, planner budgets, and column preferences in browser storage. No recovery or diagnostic path uploads those values.

## Storage model

Seven durable namespaces remain in `localStorage` because their expected size is small or medium and they are simple browser-local documents. IndexedDB was evaluated for this batch and is reserved for future state that materially outgrows these documents. Introducing a second persistence engine now would add migration and partial-transaction failure modes without a current capacity need.

`site/storage-health.js` validates each namespace on health checks, records a checksum, and retains a last-known-good raw snapshot only after the current value parses and matches its supported schema. Corrupt or version-incompatible values do not overwrite the recovery snapshot. `localStorage.setItem` is atomic for an individual key, and the existing unified restore additionally rolls back all namespace writes when one write fails. The Storage Health probe exposes write/quota failures, unresolved record mappings, approximate StorageManager usage, persistence status, and backup recency where the browser exposes those APIs.

`navigator.storage.persisted()`, `persist()`, and `estimate()` are progressive enhancements. A granted persistence request reduces eviction risk; it is not represented as a guarantee that browser data can never be cleared.

## PWA update lifecycle

The service worker precaches a complete versioned shell before installation succeeds. Older version caches are retained across activation so an old content-hashed client can finish requests against its matching cache. The UI exposes a waiting update and requires an explicit apply action. Local edit areas mark themselves dirty, preventing update/reload actions until the user saves or finishes the edit. Reload is always explicit.

The diagnostic console reports current/cached manifest availability, active build ID, service-worker control/build ID, external freshness summary, storage health, browser capabilities, and recovery actions. Copied diagnostics contain namespace names, versions, byte estimates, and statuses only. Collection records and note/enrichment contents are excluded.
