# Release readiness and recurring product audit

This document defines the evidence required before the project can describe a build as a gold-standard release candidate. It also defines a bounded recurring audit that can be run manually or on a quarterly schedule without creating routine issue noise.

## Release status

A gold-standard release candidate requires every mandatory gate below to have current evidence and a passing result. Any failed or missing mandatory gate blocks that status.

Evidence must come from repository artifacts, workflow results, documented human review, or checked-in reports. A statement that a gate was reviewed without supporting evidence is insufficient.

## Mandatory gates

| Area | Required evidence | Pass condition |
| --- | --- | --- |
| Correctness and destructive decisions | Open-defect review plus relevant automated tests | No unresolved critical or high-severity correctness or destructive-decision defect |
| Security and supply chain | CodeQL, dependency review, static analysis, dependency/update status | Required security checks pass and no known critical/high risk is left untracked |
| Browser support | Supported-browser automated results plus current real-device checklist | Supported-browser contract passes, with documented limits where real-device coverage is unavailable |
| Accessibility | Automated accessibility checks plus a WCAG 2.2 AA human review record | No known blocking WCAG 2.2 AA failure remains untracked |
| Visual and responsive behavior | Responsive/visual test results and reviewed state matrix | Required layouts and states pass at supported sizes |
| Test depth | Coverage, mutation, fuzz/property, and resilience evidence where applicable | Repository thresholds pass and important behavior has regression coverage |
| Performance and scale | Current performance/resource-budget results | Required budgets pass for representative and stress-size data |
| Local data safety | Backup, restore, migration, storage-health, and failure-path evidence | Supported recovery paths pass without silent data loss |
| Privacy and publication | Public-output/privacy review | No known unintended private or sensitive data is published |
| External data | Source registry, freshness checks, license/terms review, and stale-data behavior | Current claims meet repository source/freshness rules and stale inputs fail safely |
| Pokémon GO mechanics | Mechanics coverage registry/change-detection evidence | Required mechanics are current or explicitly marked unsupported/unknown |
| Usability | Beginner, intermediate, and advanced task-review results | Required tasks can be completed without known high-severity usability blockers |
| Machine/LLM outputs | Generated-data/schema/contract validation | Published machine-readable outputs pass their contracts and preserve provenance/uncertainty |
| Known limitations | Current human- and machine-readable limitation list | Material limitations are explicit, scoped, and severity/impact is recorded |

## Evidence record

A release-readiness review should record:

- review date and commit SHA;
- reviewer or workflow responsible for each gate;
- evidence links or artifact paths;
- pass, fail, or blocked status for every mandatory gate;
- concise explanation for failures or blocked gates;
- known limitations and their impact;
- follow-up issue numbers for concrete defects or missing work.

A blocked gate is treated the same as a failed gate for release-status purposes.

## Product heuristic audit

The recurring product review covers these observable areas:

1. Discoverability and hierarchy: important tasks are visible and reachable without hunting through unrelated tools.
2. Consistency and feedback: equivalent actions behave consistently and important actions give clear success, failure, and progress feedback.
3. Error prevention and recovery: destructive or irreversible actions have appropriate safeguards and recoverable failures expose a recovery path.
4. Progressive disclosure: common tasks remain simple while advanced details are available when requested.
5. Mobile use: primary controls remain usable at supported narrow widths and touch targets stay practical for one-handed use.
6. Terminology and cognitive load: labels match Pokémon GO/Poke Genie concepts where appropriate and avoid unexplained repository-specific terms.
7. Last-mile actionability: recommendations identify exact owned Pokémon and provide a practical handoff back to Pokémon GO or Poke Genie when supported.
8. Trust and uncertainty: source, freshness, confidence, assumptions, and unsupported states remain visible where they affect decisions.
9. Feature overlap and dead UI: duplicated tools, stale routes, unreachable controls, and abandoned interfaces are identified.
10. Performance and maintainability: repeated expensive work, avoidable workflow duplication, fragile coupling, and excessive permissions are reviewed.

## Recurring audit cadence

Run the full audit quarterly and allow a manual run at any time. Keep the audit GitHub-native and bounded: reuse existing tests and artifacts instead of duplicating large test matrices.

Run a targeted audit after either of these changes:

- a major Pokémon GO mechanic, inventory, battle, trade, event, or account-system change that affects repository guidance;
- a major repository architecture, storage, generated-data, security, or deployment change.

A targeted audit reviews only the gates and heuristic areas that the change can affect, plus any directly dependent contracts.

## Issue creation rule

Recurring audits must not create routine tracking issues merely because an audit ran. Create or update an issue only when the audit finds a concrete defect, missing evidence, stale contract, failed mandatory gate, or actionable improvement with a defined scope.

When an existing issue already tracks the finding, update that issue instead of creating a duplicate.

## Completion rule for issue #159

This contract establishes the required evidence, pass/fail semantics, audit scope, recurrence, targeted-audit triggers, and no-spam issue rule. Issue #159 remains open until the repository also provides the evidence-producing release report and bounded GitHub-native execution path required by its acceptance criteria, and the retained roadmap dependencies are complete.
