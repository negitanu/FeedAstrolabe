## Why

Reading a sequence currently requires returning to the list after each article. Marking an article read in an unread view shrinks that list, so advancing by a fixed list offset can skip the next article.

## What Changes

- Add previous/next article links and a position indicator within the current combined filter, across list pages.
- Add an explicit CSRF-protected “mark read and next” action that selects the successor before mutation and redirects to its updated list page.
- Preserve native links/forms and existing GET read-only behavior. Handle boundaries and stale filters without marking unrelated articles.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `article-reader`: Add filtered sequential browsing and explicit read-and-advance requirements.

## Impact

Reader queries, Japanese templates/styles and a new UI POST action; focused server and real-browser tests. No database migration, API contract change or additional JavaScript dependency.
