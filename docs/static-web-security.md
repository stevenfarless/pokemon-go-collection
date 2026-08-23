# Static-web security boundary

Every URL parameter, imported backup value, browser-local value, Poke Genie field, and external/current-data string is treated as untrusted data. Rendering code should prefer `textContent`, element properties, and explicit element creation. When existing templated `innerHTML` is retained, interpolated values must be escaped before insertion.

`site/security.js` blocks non-HTTP(S) DOM anchor schemes such as `javascript:` and `data:` and hardens dynamically inserted links. Imported local-data documents continue to be schema-validated on restore and are revalidated by Storage Health when read for diagnostics or recovery.

The generated Pages site receives a meta Content Security Policy that limits active resources to the same origin, blocks plugins and frames, constrains base URLs and form destinations, and restricts workers/manifests to the site origin. GitHub Pages does not provide repository-controlled response headers. The existing generated offline connectivity probe and critical/preload style mechanism use trusted inline code, so `script-src` and `style-src` currently retain `unsafe-inline`. Removing that allowance requires moving those generated inline bootstraps to external hashed assets. `frame-ancestors` is not honored in a meta CSP and is therefore not claimed as protection.

Trusted Types is capability-detected for diagnostics and documented as a possible progressive defense. It is not enforced while existing safe templated HTML sinks remain in the application because partial enforcement would break supported browsers or existing rendering paths.

PR validation scans JavaScript for executable-string sinks and runs hostile URL/JSON fixtures. New code must not add `eval`, `new Function`, `document.write`, inline event-string construction, or unsafe URL schemes.
