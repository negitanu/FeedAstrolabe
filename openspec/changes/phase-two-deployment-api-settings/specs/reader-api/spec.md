## ADDED Requirements

### Requirement: API key lifecycle
The system SHALL issue cryptographically random read-only or read/write keys with 1–365 day expiry, show plaintext only on issuance, store only a hash, and allow immediate revocation. API requests SHALL require a Bearer key and enforce a persistent per-key minute rate limit.

#### Scenario: Issue and revoke
- **WHEN** a key is issued and later revoked
- **THEN** plaintext is unavailable on subsequent settings views and revoked requests return 401

#### Scenario: Scope and rate
- **WHEN** a read-only key attempts a mutation or an active key exceeds the configured rate
- **THEN** requests return 403 or 429 respectively without changing article state

### Requirement: Feed and article API
The system SHALL expose JSON feed lists, individual feeds, bounded cursor-paginated articles and article detail with read/star state. It SHALL support feed/unread/starred/text filters, ascending after_id synchronization, write-scoped subscription creation and explicit article state updates. API errors SHALL be JSON and documented.

#### Scenario: Retrieve filtered articles
- **WHEN** an authenticated client requests unread articles for a feed with limit and cursor
- **THEN** only matching articles are returned with the next cursor and no duplicates across pages

#### Scenario: Subscribe and update
- **WHEN** a write-scoped key registers a valid feed or updates an article state
- **THEN** the change persists and appears in the UI
