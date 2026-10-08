## ADDED Requirements

### Requirement: Portable sourced outputs
The system SHALL export selected research records with citation/evidence manifests and classification filtering, protecting CSV and explicit STIX mapping.

#### Scenario: Portable sourced outputs acceptance
- **WHEN** a report contains restricted evidence and a CSV cell begins with a formula marker
- **THEN** restricted data is excluded by default and the cell is safely encoded

### Requirement: Controlled notification delivery
The system SHALL preview opt-in outgoing payloads, validate recipients/endpoints and retry durable notifications without duplicate successful sends.

#### Scenario: Controlled notification delivery acceptance
- **WHEN** a webhook job is retried after completion
- **THEN** the completed delivery is not sent again and its audit record remains

### Requirement: Recoverable operations
The system SHALL show safe worker/job health, create consistent bounded-generation backups and reject incomplete or online restore.

#### Scenario: Recoverable operations acceptance
- **WHEN** a backup lacks a referenced evidence blob or workers are active during restore
- **THEN** restore fails without replacing the live library

### Requirement: Bounded management APIs
The system SHALL provide documented scoped settings/bulk-state/OPML operations with safe limits and record CI setup separately.

#### Scenario: Bounded management APIs acceptance
- **WHEN** a bulk article-state request exceeds its limit or uses a read key
- **THEN** it is rejected without changing articles
