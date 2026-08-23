# Static publication privacy profiles

Set `POKEMON_GO_PRIVACY_PROFILE` at build time to one of:

- `full-public`: preserves the current owner's intentional public collection and friend-code behavior.
- `redacted`: publishes collection data while blanking source row indices, per-record scan/original-scan/catch dates, and any detected source columns whose names indicate precise location, trainer/friend identifiers, nicknames, or acquisition timestamps. The friend code is withheld by default.
- `private-local-preview`: applies the redacted behavior and writes a deployment-blocking marker. The Pages promotion guard must reject this profile.

`POKEMON_GO_PUBLISH_FRIEND_CODE=1` explicitly publishes the configured friend code in profiles where it is otherwise withheld. `POKEMON_GO_FRIEND_CODE` and `POKEMON_GO_PUBLIC_TITLE` let forks replace the current owner's public identity instead of inheriting it. When friend-code publication is disabled, the build removes the friend code from both visible trainer contact and metadata descriptions.

Redaction happens before shards, species/family views, recommendations, investments, history, and planning resources are generated. A final pass redacts record-shaped objects in generated JSON/CSV resources. JSON Schema, knowledge, and external-game-data resources are excluded from record redaction because they are contracts/game facts rather than owner collection records.

Opaque canonical `record_id`/`entity_id` values remain stable under redaction. This preserves joins and historical semantics without revealing the raw per-record dates used by source observations. `data/privacy-audit.json` and `privacy-audit.md` list the selected profile, sensitive source columns detected, resources redacted, friend-code publication state, and whether public deployment is allowed.

The canonical manifest `source_sha256` continues to identify the original archived source used to build the collection. The privacy audit separately records `published_export_sha256` for the profile-filtered `data/latest-export.csv`, so a redacted public artifact is never misrepresented as byte-identical to the private archived source.

Browser-local annotations, enrichment, goals, saved views, budgets, recovery snapshots, and diagnostics are never inputs to the static publication pipeline.
