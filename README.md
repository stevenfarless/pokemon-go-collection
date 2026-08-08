# Pokémon GO Collection

A static, searchable GitHub Pages companion generated from the newest archived Poke Genie CSV export.

## Fork this project

The project is designed to be reusable entirely on GitHub Free. A new player can fork the repository, enable GitHub Actions, set GitHub Pages to **Build and deployment → Source → GitHub Actions**, upload a Poke Genie export to `exports/`, and run the included **Fork bootstrap self-test** workflow.

No paid backend, database, secret API key, custom domain, or local development environment is required for the basic path. See `docs/fork-bootstrap.md` for the complete setup checklist and troubleshooting guide. See `docs/deployment-safety.md` for staged promotion, retained last-known-good artifacts, and manual rollback.

## Updating the collection

1. Export the collection from Poke Genie.
2. Upload the new CSV directly to `exports/` without renaming it.
3. Confirm that its name follows `shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv`.
4. Commit the file to `main`, or open and merge a pull request.

Older exports remain archived. The filename timestamp determines the one export used by the public site. Git commit dates, upload order, and filesystem modification times do not affect selection. Matching files outside `exports/` are ignored.

## Canonical production build

The complete production site has one supported build command:

```bash
python scripts/build_dashboard.py
```

`site/index.html` and `site/insights.html` are the canonical HTML templates. Production behavior comes from `site/app.js`, `site/hardening.js`, `site/accessibility.js`, `site/dashboard.js`, `site/companion.js`, and `site/insights.js`. Styles come from `site/styles.css`, `site/stability.css`, `site/dashboard.css`, and `site/companion.css`.

The build modules remain separated by responsibility, but they are not separate production entry points:

- `build_collection.py` normalizes the selected export and publishes the base contracts.
- `build_release.py` applies semantic diagnostics, versioned assets, and performance hardening.
- `finalize_dashboard.py` publishes the canonical dashboard assets, Data Health, Insights, and PWA resources.
- `build_dashboard.py` is the single production orchestrator used locally and in workflows.

The generated manifest records this command and every canonical source file. No regex-generated trainer header, summary controls, filter controls, or usability markup remains outside the canonical templates.

## Published resources

- `/`: searchable collection dashboard
- `/insights.html`: collection-wide summaries with dashboard drill-down links
- `/data/pokemon.json`: every normalized record and the build manifest
- `/data/latest-export.csv`: unmodified newest export
- `/data/collection-summary.json`: aggregate statistics
- `/data/data-health.json`: freshness, completeness, parser, and warning metrics
- `/data/insights.json`: calculated duplicate, CP, status, PvP, and scan summaries
- `/data/schema.json`: JSON Schema for `pokemon.json`
- `/data/collection-summary.schema.json`: JSON Schema for the summary
- `/data/data-health.schema.json`: JSON Schema for Data Health
- `/data/insights.schema.json`: JSON Schema for Insights
- `/data/build-manifest.json`: source identity, freshness, schema versions, warnings, assets, and canonical pipeline
- `/data/build-manifest.schema.json`: JSON Schema for the manifest
- `/data/source-columns.json`: required, optional, missing, and unknown CSV columns
- `/summary.md`: compact Markdown summary
- `/llms.txt`: guidance for language models and automated readers

## Search

Ordinary search remains the default. Words, quoted phrases, and minus exclusions can be combined:

```text
pikachu "wild charge" -shadow
```

Optional field-qualified terms narrow specific exported fields:

```text
name:pikachu
form:alolan
move:"shadow ball"
cp:1500
cp:1500-2500
iv:96-100
level:40+
status:shadow
pvp:great
rank:1-100
-rank:unranked
```

Supported fields are `name`, `form`, `move`, `cp`, `iv`, `level`, `status`, `pvp`, and `rank`. Numeric fields accept exact values, inclusive ranges, and a trailing plus sign. Supported status values include `normal`, `shadow`, `purified`, `lucky`, `favorite`, `hundo`, `nundo`, and `pvp-marked`.

Field syntax is optional. Unknown fields and malformed known-field terms are treated as ordinary text instead of being interpreted unpredictably. The Help popover beside the search box contains the compact grammar and examples.

Free-text search waits 100 milliseconds after the final keystroke. Selects, buttons, chips, sorting, and pagination remain immediate. Searchable record text is cached for reuse, and the URL is rewritten only after typing pauses.

## Desktop columns

The desktop table initially shows Pokémon, CP, IVs, level, status, and selected-league PvP. Moves and dates are available from the compact **Columns** menu.

Column preferences are stored only in the current browser through `localStorage`. They survive reloads and new CSV exports because they are not tied to record IDs. Pokémon identity remains permanently visible. **Recommended defaults** restores the standard six-column view.

Hidden columns remain available for filtering and sorting. When the active order uses a hidden column, the nondefault sort chip remains visible and the Columns menu identifies the hidden sort dependency. **Reset view** also clears the saved column preference.

## Data Health

The Data menu contains a compact Data Health panel. It discloses:

- exact source filename and filename timestamp
- build time and parser/schema versions
- build warnings, errors, and unknown source columns
- incomplete core scans
- missing IV, level, and move fields
- missing selected-league Poke Genie ranking data
- scans at least 180 days old
- catches from the last 30 days

