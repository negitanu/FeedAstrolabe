## ADDED Requirements

### Requirement: Bounded external XML parsing
The system SHALL reject DTDs, declared entities, external references and malformed XML before feedparser or OPML registration. Feed XML SHALL be limited to 5 MiB, 100,000 elements and depth 64. OPML SHALL be limited to 1 MiB, 10,000 elements and depth 64. Parser rejection SHALL use safe errors without exposing source XML or external identifiers and SHALL preserve existing subscriptions, articles and reading state.

#### Scenario: Declared entity in feed
- **WHEN** a feed supplies a DTD declaring an internal or external entity, including in a supported non-UTF-8 encoding
- **THEN** it is rejected before feedparser and no entity is expanded or external resource accessed

#### Scenario: Excessive or malformed XML
- **WHEN** input exceeds a byte, depth or element limit or is not well-formed XML
- **THEN** processing stops with a safe error before registration or ingestion

#### Scenario: Safe XML compatibility
- **WHEN** valid RSS/Atom or OPML uses namespaces, supported encodings or built-in/numeric XML references
- **THEN** it is processed within the limits without changing existing read/star state
