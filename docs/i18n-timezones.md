# Internationalization and timezone architecture

`site/i18n.js` separates presentation strings from business logic with stable keys and an English catalog. `en-XA` is a maintained pseudo-locale used to expose long-string/layout assumptions without claiming an additional human translation. Unsupported browser locales format through `Intl` while UI copy falls back to the English catalog.

Canonical species/form/move IDs and API keys remain locale-neutral. Localization changes presentation and aliases only. No decision rule should inspect translated labels.

Dates, times, numbers, relative time, and sorting use `Intl`. Event/current-data timestamps remain normalized machine timestamps. Planning defaults to the browser IANA timezone, with a browser-local override under `pokemon-go-collection:timezone:v1`. The locale preference is stored under `pokemon-go-collection:locale:v1`.

Machine resources remain locale-neutral unless a future resource explicitly declares otherwise. A versioned redistributable alias dataset is required before non-English Pokémon/move aliases are added.
