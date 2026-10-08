## ADDED Requirements

### Requirement: Normalized mentions
The system SHALL retain normalized identifiers and source-linked original mentions while supporting reviewed aliases.

#### Scenario: Normalized mentions acceptance
- **WHEN** equivalent IPv6 spellings appear in two evidence records
- **THEN** one entity shows both original mentions and evidence links

### Requirement: Evidence-backed relations
The system SHALL store assertions with source anchors, assessment type/confidence and temporal metadata without inferring ownership from shared infrastructure.

#### Scenario: Evidence-backed relations acceptance
- **WHEN** two domains share an observed IP
- **THEN** the relation shows the observation and does not label their owners identical

### Requirement: Reversible exploration
The system SHALL support bounded graph/timeline views and audited entity merge/unmerge.

#### Scenario: Reversible exploration acceptance
- **WHEN** a mistaken alias merge is undone
- **THEN** the original entities and their evidence-backed mentions are restored
