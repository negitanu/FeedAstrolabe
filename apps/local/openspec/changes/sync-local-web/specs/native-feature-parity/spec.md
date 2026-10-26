## ADDED Requirements

### Requirement: Native complete feature parity
The local app SHALL implement the Web application's reading, source observation, research/classification, evidence/provenance, watchlists/triage, entities/relations, security/network/AI intelligence, assistant, notifications, operations and scoped API capabilities in Go / Electron without requiring a Web connection or Python runtime.

#### Scenario: Independent feature execution
- **WHEN** synchronization is disabled and a user invokes a Web-equivalent feature
- **THEN** the local app provides the corresponding workflow and persists its results in its own library

### Requirement: Honest parity acceptance
The implementation SHALL map each original OpenSpec capability to native implementation and meaningful tests; incomplete and unverified external functionality SHALL remain explicitly pending.

#### Scenario: Release verification
- **WHEN** completion is evaluated
- **THEN** functional stubs, generic storage and mocked adapters alone do not count as full feature acceptance
