# Pokémon GO Collection

A static, searchable GitHub Pages dashboard generated from the newest archived Poke Genie CSV export.

## Updating the collection

1. Export the collection from Poke Genie.
2. Upload the new CSV to `exports/` without renaming it.
3. Confirm that its name follows `shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv`.
4. Commit the file to `main`, or open and merge a pull request.

Older exports remain in the repository. The site parses the timestamp inside every matching filename and publishes only the newest one. Git commit dates, upload order, and filesystem modification times do not influence selection.

If the newest timestamped file is empty, malformed, or missing required Poke Genie columns, the workflow fails and the previously deployed site remains available. It does not silently publish an older export.

## Published resources

- `/`: searchable human-readable dashboard
- `/data/pokemon.json`: every normalized record
- `/data/latest-export.csv`: unmodified newest export
- `/data/collection-summary.json`: aggregate statistics
- `/data/schema.json`: field and source-column notes
- `/data/build-manifest.json`: source filename, export timestamp, SHA-256, and build time
- `/summary.md`: compact Markdown summary
- `/llms.txt`: guidance for language models and automated readers

## GitHub Pages configuration

In repository settings, choose **Pages → Build and deployment → Source → GitHub Actions**. The deployment workflow uses GitHub's official Pages actions and the `github-pages` environment.

The expected site address is:

`https://stevenfarless.github.io/pokemon-go-collection/`

## Local validation

Python 3.12 or newer is recommended. The builder uses only the Python standard library.

```bash
python -m unittest discover -s tests -v
python scripts/build_site.py
python -m http.server --directory dist 8000
```

Then open `http://localhost:8000`.

## Filename selection rules

The accepted filename expression is exact:

```text
shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv
```

Example:

```text
shared-text-2026-08-05 23_24_00.336.csv
```

CSV files with other names are ignored. If two matching files encode the same newest timestamp, the build fails so the published source cannot be ambiguous.

## Privacy

The repository and GitHub Pages site are public. Uploaded exports reveal the Pokémon inventory, IVs, CP, levels, moves, scan and catch dates, and collection statuses contained in Poke Genie. Do not add account credentials, private notes, location data, or unrelated personal files.

## Data interpretation

Poke Genie PvP percentages rank IV combinations for an eligible Pokémon or evolution under a league cap. They do not measure the current PvP meta, team fit, moveset availability, or investment value.
