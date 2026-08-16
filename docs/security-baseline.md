# GitHub-native security baseline

This project is designed to remain usable on GitHub Free with no required external security SaaS. Repository security is split between controls committed as code and GitHub repository settings that a fork owner must enable separately.

## Committed controls

### CodeQL

`.github/workflows/codeql.yml` runs pinned GitHub CodeQL actions for:

- JavaScript/TypeScript;
- Python;
- GitHub Actions workflows.

The workflow runs on pull requests to `main`, pushes to `main`, a bounded weekly schedule, and manual dispatch. It uses the `security-extended` query suite and least-privilege workflow permissions required for code scanning.

All CodeQL actions are pinned to a full commit SHA. Dependabot's `github-actions` ecosystem is responsible for proposing future reviewed pin updates.

### Dependency review

`.github/workflows/dependency-review.yml` runs GitHub's pinned dependency-review action on every pull request. It fails when a pull request introduces a dependency with a known **high** or **critical** vulnerability.

A failing Action check only becomes a hard merge requirement when repository branch protection/rulesets require that check. Fork owners should configure required checks according to their GitHub plan and repository policy.

### Dependabot version updates

`.github/dependabot.yml` covers:

- GitHub Actions;
- npm development dependencies;
- pip/Python dependencies in the repository root.

Checks run weekly on Monday using `America/Chicago`, with grouped dependency pull requests where appropriate and bounded open-PR limits.

Version-update PRs are maintenance proposals, not automatic permission to merge. Normal CI/security validation still applies.

### Immutable Actions pins

Repository workflows use full Git commit SHAs for third-party/GitHub Actions rather than mutable major-version refs. A human-readable version comment may accompany the SHA. Dependabot should update those pins through reviewed pull requests.

### Workflow permissions

Workflows should declare the smallest practical permissions. New workflows must not inherit broad write access merely for convenience. Write permissions such as `security-events: write` are allowed only where the specific GitHub feature requires them.

### Security policy

`SECURITY.md` defines supported versions, private-reporting expectations, scope priorities, and coordinated-disclosure behavior.

## GitHub repository settings checklist

The following controls are not fully represented by committed files. Repository owners and fork maintainers should verify them in **Settings → Advanced Security** or the corresponding current GitHub settings surface.

### Required for the intended baseline

- GitHub Actions enabled.
- Dependency graph enabled.
- Dependabot alerts enabled.
- Dependabot security updates enabled.
- Code scanning permitted for the repository so the committed CodeQL workflow can publish results.

### Strongly recommended

- Private vulnerability reporting enabled for this public repository.
- Secret scanning and push protection enabled where GitHub makes them available for the repository.
- Branch protection/rulesets require the normal validation check, dependency review, and successful CodeQL checks before merge where supported and practical.
- Administrators avoid bypassing failed security checks except for a documented emergency remediation.

A fork is not assumed to inherit these settings. Fork/bootstrap documentation should treat this list as an explicit post-fork setup step.

## Dependency vulnerability policy

- Dependency-review PR enforcement threshold: **high** and **critical** known vulnerabilities introduced by the pull request.
- Existing Dependabot alerts should be triaged by exploitability, exposure, dependency scope, available fixes, and whether the package is used at runtime or only for development/build validation.
- A lower-severity alert may still warrant immediate remediation when the project's actual use makes exploitation plausible.
- A security update must still pass normal functional, browser, data-contract, and deployment validation.

## Code-scanning policy

- CodeQL alerts are reviewed as engineering/security findings, not automatically assumed to be exploitable.
- Confirmed high-impact findings block ordinary feature release until fixed or explicitly mitigated.
- False positives may be dismissed only with a concrete rationale in GitHub's alert history.
- Security configuration changes receive the same review/test discipline as application code.

## Fork-friendly verification

After forking:

1. Enable GitHub Actions.
2. Verify the dependency graph.
3. Enable Dependabot alerts and security updates.
4. Confirm the committed CodeQL workflow can upload results.
5. Confirm dependency-review runs on a test pull request.
6. Configure required checks/rulesets if available.
7. Enable private vulnerability reporting if the fork remains public.
8. Review workflow permissions and any owner-specific repository settings before the first production deployment.

No step in this baseline requires a paid external service, API key, hosted database, or runtime secret.

## Maintenance

Review this baseline when GitHub changes its public-repository security feature set, when a new package ecosystem is introduced, or when a workflow begins using a new action. The roadmap's recurring release-readiness audit should verify both committed controls and settings-level controls rather than assuming one proves the other.
