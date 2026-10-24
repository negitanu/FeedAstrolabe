## Why

Long feed lists need folder-level disclosure, and different reading tasks benefit from dense one-line lists or tile layouts. The reader currently offers source-type disclosure and a single article layout.

## What Changes

- Add keyboard-accessible folder disclosure within each source type, with feed/unread counts, browser persistence, selected-folder reveal and reset.
- Add standard, one-line and tile article layouts with browser-persisted selection and accessible controls.
- Retain the same articles, order, filters, pagination, detail navigation, read/star POSTs, sanitized content and CSP in every layout.
- Validate desktop/mobile layout, persistence and unavailable-storage/no-JavaScript fallback using real browsers.

## Capabilities

### New Capabilities

### Modified Capabilities

- `article-reader`: Persistent folder disclosure and selectable article presentation.

## Impact

Reader template, existing disclosure script, one small layout script, CSS, tests and README. No dependency, DB migration, API or deployment changes.
