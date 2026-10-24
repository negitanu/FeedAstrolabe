## Context

The user explicitly chose folders as the top-level navigation, merging feed kinds within the same folder. Source-first groups currently duplicate folder headings. Reader controls wrap inside a narrow form with unstyled selects; oversized header/card padding and mobile navigation delay article visibility.

## Goals / Non-Goals

**Goals:** One visible group per exact folder name, theme-consistent compact controls, more articles per viewport, persistent disclosure/layout, accessible mobile navigation.

**Non-Goals:** Changing stored folders, article sorting/filter semantics, shared settings, APIs, dependencies or deployment.

## Decisions

- Render folders directly from all feeds using case-sensitive raw names. Each feed carries a small source label; counts aggregate across kinds. Preserve empty versus literal unclassified identity, escaping and selected-feed reveal. This supersedes the earlier source-first display hierarchy.
- Use a version-2 folder preference map keyed by raw folder name. When no v2 preference exists, merge valid v1 source/folder choices: a merged folder stays closed only when every currently present kind was saved closed. Keep mixed/new groups visible. Reset removes both legacy source/folder keys and v2. Layout preferences stay unchanged.
- Put project/tag/search controls in a responsive grid, with matching select/input/button heights, theme colors and visible focus. Keep bulk read and layout selection adjacent. Preserve GET/POST names, hidden scope values and current URLs.
- Apply compact spacing only to the reader. Reduce desktop topbar/header/sidebar rows, clamp standard excerpts to two lines, reduce tile padding and row height. Keep desktop text readable and mobile targets at least 40px. Unrelated settings/research screens retain their layout.
- Wrap navigation in native details, open on desktop. The existing nonce-authorized script collapses it on mobile and handles breakpoint changes. No-JavaScript navigation stays open and fully usable. Selected folders still reveal inside the panel; users open the mobile panel to navigate.
- Measure the same synthetic library at 1440x900 and 390x844 before/after, using top-of-page screenshots, first article position and fully visible card counts. Validate all layout modes, detail panes and filters in real Chromium.

## Risks / Trade-offs

- Source-specific tests/preferences no longer map one-to-one → migrate merged folder choices conservatively and replace obsolete hierarchy assertions with folder-first behavior tests; retain CSP, action and fallback coverage.
- Compact styling could hide controls/overflow → breakpoint-specific grids, keyboard/touch tests, geometry assertions, visual QA and unchanged body typography.
- Mobile disclosure could hide navigation unexpectedly → explicit labeled summary and native operation; desktop breakpoint restores open navigation.

## Migration Plan

No data migration. New browser folder preference format migrates old choices once, without discarding the legacy data until reset. Stored layout mode remains. Rebuild the existing app after verification; no live restart is part of this task.
