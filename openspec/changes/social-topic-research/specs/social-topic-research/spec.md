## ADDED Requirements

### Requirement: Configurable official API topics
The system SHALL accept Mastodon hashtag topics and Bluesky keyword topics with a name, folder, 900–86400 second polling interval and 1–168 hour window, without fetching at registration. It MUST reject invalid origins, unsupported fields and credentials.

#### Scenario: Create research topic
- **WHEN** a user registers a valid topic through CSRF-protected UI or write-scoped API
- **THEN** the topic appears in its reader folder and the worker collects it when due

#### Scenario: Invalid or unauthorized settings
- **WHEN** a read-only API key writes a topic or a user supplies private origins or invalid limits
- **THEN** the request is rejected without network access or partial writes

### Requirement: Bounded periodic collection
The system SHALL use public HTTPS JSON official endpoints, deduplicate samples, exclude private posts/boosts and posts outside the time window, and enforce bounded requests and safe response validation.

#### Scenario: Scheduled research
- **WHEN** an enabled topic is due and global collection is enabled
- **THEN** at most three Mastodon or two Bluesky requests collect recent public samples without scraping or image fetches

#### Scenario: Pause and provider backoff
- **WHEN** collection is paused or a provider returns 429
- **THEN** scheduled collection respects pause and shared provider-instance cooldown, and manual collection also respects cooldown

### Requirement: Inspectable trends and durable articles
The system SHALL show latest ranked posts, reaction counters, related hashtag counts, sample scope and recent run history, with likes + twice reposts + replies scoring within each provider. Articles and evidence SHALL reuse existing reader functionality.

#### Scenario: Repeated collection
- **WHEN** a topic is collected twice with overlapping posts and changed reactions
- **THEN** identities/read/star state remain stable, counters are snapshotted per run and newly discovered counts exclude existing articles

#### Scenario: Failed collection and retention
- **WHEN** a request fails or more than 30 successful runs exist
- **THEN** the last good snapshot survives failures and only the latest 30 runs with up to 40 rankings each are retained

### Requirement: Safe X retirement and migration
The system SHALL disable X collection without deleting historical articles or research state, reject X registration/re-enabling and preserve topic settings/history through restart and backup/restore.

#### Scenario: Existing X library
- **WHEN** a v14 database containing X articles is upgraded
- **THEN** X feeds are disabled, manual updates make no X requests, and saved articles, stars and foreign-key integrity remain intact

#### Scenario: Restore and restart
- **WHEN** a library containing topics and ranked runs is restored or the worker restarts
- **THEN** configuration, articles and snapshot history remain consistent and repeated collection does not duplicate articles
