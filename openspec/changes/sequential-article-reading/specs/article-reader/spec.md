## ADDED Requirements

### Requirement: Filtered sequential article browsing
The reader SHALL provide previous/next article links and the current position within the complete current filter in published_at DESC, id DESC order. Links SHALL preserve feed, view, query, workspace and tag filters and show the target's list page. GET browsing SHALL NOT change read or star state. Sequential controls SHALL remain usable without JavaScript.

#### Scenario: Cross a page boundary
- **WHEN** a user opens the last article on a list page and follows the next article link
- **THEN** the next matching article and its corresponding list page are displayed with all filters preserved

#### Scenario: Equal timestamps
- **WHEN** matching articles have equal publication timestamps
- **THEN** consecutive navigation follows descending article IDs without duplicates or skips

#### Scenario: Detail outside the filter
- **WHEN** a directly opened article is outside the current filter
- **THEN** its detail remains readable, a filter mismatch is shown and sequential controls are omitted

### Requirement: Explicit read and advance
The reader SHALL offer a CSRF-protected POST that marks only the current matching article read and advances to its filtered successor chosen before mutation. It SHALL preserve stars and all reader filters, recalculate the successor's list page after mutation and derive the redirect on the server. Invalid conditions or stale membership SHALL be rejected before any read-state change.

#### Scenario: Shrinking unread list
- **WHEN** a user marks the current unread article read and advances
- **THEN** the immediately following matching unread article is shown without skipping it, on its updated list page

#### Scenario: Final matching article
- **WHEN** the current article has no filtered successor and the user marks it read and advances
- **THEN** only that article becomes read and the user returns to the same filtered list with an end-of-sequence notice

#### Scenario: Stale or invalid input
- **WHEN** the article was deleted, no longer matches the conditions, the conditions are malformed or the CSRF token is invalid
- **THEN** the action returns the corresponding error without marking any article read
