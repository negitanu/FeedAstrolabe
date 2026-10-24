## ADDED Requirements

### Requirement: Explicit bounded OpenRouter configuration
The system SHALL accept an explicit model and per-call/day token, price and call limits, start disabled, and use a runtime `.env` credential without exposing it in DB, UI, API or logs.

#### Scenario: Optional setup
- **WHEN** an operator configures a model and enables OpenRouter
- **THEN** generation becomes available without requiring additional services or credential files

#### Scenario: Missing credential or invalid settings
- **WHEN** credentials, model, revisions or limits are invalid
- **THEN** configuration or dispatch is rejected without a paid request or partial settings update

### Requirement: Grounded important-topic extraction
The system SHALL analyze at most 20 bounded public source snapshots and return at most five Japanese topics with importance, summary, explanation, uncertainty and valid source article references.

#### Scenario: Successful extraction
- **WHEN** the worker receives a valid structured result for a saved sample
- **THEN** the UI/API show importance-sorted topics with source links, model, sample time and an unverified label

#### Scenario: Untrusted input or output
- **WHEN** a source contains instructions or the response invents citations, invokes tools or violates the schema
- **THEN** no tool is executed, invalid results are rejected and existing articles and prior successful analysis remain unchanged

### Requirement: Public scope and controlled dispatch
The system SHALL exclude private-case-related sources, recheck source policy before dispatch, enforce price/token/day limits and share provider cooldowns without automatic POST retries.

#### Scenario: Classification changes before execution
- **WHEN** selected source material becomes associated with a nonpublic case after enqueue
- **THEN** dispatch fails without sending the snapshot

#### Scenario: Budget or rate limit
- **WHEN** a daily reservation would exceed limits or OpenRouter returns 429
- **THEN** no over-budget request is sent and other queued requests honor the shared retry time

### Requirement: Durable manual and automatic jobs
The system SHALL support CSRF-protected UI and scoped API manual queueing plus opt-in extraction of new collection runs, persist idempotent jobs and preserve last-good results on failure.

#### Scenario: Repeated scheduling and restart
- **WHEN** the worker schedules the same run/settings repeatedly or restarts during generation
- **THEN** no duplicate paid request occurs and interrupted running jobs are marked failed

#### Scenario: Restore and retention
- **WHEN** a library is restored or a social run expires from its 30-run history
- **THEN** saved analysis remains consistent with retained runs, restored automatic generation is disabled and unfinished jobs are not dispatched

#### Scenario: Unauthorized mutation
- **WHEN** a read-scoped key or a request without CSRF attempts to queue or configure extraction
- **THEN** the request is rejected and GET requests never generate or queue analyses
