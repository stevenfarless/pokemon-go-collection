# Fork and bootstrap on GitHub Free

This project is designed so another Pokémon GO player can fork it, upload a Poke Genie export, and publish a working collection companion without a local development environment, paid backend, secret API key, database, or custom domain.

## Before you start

For the basic GitHub Free path, keep the fork **public**. GitHub Pages and GitHub Actions are available for public repositories on GitHub Free. The collection data you commit and publish is therefore public.

A valid source file must keep Poke Genie's exported archive name exactly:

```text
shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv
```

Place it under `exports/`. Do not manually edit generated files under a Pages artifact. The workflows regenerate the site from the newest valid filename timestamp.

## Setup checklist

### 1. Fork the repository

Use GitHub's **Fork** action and keep the default branch named `main`. No owner-specific repository path is embedded in the workflows; they use `${{ github.repository }}` and the current fork automatically.

### 2. Enable GitHub Actions in the fork

GitHub does not run workflows in a newly forked public repository until Actions is enabled for that fork.

Open the fork's **Actions** tab and enable workflows when prompted. Then open **Settings → Actions → General** and ensure the repository is allowed to run GitHub Actions. The project uses GitHub-maintained public actions pinned to reviewed commit SHAs.

No repository secret is required. The workflows use the automatic `GITHUB_TOKEN` with explicit least-privilege permissions.

### 3. Configure GitHub Pages

Open **Settings → Pages**. Under **Build and deployment → Source**, choose **GitHub Actions**.

Do not choose **Deploy from a branch**. The repository already contains a custom Pages workflow that builds, validates, stages, and deploys the site.

### 4. Upload a Poke Genie export

Open `exports/` in the fork and upload the CSV from Poke Genie without renaming it. Commit it to `main`.

The deployment workflow selects the newest valid export by the timestamp encoded in the filename. If two files encode the same newest timestamp, the build fails rather than guessing.

### 5. Run the bootstrap self-test

Open **Actions → Fork bootstrap self-test → Run workflow**.

The self-test checks:

- required repository and workflow files;
- the permanent zero-cost architecture policy;
- presence and exact naming of at least one Poke Genie export;
- deployment workflow permissions and Pages actions;
- GitHub Pages configuration through the repository's Pages API;
- a complete clean build;
- JSON Schema and cross-resource invariants;
- the staged deployment promotion guard.

A passing run writes the build ID and source export into the workflow summary.

### 6. Deploy

A commit to `main` that changes an export, build/site code, or deployment configuration triggers **Deploy collection to GitHub Pages** automatically. You can also run that workflow manually.

The workflow builds into an isolated `staging/` directory and does not call the Pages deploy action until validation and browser/accessibility tests pass. A failed build therefore does not replace the last healthy deployment.

After the deploy job succeeds, open **Settings → Pages** and use **Visit site** to open the fork's own Pages URL.

## Required repository settings

The intended configuration is:

- Repository visibility: **Public** for the no-cost GitHub Free path.
- Default branch: **main**.
- Actions: **Enabled**.
- Pages → Build and deployment → Source: **GitHub Actions**.
- No Actions secrets required.
- No custom domain required.
- No external deployment target required.

The workflow itself requests only the permissions needed by each task. Normal validation is read-only. Production deployment requests `pages: write` and `id-token: write`. Manual rollback additionally needs `actions: read` so it can retrieve a retained artifact from an earlier workflow run.

## Updating your collection

For normal updates, upload the new Poke Genie export to `exports/` and commit it. You do not need to delete older exports. They remain an audit archive; only the newest valid filename timestamp is published.

The deployment fails rather than silently falling back when the newest export is malformed or structurally unusable.

## Rollback

Successful deployment candidates are retained for 14 days as `pages-lkg-<build_id>` Actions artifacts. See `docs/deployment-safety.md` for the exact rollback procedure and retention behavior.

## Troubleshooting

### Workflows do not appear or do not run

Open **Actions** in the fork and enable workflows. Then confirm **Settings → Actions → General** allows GitHub Actions. Public forks do not run inherited workflows until Actions is enabled for the fork.

### Bootstrap self-test says Pages is not enabled

Open **Settings → Pages** and select **GitHub Actions** under **Build and deployment → Source**. Rerun the self-test.

### Bootstrap self-test reports an invalid CSV filename

Download/export the CSV again from Poke Genie and upload it to `exports/` without renaming it. The required form is `shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv`.

### No export is found

Confirm the file is inside `exports/`, ends in `.csv`, and retains the exact Poke Genie timestamped filename.

### Deployment builds but validation fails

Read the first failing validation message in Actions. The project intentionally blocks publication when the generated JSON contracts, build identities, resource counts, references, or staged assets are inconsistent.

### Pages still shows an older build

Confirm the latest **Deploy collection to GitHub Pages** workflow completed its `deploy` job successfully. A failed candidate intentionally leaves the previous known-good Pages site active.

### Rollback artifact cannot be found

Confirm both the source workflow run ID and build ID. Retained artifacts expire after 14 days and are also removed if their originating workflow run is deleted.

## Self-test from a local checkout

A local environment is optional, not required. If you do have one, the same repository-level readiness check is:

```bash
python scripts/bootstrap_self_test.py
```

The production build and validation remain:

```bash
python scripts/build_dashboard.py
python scripts/validate_generated.py
python scripts/deployment_guard.py --output dist
```
