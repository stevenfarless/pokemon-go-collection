# Lightweight design system

The UI uses semantic tokens instead of feature-specific colors. `site/design-system.css` defines surfaces, text hierarchy, borders, focus, status colors, spacing, radii, typography, elevation, and 24/44px target-size tokens while mapping the legacy `--surface`, `--text`, `--muted`, `--line`, `--accent`, `--focus`, and `--danger` names onto the same contract.

Appearance supports `system`, `light`, and `dark`. The explicit override is browser-local under `pokemon-go-collection:appearance:v1`; `system` removes the override and follows `prefers-color-scheme`. A small generated head bootstrap applies an explicit override before styles paint, while `site/design-system.js` owns validation, persistence, the preference control, and runtime updates.

Reusable patterns are `.ds-card`, `.ds-toolbar`, `.ds-pill`, `.ds-source-chip`, `.ds-status`, `.ds-notice`, `.ds-empty`, `.ds-segmented`, and `.ds-danger-confirm`. Status classes always include readable text in addition to border/color state. Forced-colors and reduced-motion rules are part of the shared stylesheet.

The generated `style-guide.html` is the internal static reference. It is intentionally original and generic and does not imitate Pokémon GO branding or proprietary visual assets.
