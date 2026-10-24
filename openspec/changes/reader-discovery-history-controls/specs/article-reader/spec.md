## MODIFIED Requirements

### Requirement: Article browsing
The system SHALL provide a responsive Japanese UI, deterministically sorted article lists, newest-first by default, article detail, HTTP(S) original links, and combined feed, folder, unread, starred, history, detailed literal search, date range, multiple source, workspace and tag filters. The reader SHALL progressively append matching articles as the user scrolls, without numbered pages, previous/next page controls or a user-facing result-count limit. Opening a detail SHALL NOT mutate read state; marking read SHALL require an explicit POST. Public API pagination SHALL remain compatible.

#### Scenario: Search and filter
- **WHEN** a user selects unread articles and searches for a title or content fragment
- **THEN** only matching unread articles are listed, and all subsequent batches retain the same complete filter

#### Scenario: Browse empty list
- **WHEN** no articles match the selected view
- **THEN** a meaningful empty state is displayed without a loading loop or pagination controls

#### Scenario: Read beyond the first batch
- **WHEN** the end of the rendered list approaches the viewport
- **THEN** the next batch is appended once in the selected deterministic date/id order until no matching results remain, with no page navigation

#### Scenario: Stable continuation while data changes
- **WHEN** newer articles arrive or earlier articles are removed between continuation requests
- **THEN** existing matching articles are not skipped because of offset shifts and an article ID is not rendered twice

#### Scenario: Invalid or mismatched continuation
- **WHEN** a continuation is modified, malformed or used with different reader filters
- **THEN** the request fails without returning an unfiltered or broader batch

#### Scenario: Loading failure and keyboard access
- **WHEN** an additional request fails or automatic intersection observation is unavailable
- **THEN** existing articles remain visible and a keyboard-operable control can retry or load the next batch without an automatic retry loop

#### Scenario: Keep the loaded list while reading
- **WHEN** a user opens an appended article, navigates between article details, closes the detail or returns with browser history
- **THEN** the loaded cards, display layout, filters and reading position remain available without resetting to the first batch

#### Scenario: Read and star from an appended article
- **WHEN** a user marks an appended article read/unread or starred/unstarred
- **THEN** the mutation applies to that article and the retained list is reconciled with the active filter without duplicate cards or a pagination transition

#### Scenario: Legacy and no-script access
- **WHEN** an old reader URL contains a page parameter or JavaScript is disabled
- **THEN** its valid filters and requested article remain usable, and all matching articles remain reachable through a full-results fallback without numbered pagination
