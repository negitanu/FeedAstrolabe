## ADDED Requirements

### Requirement: Register supported social sources
The system SHALL register X accounts/lists and public Mastodon accounts through CSRF-protected settings and write-scoped API, and reject duplicate or invalid sources without a network request at registration.

#### Scenario: Register and inspect
- **WHEN** a user registers a valid social source
- **THEN** it appears in shared feed lists with provider metadata and is collected on a worker tick or explicit refresh

#### Scenario: Invalid source
- **WHEN** a source supplies an unsupported kind, private origin or credential field
- **THEN** registration fails without exposing or persisting credentials

### Requirement: Durable bounded incremental collection
The system SHALL preserve stable post IDs and read/star state, take one initial page and subsequently process at most three pages per poll with durable continuation and a fixed lower bound.

#### Scenario: More than a batch
- **WHEN** new posts fill more than three pages
- **THEN** continuation survives restart and the high-water ID advances only after all pages finish

#### Scenario: Later page fails
- **WHEN** a page fails after an earlier page committed
- **THEN** earlier posts and continuation remain and the retry resumes from that cursor

### Requirement: Unified reading and status
The system SHALL render sanitized SNS content with read/star/search support and expose posts through existing authenticated article endpoints; RSS OPML export SHALL exclude SNS records.

#### Scenario: Repeat post
- **WHEN** a post ID is collected again with changed content
- **THEN** content updates while its article ID, read and star state remain

### Requirement: Respect retry gates
The system SHALL display safe authentication/rate-limit errors and persisted next retry times and honor provider cooldowns for worker and manual polls; X cooldown SHALL apply to all X sources sharing its credential.

#### Scenario: Rate limited
- **WHEN** X responds 429 with a reset time
- **THEN** no X source is requested until the reset time and existing posts remain accessible
