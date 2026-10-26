## ADDED Requirements

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
