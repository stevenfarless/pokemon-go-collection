# Pokémon GO Collection

A static, searchable GitHub Pages dashboard generated from the newest archived Poke Genie CSV export.

## Updating the collection

1. Export the collection from Poke Genie.
2. Upload the new CSV directly to `exports/` without renaming it.
3. Confirm that its name follows `shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv`.
4. Commit the file to `main`, or open and merge a pull request.

Older exports remain in `exports/`. The site parses the timestamp inside every matching filename and publishes only the newest one. Git commit dates, upload order, and filesystem modification times do not influence selection.

Matching CSV files outside `exports/` are ignored and do not trigger deployment. If the newest timestamped file inside `exports/` is empty, malformed, or missing required Poke Genie columns, the workflow fails and the previously deployed site remains available. It does not silently publish an older export.

## Published resources

- `/`: searchable human-readable dashboard
- `/data/pokemon.json`: every normalized record
- `/data/latest-export.csv`: unmodified newest export
- `/data/collection-summary.json`: aggregate statistics
- `/data/schema.json`: field and source-column notes
- `/data/build-manifest.json`: source filename, export timestamp, SHA-256, and build time
- `/summary.md`: compact Markdown summary
- `/llms.txt`: guidance for language models and automated readers

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

## Layout stability

The collection region reserves a responsive minimum height before JSON data finishes loading. This keeps the footer from jumping through the mobile viewport while preserving normal growth for populated tables, zero-result searches, and data-error states.

## GitHub Pages configuration

In repository settings, choose **Pages → Build and deployment → Source → GitHub Actions**. The deployment workflow uses the `github-pages` environment and least-privilege permissions.

The site address is:

`https://stevenfarless.github.io/pokemon-go-collection/`

## Local validation

Python 3.12 or newer is recommended. The builder uses only the Python standard library.

```bash
python -m unittest discover -s tests -v
node --check site/app.js
node --check site/hardening.js
node tests/test_multisort.js
node tests/test_hardening.js
python scripts/build_collection.py
python -m http.server --directory dist 8000
```

Then open `http://localhost:8000`.

`build_collection.py` constrains archive discovery to `exports/`, invokes the existing normalizer, injects the hardened URL/scan-quality layer, and includes the supplemental layout-stability stylesheet.

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
