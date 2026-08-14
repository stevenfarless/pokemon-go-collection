# Deployment safety and rollback

The production Pages workflow treats every build as an isolated promotion candidate and verifies the actual public deployment after promotion.

## Promotion sequence

1. `scripts/build_dashboard.py --output staging` creates a fresh isolated directory.
2. `scripts/validate_generated.py --output staging` enforces JSON Schemas and coordinated resource invariants.
3. `scripts/deployment_guard.py --output staging` verifies required Pages files, active build ID, record count, declared assets, and absence of undeclared stale hashed assets.
4. Browser/accessibility tests run directly against `staging`.
5. The validated staging directory is retained as `pages-lkg-<build_id>` and uploaded as the Pages artifact.
6. Before promotion, the deploy job queries the current Pages configuration and attempts to record the live build ID from `data/build-manifest.json`.
7. `actions/deploy-pages` promotes the validated artifact.
8. `scripts/production_smoke.py` verifies the deployed public machine/resource surface with bounded propagation retries.
9. `scripts/production_smoke_browser.js` launches Chromium against the public Pages URL and verifies browser behavior.
10. The workflow is successful only after both post-deployment smoke layers pass.

Pre-deployment parser, schema, invariant, staging-resource, or browser failures stop before promotion. Post-deployment smoke failures are reported prominently and identify the previously live build when it could be captured.

## Post-deployment machine smoke

The public-site verifier checks:

- root, `insights.html`, `tools.html`, `manifest.webmanifest`, and `sw.js`;
- `data/llm-bootstrap.json`;
- `data/build-manifest.json`;
- `data/pokemon-index.json`;
- `data/pokemon.json`;
- `api/v1/index.json` and `api/v1/manifest.json`;
- candidate and investment resources;
- `data/external/index.json` and every listed external snapshot;
- the first and last canonical Pokémon shards.

All coordinated resources must match the just-promoted build ID. Record-count invariants must also agree. A stale CDN response with an older build ID is never accepted as success.

Normal GitHub Pages propagation is handled with bounded retry/backoff. Exhausting that window fails production verification.

## Post-deployment browser smoke

Chromium loads the real public Collection page and must:

- initialize without fatal page/console errors;
- load the expected build ID;
- return results for a known exact species search;
- return zero rows for an impossible search;
- expose the Tools navigation route;
- load Tools canonical/local-data resources;
- expose Enrichment and Unified Backup controls;
- preserve Collection/Insights cross-navigation.

This catches route, CDN, service-worker, JavaScript, and production-path regressions that staging alone cannot prove.

## Last-known-good artifact

Each validated promotion candidate is uploaded as:

```text
pages-lkg-<build_id>
```

Retention is bounded to **14 days**. The artifact contains the complete validated static site.

When production smoke fails, the workflow uses the pre-deploy live build ID to query the repository Actions artifact API for the matching unexpired `pages-lkg-<previous_build_id>` artifact. When found, the failure summary reports the artifact ID and originating workflow run ID. This gives the operator an exact rollback target instead of merely saying the deployment failed.

If the prior live build or retained artifact cannot be resolved, the summary says so explicitly and directs the operator to the preceding successful Pages workflow. It never invents a rollback target.

## Manual rollback

Open **Actions → Roll back GitHub Pages → Run workflow** and provide:

- `run_id`: the successful **Deploy collection to GitHub Pages** workflow run that created the retained artifact;
- `build_id`: the 12-character build ID recorded in that run and artifact name.

The rollback workflow downloads exactly `pages-lkg-<build_id>`, re-runs the current deployment guard, verifies the embedded build ID, packages it as a Pages artifact, and deploys it.

Rollback does not rebuild an old export with current code. It redeploys the exact previously validated artifact and does not rewrite historical collection data.

## Mixed-build protection

The public resource registry requires one coordinated build identity. The promotion guard additionally checks the generated asset directory. Any undeclared/stale file under `assets/` fails promotion.

The workflow deletes `staging` before building. Pages receives one complete artifact, not incremental copies.

## Failure diagnosis

Common failure classes:

- export filename/core-column failure: correct the Poke Genie export under `exports/`;
- schema/invariant failure: inspect `validate_generated.py` and the named resource;
- stale/mixed asset failure: ensure an empty staging build and no copied old assets;
- production build-ID mismatch: wait only within the bounded Pages propagation window; do not accept an old build as current;
- production route/search/JavaScript failure: inspect the public smoke step and retain the previous build target before attempting a fix;
- rollback artifact not found: confirm the prior build ID, workflow run, 14-day retention window, and that the originating workflow run still exists;
- rollback build-ID mismatch: do not bypass the check; choose the artifact/run pair containing the intended build.

No external monitoring vendor, database, paid service, owner-provisioned secret, or runtime server is required.
