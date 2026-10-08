## ADDED Requirements

### Requirement: Configure public observations
The system SHALL accept a public HTTP(S) target, CSS selector,0-10000ms settling time,60-86400s polling interval and1-365d retention through CSRF-protected UI and write-scoped API, without fetching at registration.

#### Scenario: Separate selectors
- **WHEN** two observations use the same target and different selectors
- **THEN** both can be registered, while identical target/selector is rejected

### Requirement: Baseline and change events
The system SHALL store the first normalized text as baseline without an article, and SHALL create an escaped diff article only when normalized text changes, preserving repeated transitions and read/star states.

#### Scenario: Unchanged whitespace
- **WHEN** only normalized Unicode/whitespace changes
- **THEN** no additional article is created

#### Scenario: Reverting content
- **WHEN** content changes A to B to A
- **THEN** two distinct events remain in the common UI/API

### Requirement: Dedicated durable scheduling
The system SHALL queue manual page refreshes uniquely and collect due pages in a separate single-worker lock, respecting pause/backoff and rejecting stale configuration results.

#### Scenario: Missing selector
- **WHEN** the selector disappears or rendering times out
- **THEN** an actionable safe error appears and the prior baseline/articles remain

#### Scenario: Edited during capture
- **WHEN** configuration changes during rendering
- **THEN** the old result does not overwrite the new baseline

### Requirement: Retain observation history
The system SHALL apply configured retention to unstarred page articles while preserving starred articles and the current baseline; RSS/SNS history SHALL be unaffected.

#### Scenario: Expired starred event
- **WHEN** retention pruning runs
- **THEN** expired unstarred page events are removed but starred and RSS/SNS events survive
