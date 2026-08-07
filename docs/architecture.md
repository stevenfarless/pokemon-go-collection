# Zero-cost GitHub-only architecture

This repository has a permanent product constraint: the complete core collection companion must remain buildable, deployable, forkable, and usable without paying for infrastructure outside GitHub.

Closing issue #70 means the enforcement described here has been implemented. It does not retire this rule.

## Core platform

The supported core stack is:

- GitHub repository storage for source, archived Poke Genie exports, generated contracts, and documentation.
- GitHub Actions for validation and static generation within GitHub Free limits.
- GitHub Pages for the published site.
- Static HTML, CSS, JavaScript, JSON, Markdown, web app manifests, and service workers.
- Browser-local capabilities such as `localStorage`, IndexedDB, Web Workers, File APIs, and WASM when useful.

The core product must not require Firebase, Supabase, hosted databases, paid APIs, paid search/vector services, serverless functions, or another owner-specific backend. Optional integrations are permitted only when the site remains fully functional without them and a free static fallback is documented.

## Data and privacy boundary

Poke Genie exports are archived unchanged under `exports/`. The production build derives normalized static resources from the newest valid timestamped export. Browser-local views, notes, preferences, and similar personal state remain client-side unless a future issue explicitly adds an optional export/import mechanism.

No core workflow requires account credentials, external API keys, or repository secrets beyond GitHub's built-in Pages/OIDC permissions.

## Fork/bootstrap contract

A fresh public fork must be able to reproduce the project using a GitHub Free account:

1. Fork the repository.
2. Keep GitHub Actions enabled.
3. In repository Settings > Pages, use **GitHub Actions** as the Pages source.
4. Add a Poke Genie CSV under `exports/` using the supported `shared-text-YYYY-MM-DD HH_MM_SS.mmm.csv` filename pattern.
5. Run the validation workflow or open a pull request.
6. Merge/push to `main`. The Pages workflow builds `dist/`, validates it, uploads the Pages artifact, and deploys it.
7. Confirm `data/build-manifest.json` identifies the expected export, build ID, counts, and published resources.

No custom domain, external database, SaaS account, API key, or paid service is required.

## Enforcement

`scripts/check_architecture.py` runs in validation and deployment. It fails when the core runtime introduces known hosted-backend dependencies, owner-provisioned workflow secrets, or other prohibited required-service indicators.

The check is intentionally conservative rather than pretending static analysis can prove every architecture property. Code review must still verify that new features:

- have a bounded storage and Actions-cost strategy;
- keep generated history, caches, and artifacts from growing without limit;
- use repository-hosted snapshots for current data when legally and technically practical;
- degrade explicitly when optional external/current data is stale or unavailable;
- do not make a paid LLM or another external service necessary for core calculations;
- preserve fork-friendly relative paths and avoid owner-specific infrastructure.

## Architecture review for future issues

Before an issue is considered complete, any infrastructure choice must satisfy this policy. A feature that cannot fit the constraint must be redesigned as static/client-side, made optional with a complete free fallback, or rejected/superseded.

The authoritative product requirement remains issue #70 plus this document. A later change to the constraint requires an explicit repository-owner decision and corresponding documentation update.
