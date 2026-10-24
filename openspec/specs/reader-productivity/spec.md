## Purpose

Provide safe discovery and productive daily article reading without changing existing API pagination.

## Requirements

### Requirement: Independent recent reading history
The reader SHALL persist the latest actual detail visit per article independently of read/star state using CSRF-protected POST. A 最近読んだ記事 view SHALL order by latest visit by default and retain all normal filters. Bulk read, star changes, GET/API reads and middle-click original access SHALL NOT create visits. The shared-library history SHALL survive restart and disappear with deleted articles.

#### Scenario: Read an old article again
- **WHEN** an old article is opened and its visit is recorded
- **THEN** it appears first in history without changing its read/star state

#### Scenario: Non-visit state changes
- **WHEN** articles are bulk-marked read or starred without opening them
- **THEN** history remains unchanged

### Requirement: Shared deterministic ordering
The reader SHALL offer 新しい順 and 古い順 for publication date, and 最近読んだ順 for history. Ordering SHALL include article ID as tie-breaker and be shared by continuation, detail neighbours, next unread and explicit read-next. Signed continuation scope SHALL include order and all filters.

#### Scenario: Ascending continuation and next article
- **WHEN** old-first results span multiple batches with equal publication dates
- **THEN** all matching IDs are returned once in ascending date/ID order and detail next uses that order

#### Scenario: Cursor scope mismatch
- **WHEN** a continuation is reused with a different order or detailed condition
- **THEN** the request is rejected without broadening results
