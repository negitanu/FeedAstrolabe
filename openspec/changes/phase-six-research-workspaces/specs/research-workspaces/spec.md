## ADDED Requirements

### Requirement: Research organization
The system SHALL create, edit, archive and list workspaces, with explicit purpose/questions/status and many-to-many feed/article associations.

#### Scenario: Research organization acceptance
- **WHEN** an article is linked to two workspaces and one workspace is archived
- **THEN** the article/read/star state and the other association survive

### Requirement: Versioned notes
The system SHALL store revisioned notes with fact/source-claim/hypothesis labels and reject stale writes atomically.

#### Scenario: Versioned notes acceptance
- **WHEN** two clients edit the same note revision
- **THEN** the first edit succeeds and the second returns409 without overwriting it

### Requirement: Scoped workspace access
The system SHALL offer paginated UI/API operations with input bounds, write scope and CSRF for UI mutations, and explicit outbound classification.

#### Scenario: Scoped workspace access acceptance
- **WHEN** a read-only key attempts to modify a workspace or note
- **THEN** 403 is returned and stored state is unchanged
