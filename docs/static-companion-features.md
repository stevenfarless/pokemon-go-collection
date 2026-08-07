# Static collection companion features

These features remain fully static. No collection data, saved view, comparison selection, or preference is sent to Firebase or another application server.

## Mobile cards and Pokémon details

Below 720 CSS pixels, the desktop table is replaced visually by compact result cards showing identity, CP, IV, level, status, and selected-league PvP information. Details open in a native modal dialog and expose the complete normalized record, including moves, dates, size, scan fields, and all three supported Poke Genie PvP league sections.

The current export does not provide a first-class immutable Pokémon instance identifier. The companion therefore derives a deterministic browser identifier from the record identity fields available in the export. This is useful for details and temporary comparisons, but a materially changed or ambiguous export can change that identifier. No note or destructive decision is attached to that derived identity.

## Saved views

Personal saved views contain only the current URL query and optional desktop column preferences. They are stored under a versioned `localStorage` key and survive reloads in the same browser profile.

Saved views can be renamed, duplicated, deleted, exported as human-readable JSON, and imported later. Duplicate import names are renamed by default. The import panel also provides an explicit option to replace duplicate names. Unsupported schema versions and malformed backups fail without changing existing saved views.

Browser storage can be cleared by the browser or operating system. Exported JSON is the backup mechanism.

## Comparison workspace

Two to six Pokémon can be compared side by side. Selection persists while changing filters or pages during the current browser session. The comparison presents CP, level, IVs, status, moves, and Great, Ultra, and Little League Poke Genie ranking data when available.

The comparison deliberately does not declare a universal winner. PvP rank, IV percentage, CP, Shadow status, moves, availability, and investment cost answer different questions. A lower value in one column never means another copy is automatically safe to transfer.

## Pokémon GO search-string generator

The GO Search dialog translates compatible dashboard filters into a Pokémon GO inventory search string. Each requested condition is labeled as Exact, Approximate, or Not representable. Approximate and omitted conditions are explained before copying.

The operator map was verified on 2026-08-07 against Niantic's official `Searching & Filtering your Pokémon Inventory` Help Center article. Because Pokémon GO search syntax can change, the verification date and source are displayed in the generator.

Dashboard filtering and Pokémon GO inventory search are not the same language. Poke Genie PvP rank, scan completeness, arbitrary IV percentages, local saved views, and several normalized form fields have no exact in-game equivalent. The generator never labels a resulting string safe for blind bulk transfer.

## Installable offline PWA

The generated site publishes `manifest.webmanifest`, a project-created SVG icon, and a versioned `sw.js` service worker. Hashed application assets and the current collection resources are precached as one build version.

HTML and collection JSON use a network-first strategy. When offline, the service worker can return the previously cached build. The UI displays an offline banner with the cached export timestamp. Static hashed assets use cache-first behavior. When a new service worker is waiting, the banner exposes a manual refresh/update action.

Old application caches are deleted only after the new service worker activates. A failed network response is never inserted into the cache as valid collection data. Local saved views remain in browser storage and are separate from service-worker caches. Unregistering the service worker returns the site to ordinary GitHub Pages behavior.
