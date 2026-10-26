## ADDED Requirements

### Requirement: Safe feed collection
The system SHALL discover, preview and collect RSS/Atom from public HTTP(S) URLs with bounded downloads and reject private IPs, unsafe redirects, DTD and oversized responses.

#### Scenario: Collect and refresh
- **WHEN** a valid feed is subscribed and refreshed again
- **THEN** articles are deduplicated and read/star states retained

#### Scenario: Failed collection
- **WHEN** a refresh fails
- **THEN** old articles are retained and the error is visible

### Requirement: Persistent source organization
The system SHALL persist folders, feed membership, order, pause state and sidebar presentation; folder selection SHALL show its articles and expansion SHALL require its arrow.

#### Scenario: Pause and resume
- **WHEN** a source is paused then resumed
- **THEN** saved articles remain and collection resumes

#### Scenario: Move source
- **WHEN** a source is moved between folders and the app restarts
- **THEN** its membership and ordering are retained

### Requirement: Reader state and search
The system SHALL support unread, starred, history, folder/feed, literal text, any/excluded terms, date range and publication/history ordering with progressive loading and a stable detail panel.

#### Scenario: Mark all matching
- **WHEN** the user marks all matching articles read
- **THEN** unrendered matching articles are also marked

#### Scenario: Open detail
- **WHEN** the user opens an article and then closes it
- **THEN** read state and history are saved and list position is retained

#### Scenario: Selected updates
- **WHEN** the user selects multiple articles and changes their state
- **THEN** only the selected IDs change atomically

### Requirement: OPML interchange
The system SHALL preview OPML before confirmation, skip duplicate URLs, preserve folder grouping and export subscriptions.

#### Scenario: Import duplicates
- **WHEN** an OPML contains existing and repeated sources
- **THEN** the preview reports duplicates and confirmation adds each new source once

### Requirement: Explicit TLS compatibility mode
The system SHALL retain the Go default maximum TLS version by default and SHALL offer an explicit TLS 1.2 compatibility option for networks that reject newer handshakes, without disabling certificate verification or public-IP protections.

#### Scenario: Compatibility collection
- **WHEN** the user explicitly starts with FEEDASTROLABE_LOCAL_TLS12=1 on a network requiring TLS 1.2
- **THEN** collection uses TLS 1.2 with normal hostname, certificate and URL validation
