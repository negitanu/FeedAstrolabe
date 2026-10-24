## 1. Reader redesign

- [x] 1.1 Implement folder-first groups, source badges and compatible persistent disclosure migration.
- [x] 1.2 Align themed reader controls, compact spacing and accessible mobile navigation.

## 2. Verification

- [x] 2.1 Update hierarchy/browser tests and verify filters, migration, mobile navigation, layout and article actions.
- [x] 2.2 Measure and visually inspect before/after density, document behavior and pass full regression plus strict spec/secret/diff checks.

Verification: all 406 tests passed with real Chromium and no skips; focused browser checks passed for combined folders, v1-to-v2 choices, scopes/bulk read, mobile navigation and 320–1920px viewports. The same synthetic library showed first desktop article y422→149px and complete standard/line/tile cards 2→5, 9→20, 4→12 at 1440×900; mobile initial article y1958→351px. Desktop/mobile screenshots were inspected. All 29 OpenSpec items, diff/secret checks and Gitleaks source/tests/docs scans passed. See docs/verification-compact-reader.md. No live service or operator data was changed.
