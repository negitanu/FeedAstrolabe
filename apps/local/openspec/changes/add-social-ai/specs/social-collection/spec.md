## ADDED Requirements

### Requirement: Public SNS sources
The system SHALL register Mastodon hashtags (1-3), Mastodon local accounts and Bluesky keyword searches, share reader folders/states, and exclude SNS internal URLs from RSS OPML.

#### Scenario: Register without collection
- **WHEN** a user saves an SNS source
- **THEN** the definition is stored without outbound requests and appears in the library

### Requirement: Bounded atomic samples
The system SHALL deduplicate public posts, persist engagement-ranked top 40, tags and the latest 30 runs, preserve prior success on any failed page, and retain read/star states.

#### Scenario: Partial failure
- **WHEN** the second upstream page fails
- **THEN** no partial run or partial articles are committed

#### Scenario: Repeated collection
- **WHEN** the same post appears in several search orders
- **THEN** it has one article and one ranking entry per run

### Requirement: Scheduled collection and shared waits
The system SHALL respect a persistent global collection pause, per-source pause, 15-1440 minute intervals and 1-168 hour windows, exponential backoff and service-wide 429 waits including manual requests.

#### Scenario: Rate limit
- **WHEN** a service returns 429 with Retry-After
- **THEN** all sources for the service wait until that deadline without immediate retries

#### Scenario: Global pause
- **WHEN** automatic collection is globally paused after an automatic AI job was queued
- **THEN** scheduled collection stops and the automatic job fails before transmission while explicit manual operations remain available
