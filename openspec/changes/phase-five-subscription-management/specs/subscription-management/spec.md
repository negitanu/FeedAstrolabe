## ADDED Requirements

### Requirement: Atomic partial subscription edits
The system SHALL provide write-scoped PATCH /api/v1/feeds/{id} for folder, enabled and nullable poll_interval, plus RSS/page URL and page selector,settle_ms,retention_days. It SHALL reject unsupported fields, invalid types, private/credential URLs, duplicates and missing IDs without partial mutation.

#### Scenario: Invalid mixed patch
- **WHEN** a valid folder is patched together with an invalid interval
- **THEN**400 is returned and the original configuration remains unchanged

#### Scenario: Read-only client
- **WHEN** a read-scoped key attempts an edit or delete
- **THEN**403 is returned and no subscription is changed

### Requirement: Preserve state when repairing targets
URL repairs SHALL retain subscription and article IDs/read/star states, clear RSS conditional validators, and reset page baselines for URL/selector/wait changes while retaining history and sequence. Stale in-flight page results SHALL be discarded.

#### Scenario: RSS URL repair
- **WHEN** an RSS URL changes
- **THEN** the next fetch is unconditional and old articles and flags remain

#### Scenario: Page metadata edit
- **WHEN** only folder or retention changes
- **THEN** baseline remains and no artificial change event is generated

#### Scenario: Page target edited during capture
- **WHEN** URL changes while its old page capture is in progress
- **THEN** the old result cannot restore its baseline

### Requirement: Delete subscriptions safely
Write-scoped DELETE /api/v1/feeds/{id} SHALL return204 and cascade its articles and manual jobs. UI deletion and API deletion SHALL serialize with RSS/SNS collection; missing IDs SHALL return404 and active collection SHALL return409 for API mutations.

#### Scenario: Delete queued page
- **WHEN** a queued page subscription is deleted
- **THEN** its job and history disappear and an old capture cannot recreate them

### Requirement: Common manual refresh API
POST /api/v1/feeds/{id}/refresh SHALL require write scope, return202 for uniquely queued pages and200 with counts/status for synchronous RSS/SNS collection. Provider cooldown SHALL return429 with Retry-After, missing IDs404 and active collection409.

#### Scenario: Paused page refresh
- **WHEN** a paused page is manually refreshed twice
- **THEN**202 is returned and exactly one durable reservation remains

#### Scenario: Provider cooldown
- **WHEN** X or Mastodon is in a provider cooldown
- **THEN**429 reports when retrying is allowed without contacting the provider

### Requirement: Shared UI management
CSRF-protected UI SHALL expose RSS/page URL repair and use shared validation for schedule and page settings.

#### Scenario: UI repair
- **WHEN** a valid repair is submitted from settings
- **THEN** the URL changes and existing article states are retained
