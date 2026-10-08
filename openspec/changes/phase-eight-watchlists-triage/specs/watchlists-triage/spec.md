## ADDED Requirements

### Requirement: Repeatable triage
The system SHALL persist workspace saved searches and bounded include/exclude/priority rules with matching explanations.

#### Scenario: Repeatable triage acceptance
- **WHEN** an article matches a product rule and an exclusion rule
- **THEN** the displayed triage result explains both and retains the original article

### Requirement: Idempotent matching
The system SHALL create durable in-app watch events once per rule/evidence version and allow explicit reprocessing.

#### Scenario: Idempotent matching acceptance
- **WHEN** a worker retries the same evidence version
- **THEN** no duplicate watch event or digest item is created

### Requirement: Provenance-preserving groups
The system SHALL group exact duplicates while preserving their sources, evidence and read/star state.

#### Scenario: Provenance-preserving groups acceptance
- **WHEN** two publishers provide identical content
- **THEN** the group exposes both sources without removing either record
