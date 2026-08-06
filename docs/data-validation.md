# Poke Genie export validation policy

The production build validates CSV values before normalization. Diagnostics identify the CSV row number, Poke Genie source index, Pokémon name when available, column, offending value, severity, and the action taken.

Fatal errors stop deployment. They include a missing Pokémon name and missing, non-numeric, decimal, or non-positive values for `Pokemon Number` and `CP`. The build never falls back to an older export.

Malformed optional fields create warnings. The affected field is replaced with a missing value before normalization, preventing corrupted data from being published as a legitimate number. This covers HP, IVs, IV percentage, levels, dimensions, dust and candy costs, PvP ranks, stat products, status codes, and booleans. Blank optional fields are treated as intentionally missing and do not create warnings.

Recognized Shadow/Purified codes are `0` normal, `1` Shadow, and `2` Purified. Unknown codes are never silently treated as ordinary data. Levels must be from 1 through 51 in 0.5-level increments. IV components must be integers from 0 through 15, and percentages must be from 0 through 100.

Each successful build publishes `data/build-diagnostics.json`. The build manifest records warning and error counts and links to that report. CI tests cover decimal integer fields, non-numeric strings, out-of-range IVs, unknown status codes, level validation, and blank optional values.
