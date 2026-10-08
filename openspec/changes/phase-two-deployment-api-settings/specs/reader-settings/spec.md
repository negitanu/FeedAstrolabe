## ADDED Requirements

### Requirement: Persistent reader preferences
The system SHALL validate and persist global polling interval (60–86400 seconds), collection pause, API rate (1–1000/minute), page size (10–100) and initial view. Invalid settings SHALL leave the prior settings unchanged.

#### Scenario: Save and restart
- **WHEN** preferences are saved and Web/worker restart
- **THEN** the saved preferences remain effective

### Requirement: Per-feed scheduling
The system SHALL support per-feed pause and interval overrides, refresh only due enabled feeds automatically, back off after failures, and observe changed settings on the next idle scheduler tick (10 seconds), allowing an in-progress fetch to finish. Manual explicit refresh SHALL remain available when paused.

#### Scenario: Due and paused feeds
- **WHEN** the scheduler runs with due, future and paused subscriptions
- **THEN** it fetches only due enabled subscriptions unless globally paused

#### Scenario: Failure backoff
- **WHEN** a scheduled feed fetch repeatedly fails
- **THEN** its next attempt is delayed exponentially up to 24 hours, and success resets failures
