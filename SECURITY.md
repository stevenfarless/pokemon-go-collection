# Security policy

## Supported versions

Security fixes target the current `main` branch and the current GitHub Pages deployment. Historical commits, archived Poke Genie exports, and superseded generated builds are retained for project history and are not maintained as separate supported software versions.

## Reporting a vulnerability

Please do not publish exploit details, sensitive data, credentials, or a working proof of concept in a public issue.

For a suspected security vulnerability:

1. Use the repository's **Security and quality → Report a vulnerability** flow when private vulnerability reporting is enabled.
2. If that private reporting control is not available, open a minimal public issue titled `Security contact request` with no exploit details or sensitive data. The maintainer can then establish an appropriate private channel.

A useful private report should include, when known:

- the affected page, workflow, script, or data boundary;
- reproduction steps;
- security impact and realistic attacker prerequisites;
- browser/OS or GitHub Actions context where relevant;
- whether public collection data or browser-local private state is involved;
- a suggested remediation, if you have one.

Do not include unrelated collection exports, private notes, precise location information, access tokens, or credentials.

## Scope priorities

Particularly important reports include:

- DOM/script injection or unsafe URL handling;
- exposure of browser-local notes, enrichment, goals, or backup contents;
- workflow or dependency supply-chain compromise;
- unsafe GitHub Actions permissions or untrusted-code execution;
- generated-data validation bypasses that could publish malformed or misleading collection facts;
- service-worker/cache behavior that can mix incompatible builds or misrepresent stale data as current;
- vulnerabilities in import/restore or other local file-processing boundaries.

Ordinary Pokémon GO gameplay disagreements, stale game-balance opinions, or incorrect source data without a security consequence should use normal issues instead.

## Disclosure and remediation

The project follows coordinated disclosure. Valid reports should be reproduced privately, fixed on a dedicated branch or private advisory workspace when necessary, validated through the normal security/test gates, and disclosed publicly only after a safe fix or mitigation is available.

There is no guaranteed response-time SLA for this personal open-source project, but security reports should be handled before ordinary feature work when the reported impact is credible and material.
