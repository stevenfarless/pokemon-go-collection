# Deployment safety and rollback

The production Pages workflow treats every new build as an isolated promotion candidate. The currently deployed site is not modified unless the candidate completes the canonical build, contract validation, promotion guard, and browser/accessibility regression tests.

## Promotion sequence

1. `scripts/build_dashboard.py --output staging` creates a fresh isolated directory.
2. `scripts/validate_generated.py --output staging` enforces the versioned JSON Schemas and coordinated resource invariants.
3. `scripts/deployment_guard.py --output staging` verifies required Pages files, the active build ID, positive canonical record count, declared assets, and the absence of undeclared stale hashed assets.
4. Browser and accessibility tests run directly against `staging`.
5. Only after all checks pass is the complete staging directory uploaded as a GitHub Pages artifact.
6. `actions/deploy-pages` atomically promotes that artifact.

A parser error, malformed export, schema failure, invariant failure, missing resource, stale asset, or browser-test failure stops before the deploy job. The previously deployed GitHub Pages site therefore remains the last-known-good site.

## Last-known-good artifact

Each successful promotion candidate is also uploaded as an Actions artifact named:

```text
pages-lkg-<build_id>
```

The retained artifact is created only after the staging build has passed the promotion guard and browser/accessibility tests. It contains the complete static site, not a mixture of generated files from multiple runs.

Retention is intentionally bounded to **14 days**. GitHub Actions deletes the artifact after that period, limiting storage use on GitHub Free while leaving a practical rollback window. GitHub's normal workflow-run and artifact deletion rules still apply. Deleting the originating workflow run also removes its retained artifact.

## Manual rollback

Open **Actions → Roll back GitHub Pages → Run workflow** and provide:

- `run_id`: the successful **Deploy collection to GitHub Pages** workflow run that created the retained artifact;
- `build_id`: the 12-character build ID recorded in that run summary and in the deployed `data/build-manifest.json`.

The rollback workflow downloads exactly `pages-lkg-<build_id>` from that run, re-runs the current `deployment_guard.py` against it, requires the embedded build ID to equal the requested build ID, packages it as a new Pages artifact, and deploys it.

Rollback does not rebuild an old export with current code. It redeploys the exact previously validated static artifact, which avoids creating a new interpretation of historical source data during recovery.

## Mixed-build protection

The public resource registry already requires one coordinated build identity for declared data resources. The promotion guard adds a Pages-level check for the generated asset directory. Any undeclared or stale file under `assets/` fails promotion. This prevents a reused output directory from silently carrying old hashed JavaScript or CSS into a new deployment.

The workflow also starts by deleting `staging` before building. GitHub Pages receives one complete artifact after all checks, rather than incremental file copies.

## Failure diagnosis

Actions logs and the workflow summary identify the source export and build ID when a promotion candidate reaches the guard. Failures before that point retain the parser/schema error from the canonical validation commands.

Common failure classes:

- export filename or core-column failure: correct the Poke Genie export under `exports/`;
- schema/invariant failure: inspect the `validate_generated.py` message and generated resource named in the error;
- stale/mixed asset failure: ensure the build starts from an empty staging directory and no build step copies old generated assets;
- rollback artifact not found: confirm the source run ID, build ID, 14-day retention window, and that the originating workflow run still exists;
- rollback build-ID mismatch: do not bypass the check; select the run/artifact pair that actually contains the intended known-good build.

No external storage, paid service, secret API key, database, or server is required for promotion or rollback.
