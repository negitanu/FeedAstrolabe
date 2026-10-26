# local-data Specification

## Purpose

FeedAstrolabe-local 0.1.0 の local-data に関する現行契約。Go / Electron の独立したローカル実装を定義する。元版との差分は docs/parity.md を参照。

## Requirements

### Requirement: Durable private storage
The system SHALL store library data separately from the Python application and persist state across restarts.

#### Scenario: Restart
- **WHEN** the app restarts with the same data directory
- **THEN** the articles, states, sources and cases are restored

### Requirement: Settings and recovery
The system SHALL export versioned settings without article/research bodies, and a distinct complete backup with validated transactional restoration and an automatic pre-restore backup.

#### Scenario: Invalid backup
- **WHEN** a malformed or unsupported backup is supplied
- **THEN** the current library remains unchanged

#### Scenario: Complete recovery
- **WHEN** a valid complete backup is restored
- **THEN** library relationships, states and evidence are recovered

### Requirement: SNS and AI recovery
The system SHALL migrate schema1 to schema2 with a pre-migration backup, export and restore SNS/AI lineage without secrets, accept legacy backup1, and disable generation and fail unfinished jobs on restore.

#### Scenario: Recover library
- **WHEN** a backup with enabled AI and queued work is restored
- **THEN** configuration and history remain while AI is disabled and work is not replayed
