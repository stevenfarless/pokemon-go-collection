# Accessibility contract: WCAG 2.2 AA

The collection companion targets WCAG 2.2 Level AA for primary workflows. Automated checks are regression evidence; they do not by themselves establish conformance. Manual assistive-technology checks remain required where browser automation cannot establish the user experience.

## Verification matrix

| Area | WCAG 2.2 criteria emphasized | Automated evidence | Manual evidence |
| --- | --- | --- | --- |
| Reflow and zoom | 1.4.10 Reflow, 1.4.4 Resize Text | 320 CSS-pixel Playwright reflow check; responsive visual matrix | Safari/iOS zoom and desktop 200%/400% review |
| Text spacing | 1.4.12 Text Spacing | WCAG spacing override at 320 CSS px with overflow/function checks | inspect labels, dense cards, dialogs, and tool panels after browser text-spacing overrides |
| Contrast and state | 1.4.3 Contrast, 1.4.11 Non-text Contrast, 1.4.1 Use of Color | axe scans; forced-colors browser checks | light/dark/high-contrast inspection when themes change |
| Keyboard and focus | 2.1.1 Keyboard, 2.4.3 Focus Order, 2.4.7 Focus Visible, 2.4.11 Focus Not Obscured (Minimum) | drawer focus trap/return tests; focused-control viewport checks | full keyboard traversal on each release candidate |
| Touch and pointer | 2.5.8 Target Size (Minimum) | high-frequency controls checked at 24 CSS px minimum; frequent coarse-pointer controls checked at the preferred 44 CSS px height | iPhone touch review for dense tool surfaces |
| Status and errors | 3.3.x input/error criteria, 4.1.3 Status Messages | axe plus live-region/status assertions in functional tests | VoiceOver/NVDA announcement review for loading, filtering, copy, restore, and failure states |
| Dialogs and dynamic UI | 1.3.x, 2.1.1, 2.4.x, 4.1.2 | axe scans with Filters, comparison, and mobile record-detail dialogs open; functional focus-return tests | open/close each dialog and verify name, focus placement, navigation, and return |
| Adaptability | 1.3.x structure, 1.4.10 Reflow | semantic axe scans; portrait/landscape browser checks | portrait/landscape spot check on iOS |
| Motion | 2.3.3 Animation from Interactions (AAA improvement) and user preference support | `prefers-reduced-motion` computed-style checks | confirm no essential information depends on animation |
| Forced colors | AA contrast/focus implications | Chromium forced-colors emulation and visible focus/borders | Windows high-contrast spot check |
| Drag/reorder | 2.5.7 Dragging Movements | no primary workflow may require drag-only input; comparison reorder uses explicit buttons | verify any future reorder feature has button/keyboard alternatives |

## Automated release rules

Primary Collection, Insights, and Tools pages must pass axe with no serious or critical WCAG-tagged violations. Filters, comparison, and mobile record-detail dynamic states are included in the automated regression layer. Collection must remain operable at a 320 CSS-pixel viewport without page-level horizontal overflow; intentionally scrollable data regions may scroll internally. The same primary mobile workflow must survive the WCAG text-spacing override without page-level overflow or clipped primary controls.

Keyboard focus on primary toolbar and drawer controls must remain within the viewport and visibly styled. High-frequency controls must meet WCAG 2.2's 24 CSS-pixel target-size minimum unless the criterion's spacing/equivalent-target exception clearly applies. On coarse pointers, frequent Collection controls use a 44 CSS-pixel preferred target height where the layout permits it.

`prefers-reduced-motion: reduce` disables nonessential transitions and animations through the shared stability stylesheet. `forced-colors: active` restores visible control borders and focus outlines using system colors instead of relying on decorative color tokens. Portrait and landscape checks require the primary search/filter workflow to remain reachable in both orientations.

## Manual release script

Before a major release or after a material navigation/dialog redesign:

1. On iPhone Safari with VoiceOver, open Collection, search for a Pokémon, open and close Filters, open a record detail, build a comparison, inspect Data Health, and copy the Friend Code. Confirm control names, status announcements, logical reading order, focus placement, and focus return.
2. On Windows with NVDA and Firefox, repeat Collection search/filter/detail/comparison, then open Insights and Tools. Verify headings/landmarks, tables or cards, charts and textual alternatives, dialogs, restore status, error messages, and asynchronous result counts are announced coherently.
3. Complete Collection, Insights, and Tools using only the keyboard. Confirm focus is never trapped outside an open dialog/drawer and never hidden behind sticky content.
4. Review Collection, Insights, and Tools at 200% and 400% browser zoom. Confirm reading order remains logical and no required control is clipped, overlapped, or reachable only through two-dimensional page scrolling.
5. Apply text spacing equivalent to WCAG 1.4.12: line height 1.5, paragraph spacing 2× font size, letter spacing 0.12× font size, and word spacing 0.16× font size. Confirm labels, chips, cards, dialogs, tables, and tool controls remain usable.
6. Rotate iPhone between portrait and landscape during search, filter, detail, comparison, and Tools workflows. Confirm orientation does not remove required functionality.
7. Enable Reduce Motion and verify the application remains understandable without transition/animation cues.
8. Enable Windows High Contrast or another OS/browser forced-color mode and confirm controls, selected/current state, warnings, charts, and focus remain distinguishable without color alone.
9. Trigger a collection-load failure or offline state and a local-data restore validation failure. Confirm the status/error is announced and recovery controls remain operable.

Record any failure as an issue with the page, browser/assistive technology, exact step, expected result, and observed result. Known AA failures block release until fixed or the affected workflow is removed from the supported surface.
