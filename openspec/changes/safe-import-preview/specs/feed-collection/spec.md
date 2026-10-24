## ADDED Requirements

### Requirement: Reviewable subscription import
The UI SHALL preview OPML subscription titles, public URLs, folders and status before registration, preserving document order and distinguishing new subscriptions, existing URLs and duplicates within the file. Upload and cancellation SHALL NOT mutate subscriptions or fetch source URLs. Confirmation SHALL require a valid CSRF token and a signed, size-bounded plan bound to the initiating session with a 15-minute lifetime.

#### Scenario: Preview and cancel
- **WHEN** a user uploads a valid OPML file and returns to settings without confirming
- **THEN** the preview shows ordered entries and planned additions and no subscriptions have been registered

#### Scenario: Confirm amid library changes
- **WHEN** a user confirms a valid preview after another request registered one of its URLs
- **THEN** registration is atomic, that URL is skipped, other new URLs are registered and actual counts are reported

#### Scenario: Reject invalid confirmation
- **WHEN** a plan is modified, expired, oversized or submitted from a different session, or CSRF validation fails
- **THEN** confirmation is rejected before any subscription is written

#### Scenario: Authenticated API compatibility
- **WHEN** an authorized API client explicitly imports safe OPML
- **THEN** the existing one-step atomic import and added/skipped result remain available without fetching source URLs
