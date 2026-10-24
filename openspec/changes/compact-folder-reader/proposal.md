## Why

The operator wants folders as the primary navigation, with RSS/X and other feeds together underneath each folder. The current source-first hierarchy and large reader header/control spacing hide useful content, and unstyled project/tag selects clash with the theme.

## What Changes

- Replace source-first grouping with top-level folder groups, feed source badges and persistent disclosure; migrate compatible previous folder choices.
- Align themed project/tag/search controls, bulk read and layout choices in a compact reader toolbar.
- Reduce reader/sidebar/card spacing and constrain excerpts while retaining readable text and touch controls; collapse mobile navigation by default.
- Measure viewport density before/after on the same synthetic data and validate filters, article actions, persistence and overflow.

## Capabilities

### New Capabilities

### Modified Capabilities

- `article-reader`: Folder-first navigation and compact responsive reader presentation.

## Impact

Reader template, disclosure script, reader-scoped CSS, tests and documentation. No DB/API changes, new dependencies or live deployment.
