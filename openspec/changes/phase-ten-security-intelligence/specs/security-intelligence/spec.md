## ADDED Requirements

### Requirement: Attributed vulnerability cards
The system SHALL display dated KEV/EPSS/severity/remediation observations with source/version and stale/unknown states.

#### Scenario: Attributed vulnerability cards acceptance
- **WHEN** EPSS retrieval fails after a successful prior observation
- **THEN** the prior score remains visible as stale and missing data is not shown as zero

### Requirement: Qualified applicability
The system SHALL label watched product/version applicability as confirmed, possible or unknown with supporting evidence.

#### Scenario: Qualified applicability acceptance
- **WHEN** only a product name matches an advisory
- **THEN** the result is possible or unknown rather than a confirmed affected asset

### Requirement: Bounded connectors
The system SHALL enforce provider endpoint/input/rate/credential policies and record provenance for read-only enrichment.

#### Scenario: Bounded connectors acceptance
- **WHEN** a provider is rate-limited or returns a private redirect
- **THEN** the job waits or fails safely without bypassing limits or leaking credentials
