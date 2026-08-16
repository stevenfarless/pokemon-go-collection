# Static-analysis and maintainability policy

The project uses small, explicit quality gates chosen for high signal. The purpose is to catch correctness and maintainability problems early without forcing framework churn, a wholesale TypeScript rewrite, or style-only refactors unrelated to product work.

## Python

Ruff is pinned in `requirements-dev.txt` and configured in `pyproject.toml` for Python 3.12.

The initial enforced rule set is deliberately correctness-focused:

- `E4`: import-related pycodestyle errors;
- `E7`: statement-related pycodestyle errors;
- `E9`: runtime/syntax-class pycodestyle errors;
- `F`: Pyflakes correctness diagnostics such as undefined or unused names/imports.

Generated output and browser-report directories are excluded. The rule set may be expanded after the existing codebase is clean and the additional rule demonstrates useful signal. Rules should not be enabled merely to produce a larger lint count.

Ruff formatter settings are recorded for consistent future use, but automatic formatting is not a release gate yet. Formatting policy can become stricter after representative diffs demonstrate that it improves maintainability without obscuring functional changes.

## JavaScript

`eslint.config.mjs` uses ESLint's built-in correctness rules. The repository invokes an exact ESLint version through the `lint:js` package script so CI is reproducible without adding a large new transitive dependency tree to the project's runtime or package lock solely for linting.

The initial rules target problems such as:

- impossible/incorrect control flow;
- duplicate cases, keys, arguments, and class members;
- assignment to constants/functions/classes/imports;
- invalid regular expressions and numeric precision errors;
- unreachable code and unsafe `finally` behavior;
- suspicious async Promise executors and Promise executor returns;
- invalid `typeof`, `NaN`, setter/getter, constructor, and `super` behavior.

Global-name/style rules are intentionally not used as a proxy for correctness. Browser and Node modules in this repository use several global environments, so a future `no-undef` rollout should be paired with explicit environment/global contracts rather than a broad suppression file.

## JavaScript type checking evaluation

`tsc --checkJs` was evaluated for this roadmap issue but is not an initial release gate. Much of the current browser code is dynamic plain JavaScript without sufficiently complete JSDoc contracts; enabling broad check-JS immediately would primarily create migration noise rather than reliable type guarantees.

The preferred incremental path is:

1. add precise JSDoc typedefs/contracts to high-risk deterministic modules as they are touched;
2. type-check those modules or a small typed boundary first;
3. expand only when the checked surface produces actionable signal;
4. do not rewrite functioning modules into TypeScript solely to raise a tooling metric.

CodeQL from the security baseline provides an additional semantic-analysis layer but does not replace linting or future type checking.

## Workflow/YAML validation

GitHub itself parses Actions workflow YAML before execution, and the CodeQL `actions` language in the security baseline analyzes workflow code. The project does not currently add a second YAML linter solely for stylistic YAML rules. A dedicated workflow linter should be introduced only if it catches defects not already covered by GitHub parsing/CodeQL and can be pinned/maintained cheaply.

## Maintainability guidance

Large modules are not automatically defects. Refactor when a module's size or responsibilities materially harm one or more of:

- deterministic unit testing;
- reviewability of changes;
- reuse of shared rules/contracts;
- isolation of browser-local state;
- performance/lazy loading;
- source/freshness/provenance boundaries.

Do not split files merely to satisfy an arbitrary line-count target. Prefer extracting stable pure functions, typed data boundaries, and reusable UI primitives when doing so removes duplication or makes safety rules easier to test.

## CI behavior

`.github/workflows/static-analysis.yml` runs as a separate fast gate on relevant pull requests and pushes to `main`. It executes before merge independently of the heavier browser/Lighthouse validation workflow.

Static-analysis failures should be corrected, or the rule/configuration should be changed explicitly with a documented reason. Broad inline suppressions are discouraged; when an exception is genuinely necessary, keep it as narrow as possible and explain the reason near the code or configuration.

## Updating tool versions

- Ruff is a normal pip development dependency and can be maintained through Dependabot once #109 is complete.
- ESLint is pinned exactly in the package script; update that version deliberately, review release notes, and run the full static-analysis suite.
- Tool upgrades must not silently broaden rule behavior without review.
