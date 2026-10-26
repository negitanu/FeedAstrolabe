# library-sync Specification

## Purpose

Optional durable Web/native synchronization while preserving standalone use.

## Requirements

### Requirement: Standalone and optional synchronization
The local app SHALL start and collect/read/research without a Web connection; synchronization SHALL default to disabled and disabling SHALL retain all local data and pending changes.

#### Scenario: Offline use
- **WHEN** synchronization is disabled or Web is unreachable
- **THEN** local reading and collection continue and failed synchronization does not delete data

### Requirement: Bidirectional durable library changes
The applications SHALL synchronize subscriptions, article content, independent read/star/subscription-enabled states and collection enabled/paused and last collection results using stable identities, durable events, tombstones and bounded batches.

#### Scenario: Offline state changes and retry
- **WHEN** either side changes read or star while offline and a response is lost during reconnection
- **THEN** retry converges without duplicate articles, lost pending events or unrelated state overwrite

#### Scenario: Delete and collection
- **WHEN** a subscription is paused or deleted and synchronization completes
- **THEN** pause retains articles while deletion propagates and stale events do not resurrect deleted data

### Requirement: Safe synchronization transport
The synchronization endpoint SHALL use existing Cloudflare Access/Entra protection without new application authentication, reject cross-origin writes, validate all events before atomic application, and keep local IPC isolated.

#### Scenario: Invalid or unauthenticated response
- **WHEN** a response is HTML, redirected, incompatible, malformed or oversized
- **THEN** local pending changes and cursors remain unchanged and the UI reports failure

### Requirement: Migration and recovery
Both applications SHALL preserve existing state and create a consistent backup before synchronization schema migration. Replaying events SHALL be idempotent and clock conflicts SHALL resolve deterministically.

#### Scenario: Existing library migration
- **WHEN** an existing database first enables the new schema
- **THEN** a recoverable backup exists and article state and order remain intact

### Requirement: Clear sync activation and connection diagnostics
The local app SHALL keep the synchronization checkbox beside its label, explain that it enables synchronization while running, and distinguish authentication failure, missing server API and network failures before uploading library changes.

#### Scenario: Checkbox layout and save
- **WHEN** the user opens synchronization settings in any theme or a narrow window
- **THEN** the checkbox and its activation label are adjacent and disabling then saving stops synchronization

#### Scenario: Old server or Access login
- **WHEN** the configured server lacks the sync route or Access redirects a read-only readiness request
- **THEN** the app displays respectively a server update instruction or an Access sign-in instruction without uploading pending events or advancing cursors
