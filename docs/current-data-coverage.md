# Current rotating-data coverage

The external-data framework remains provider-independent and static. Current facts are usable for recommendations only when a normalized snapshot has `freshness.state == "fresh"`. Stale or expired snapshots remain provenance/reference data and are blocked from current recommendations.

Coverage includes events and raids plus explicit category contracts for moves, GO Battle League/cups, Team GO Rocket, Max Battles, research, eggs, and Ditto. A category may be `available-path` when a reviewed manual/static acquisition path exists or `unavailable` when no legally maintainable complete source has been adopted. Unavailable is preferable to silently scraping an easy source.

Official sources are preferred. Community data requires a separate reviewed redistribution/license decision. Provider-specific names never become canonical species/form join keys.
