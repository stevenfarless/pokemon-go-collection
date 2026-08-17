# Accessibility contract: WCAG 2.2 AA

The collection companion targets WCAG 2.2 Level AA for primary workflows. Automated checks are regression evidence; they do not by themselves establish conformance. Manual assistive-technology checks remain required where browser automation cannot establish the user experience.

## Verification matrix

| Area | WCAG 2.2 criteria emphasized | Automated evidence | Manual evidence |
| --- | --- | --- | --- |
| Reflow and zoom | 1.4.10 Reflow, 1.4.4 Resize Text | 320 CSS-pixel Playwright reflow check; responsive visual matrix | Safari/iOS zoom and desktop 400% review |
| Contrast and state | 1.4.3 Contrast, 1.4.11 Non-text Contrast, 1.4.1 Use of Color | axe scans; forced-colors browser checks | light/dark/high-contrast inspection when themes change |
| Keyboard and focus | 2.1.1 Keyboard, 2.4.3 Focus Order, 2.4.7 Focus Visible, 2.4.11 Focus Not Obscured (Minimum) | drawer focus trap/return tests; focused-control viewport checks | full keyboard traversal on each release candidate |
| Touch and pointer | 2.5.8 Target Size (Minimum) | high-frequency controls checked at 24 CSS px minimum; 44 px preferred controls retained where layout permits | iPhone touch review for dense tool surfaces |
| Status and errors | 3.3.x input/error criteria, 4.1.3 Status Messages | axe plus live-region/status assertions in functional tests | VoiceOver announcement review for loading, filtering, copy, restore, and failure states |
| Adaptability | 1.3.x structure, 1.4.10 Reflow | semantic axe scans; phone/tablet/desktop browser tests | portrait/landscape spot check on iOS |
| Motion | 2.3.3 Animation from Interactions (AAA improvement) and user preference support | `prefers-reduced-motion` computed-style checks | confirm no essential information depends on animation |
| Forced colors | AA contrast/focus implications | Chromium forced-colors emulation and visible focus/borders | Windows high-contrast spot check when available |
| Drag/reorder | 2.5.7 Dragging Movements | no primary workflow may require drag-only input | verify any future reorder feature has button/keyboard alternatives |

## Automated release rules

Primary Collection, Insights, and Tools pages must pass axe with no serious or critical violations. Collection must remain operable at a 320 CSS-pixel viewport without page-level horizontal overflow; intentionally scrollable data regions may scroll internally. Keyboard focus on primary toolbar and drawer controls must remain within the viewport and visibly styled. High-frequency controls must meet WCAG 2.2's 24 CSS-pixel target-size minimum unless the criterion's spacing/equivalent-target exception clearly applies.

`prefers-reduced-motion: reduce` disables nonessential transitions and animations through the shared stability stylesheet. `forced-colors: active` restores visible control borders and focus outlines using system colors instead of relying on decorative color tokens.

## Manual release script

Before a major release or after a material navigation/dialog redesign:

1. On iPhone Safari with VoiceOver, open Collection, search for a Pokémon, open and close Filters, change a filter, inspect Data Health, and copy the Friend Code. Confirm focus order, control names, status announcements, and focus return.
2. On desktop, complete the same flow using only the keyboard. Confirm focus is never trapped outside an open dialog/drawer and never hidden behind sticky content.
3. Review Collection, Insights, and Tools at 200% and 400% zoom. Confirm reading order remains logical and no required control is clipped or overlapped.
4. Enable reduced motion and verify the application remains understandable without transition/animation cues.
5. Enable an OS/browser high-contrast or forced-colors mode and confirm controls, selected/current state, warnings, and focus remain distinguishable without color alone.

Record any failure as an issue with the page, browser/assistive technology, exact step, expected result, and observed result. Known AA failures block release until fixed or the affected workflow is removed from the supported surface.
