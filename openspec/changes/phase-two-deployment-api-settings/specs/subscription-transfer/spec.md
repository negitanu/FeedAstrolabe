## ADDED Requirements

### Requirement: OPML transfer
The system SHALL import and export folders and public HTTP(S) feed URLs via OPML. Import SHALL reject XML entities, oversized files, more than 100 feeds or invalid URLs without partial registration, skip duplicates and defer network collection to the worker.

#### Scenario: Round trip
- **WHEN** an exported OPML is imported into an empty library
- **THEN** feed URLs and folders are restored and can be fetched by the worker

#### Scenario: Unsafe input
- **WHEN** an OPML contains external entities, private-address URLs or an invalid URL
- **THEN** import fails and no subscriptions are added