Each actionable count links to the corresponding dashboard search. Core scan completeness requires overall IV percentage, Attack/Defense/HP IVs, minimum and maximum level, fast move, and the first charged move. Missing league ranking data is reported separately because it does not invalidate the inventory record.

The source timestamp has no asserted timezone because it comes from the Poke Genie filename. The build timestamp is UTC.

## Collection Insights

`insights.html` is a separate static page so the primary dashboard remains search-first. It contains:

- collection totals and supported statuses
- duplicate-count distribution by Pokédex number, species, and form
- largest duplicate groups
- single-copy groups
- highest CP by species and form
- Great, Ultra, and Little League Poke Genie IV-ranking summaries
- Data Health summaries

Rows and cards link back to filtered or sorted dashboard views where the existing query model can express the group. Insights do not label Pokémon safe to transfer and do not infer missing in-game attributes.

## Clear filters and Reset view

**Clear filters** removes search text and filter criteria, returns to page 1, and preserves sorting, rows per page, and column preferences.

**Reset view**, in the Data menu, restores filters, sorting, pagination, preset selection, 50 rows per page, and recommended columns.

Shared URLs and presets restore state without opening the Filters or Sort drawer. Drawers open only through an explicit pointer or keyboard action.

## Poke Genie export compatibility

The CSV compatibility contract is versioned as `poke-genie-csv-v1`. Only `Name`, `Pokemon Number`, and `CP` are required to publish a usable record. Other known columns are optional groups covering identity, appraisal, moves, dates, size, status, and league calculations.

Missing optional columns normalize to `null`, `false`, or `normal` according to the field contract. Unknown future columns do not fail the build; they are disclosed in the manifest. Missing core columns still fail directly. The normalized JSON contract is independently versioned and validated against the same schemas published by the site.

## Accessibility

Sortable table headers keep their visible column name as the accessible name. Sort direction is exposed through `aria-sort`, and the table caption explains click and Shift-click behavior.

Filter chips have explicit removal names and 44-pixel touch targets. Filter changes use a concise live region. Nondefault sorting is exposed in a compact button that opens the Sort drawer. Drawers trap focus, close with Escape, and restore focus. Insights use headings, text, links, tables, and decorative bars that do not carry information unavailable in text.

## Asset, cache, and offline policy

Generated CSS and JavaScript use content-hashed filenames recorded in the build manifest. Collection-data requests use the build identifier to avoid mixing application code and stale JSON. GitHub Pages controls HTTP cache headers.

The installable PWA uses a build-versioned service worker. Static shell resources are precached, while collection data uses the project's versioned network-first strategy. The UI exposes offline state so a cached collection is not mistaken for a freshly fetched build.

## Local validation

Use Python 3.12 and Node.js 24. `package-lock.json` is authoritative.

```bash
python -m pip install --disable-pip-version-check -r requirements-dev.txt
npm ci --no-audit --no-fund
npx playwright install --with-deps chromium
python scripts/bootstrap_self_test.py
python -m unittest discover -s tests -v
node --check site/app.js
node --check site/hardening.js
node --check site/accessibility.js
node --check site/dashboard.js
node --check site/companion.js
node --check site/insights.js
node --check site/sw.js
node tests/test_multisort.js
node tests/test_hardening.js
node tests/test_accessible_sort.js
node tests/test_summary_presets.js
node tests/test_usability.js
node tests/test_dashboard.js
node tests/test_companion.js
python scripts/build_dashboard.py
python scripts/validate_generated.py
python scripts/deployment_guard.py --output dist
npm run test:browser
python -m http.server --directory dist 8000
```

Open `http://localhost:8000` for the dashboard and `http://localhost:8000/insights.html` for Insights.

## Filename selection rules

The accepted expression is exact:

```text
shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv
```

Example:

```text
shared-text-2026-08-05 23_24_00.336.csv
```

If two files under `exports/` encode the same newest timestamp, the build fails rather than selecting ambiguously. If the newest export is empty, malformed, or missing a core column, deployment fails and the previous site remains available.

## Dependencies and deployment

Workflow actions are pinned to reviewed full commit SHAs. Dependabot checks GitHub Actions and npm development dependencies weekly. Validation and deployment use `npm ci` from the committed lockfile.

GitHub Pages must use **Build and deployment → Source → GitHub Actions**. Production builds are created in an isolated staging directory, validated before promotion, and uploaded as one complete Pages artifact. Successful candidates are retained for 14 days as last-known-good rollback artifacts. The deployment and rollback workflows use the `github-pages` environment and least-privilege permissions.

Site address for this repository:

`https://stevenfarless.github.io/pokemon-go-collection/`

Forks receive their own Pages URL from GitHub; no owner-specific deployment URL is required by the workflows.

## Privacy and interpretation

The repository and site are public. Exports reveal the Pokémon inventory, IVs, CP, levels, moves, dates, and statuses included by Poke Genie. Do not add credentials, private notes, location data, or unrelated personal files.

Poke Genie PvP percentages rank IV combinations under a league cap. They do not measure current meta strength, team fit, move availability, or investment value. Missing values remain uncertainty rather than evidence of low value.
