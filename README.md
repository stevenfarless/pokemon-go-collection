# Pokémon GO Collection

A static, searchable GitHub Pages dashboard generated from the newest archived Poke Genie CSV export.

## Updating the collection

1. Export the collection from Poke Genie.
2. Upload the new CSV directly to `exports/` without renaming it.
3. Confirm that its name follows `shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv`.
4. Commit the file to `main`, or open and merge a pull request.

Older exports remain in `exports/`. The site parses the timestamp inside every matching filename and publishes only the newest one. Git commit dates, upload order, and filesystem modification times do not influence selection.

Matching CSV files outside `exports/` are ignored and do not trigger deployment. If the newest timestamped file inside `exports/` is empty, malformed, or missing a required core column, the workflow fails and the previously deployed site remains available. It does not silently publish an older export.

## Published resources

- `/`: searchable human-readable dashboard
- `/data/pokemon.json`: every normalized record and its build manifest
- `/data/latest-export.csv`: unmodified newest export
- `/data/collection-summary.json`: aggregate statistics
- `/data/schema.json`: valid JSON Schema for `pokemon.json`
- `/data/collection-summary.schema.json`: valid JSON Schema for the summary
- `/data/build-manifest.json`: freshness, source hash, schema versions, warnings, and asset names
- `/data/build-manifest.schema.json`: valid JSON Schema for the manifest
- `/data/source-columns.json`: required, optional, missing, and unknown CSV-column metadata
- `/summary.md`: compact Markdown summary
- `/llms.txt`: guidance for language models and automated readers

## Poke Genie export compatibility

The CSV compatibility contract is versioned as `poke-genie-csv-v1`. Only these columns are required to publish a usable record:

- `Name`
- `Pokemon Number`
- `CP`

All other known Poke Genie columns are optional groups covering identity, appraisal, moves, dates, size, status, and Great, Ultra, and Little League calculations. Missing optional columns become `null`, `false`, or `normal` in the normalized record, depending on the field. The build manifest and `source-columns.json` disclose every missing optional column.

Unknown future columns do not fail the build. They are listed in the manifest so a later schema version can adopt them deliberately. Reordered columns are accepted. Missing core columns still fail with a direct error.

The normalized JSON contract is independently versioned as `1.0.0`. CI validates the payload, summary, and manifest against the same JSON Schemas published by the site.

## Search-link safety

The dashboard stores filters, sorting, page size, and pagination in the URL so searches can be bookmarked or shared. URL state is allow-listed and normalized before the dashboard initializes. Invalid numbers, dates, select values, sort rules, page numbers, and unknown parameters are discarded rather than producing broken pagination or empty control states. Valid existing and legacy sort links remain supported.

## Scan completeness policy

The **Complete scan** and **Needs rescan** filters use a documented core Poke Genie scan policy. A complete record contains:

- overall IV percentage
- Attack, Defense, and HP IVs
- minimum and maximum level
- fast move
- first charged move

A second charged move, dates, dimensions, and PvP ranking are not required for general scan completeness. **Missing selected-league PvP data** remains a separate filter because some Pokémon or evolutions may not have a ranking for every league. When a scan-quality filter is active, the dashboard shows the fields used by that classification.

## Accessibility

Sortable table headers keep their visible column name as the accessible name. Sort direction is exposed on the header through `aria-sort`, while the shared table caption explains normal click and Shift-click behavior. The visible priority number and arrow remain decorative so voice-control commands can use the exact visible column name.

## Layout and loading

The collection region reserves a responsive minimum height before JSON data finishes loading. This keeps the footer from jumping through the mobile viewport while preserving normal growth for populated tables, zero-result searches, and data-error states.

The complete first-render stylesheet is inlined in generated HTML, so the external stylesheet is no longer render-blocking and the page does not flash unstyled content. A content-hashed CSS copy is also emitted as a nonblocking preload and no-JavaScript fallback.

## Cache and asset policy

GitHub Pages controls the site’s HTTP caching headers; this repository cannot set custom `Cache-Control` values through the Pages artifact. Lighthouse observed short cache lifetimes for the previous stable JavaScript and CSS filenames.

Every build now creates content-hashed CSS and JavaScript filenames. The exact paths are recorded in `build-manifest.json` and injected into the generated HTML. Collection-data requests include the same 12-character build identifier, preventing a newly loaded application from combining with stale JSON from another build. Deployments are atomic Pages artifacts, and no service worker is used, avoiding a second independent cache lifecycle.

## GitHub Pages configuration

In repository settings, choose **Pages → Build and deployment → Source → GitHub Actions**. The deployment workflow uses the `github-pages` environment and least-privilege permissions.

The site address is:

`https://stevenfarless.github.io/pokemon-go-collection/`

## Local validation

Python 3.12 or newer is recommended.

```bash
python -m pip install --disable-pip-version-check -r requirements-dev.txt
python -m unittest discover -s tests -v
node --check site/app.js
node --check site/hardening.js
node --check site/accessibility.js
node tests/test_multisort.js
node tests/test_hardening.js
node tests/test_accessible_sort.js
python scripts/build_collection.py
python scripts/validate_generated.py
python -m http.server --directory dist 8000
```

Then open `http://localhost:8000`.

`build_collection.py` constrains archive discovery to `exports/`, applies the versioned source-column compatibility contract, invokes the existing normalizer, publishes JSON Schemas, versions generated assets, and injects the URL, scan-quality, layout, and accessibility hardening layers.

## Filename selection rules

The accepted filename expression is exact:

```text
shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv
```

Example:

```text
shared-text-2026-08-05 23_24_00.336.csv
```

CSV files with other names are ignored. If two files under `exports/` encode the same newest timestamp, the build fails so the published source cannot be ambiguous.

## GitHub Actions dependency policy

Workflow actions are pinned to reviewed full commit SHAs. The corresponding release tag remains in a trailing comment for readability. Dependabot checks GitHub Actions weekly and groups compatible updates into a pull request.

When reviewing an action update:

1. Confirm the proposed SHA belongs to the stated official action and release tag.
2. Review the upstream release notes and changed permissions or runtime requirements.
3. Confirm workflow permissions remain least-privilege.
4. Require validation and a successful Pages build before merging.

## Privacy

The repository and GitHub Pages site are public. Uploaded exports reveal the Pokémon inventory, IVs, CP, levels, moves, scan and catch dates, and collection statuses contained in Poke Genie. Do not add account credentials, private notes, location data, or unrelated personal files.

## Data interpretation

Poke Genie PvP percentages rank IV combinations for an eligible Pokémon or evolution under a league cap. They do not measure the current PvP meta, team fit, moveset availability, or investment value.
