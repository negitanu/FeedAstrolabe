## ADDED Requirements

### Requirement: SNS and AI recovery
The system SHALL migrate schema1 to schema2 with a pre-migration backup, export and restore SNS/AI lineage without secrets, accept legacy backup1, and disable generation and fail unfinished jobs on restore.

#### Scenario: Recover library
- **WHEN** a backup with enabled AI and queued work is restored
- **THEN** configuration and history remain while AI is disabled and work is not replayed
