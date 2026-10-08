## ADDED Requirements

### Requirement: Temporal network observations
The system SHALL preserve attributed time-specific DNS/RDAP/CT/routing/RPKI records and field changes.

#### Scenario: Temporal network observations acceptance
- **WHEN** a watched domain DNS answer changes
- **THEN** both observations and a sourced change event remain available

### Requirement: Uncertainty-aware interpretation
The system SHALL distinguish missing coverage, observed absence, certificate issuance and confirmed endpoint facts.

#### Scenario: Uncertainty-aware interpretation acceptance
- **WHEN** CT reports a certificate containing a domain name
- **THEN** the UI records issuance without claiming the domain is actively serving that certificate

### Requirement: Passive bounded monitoring
The system SHALL use opted-in public identifiers with read-only allowlisted providers and budgeted schedules.

#### Scenario: Passive bounded monitoring acceptance
- **WHEN** a lookup requests a private target or an unapproved referral endpoint
- **THEN** the request is rejected before accessing it
