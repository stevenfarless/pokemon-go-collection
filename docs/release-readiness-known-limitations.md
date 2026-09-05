# Release-readiness known limitations

The release-readiness evidence file includes a top-level `known_limitations` array for current limitations that need to remain visible in both machine-readable and human-readable audit output.

Each entry uses:

- `id`: stable nonblank identifier.
- `severity`: `low`, `medium`, `high`, or `critical`.
- `impact`: concrete user or repository impact.
- `issue`: linked GitHub issue number when available; required for `high` and `critical` entries.
- `evidence`: supporting artifact or source references.
- `notes`: optional context.

High and critical limitations block full release-candidate status even when every mandatory audit gate passes. Low and medium limitations remain visible in the report and may coexist with release-candidate status when the reviewed gates otherwise pass.

The `known_limitations` gate still requires its own reviewed evidence before it can pass. An empty top-level array therefore represents the reviewed conclusion that no current limitations were recorded; it does not make the gate pass by itself.
