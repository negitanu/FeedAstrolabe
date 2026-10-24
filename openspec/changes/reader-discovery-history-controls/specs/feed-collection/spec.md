## ADDED Requirements

### Requirement: Safe website discovery and subscription preview
The system SHALL accept an HTTP(S) site or RSS/Atom URL in 集める, reuse bounded public-address-validated fetching, and discover at most eight deduplicated RSS/Atom alternate links against the final redirect URL. Candidate previews SHALL show a validated title, source URL and up to five latest articles before explicit subscription confirmation. Preview and discovery SHALL NOT register feeds or articles. Confirmation SHALL require CSRF and a session-bound signed plan expiring after fifteen minutes, revalidate/refetch the feed and preserve duplicate subscriptions.

#### Scenario: Website with multiple feeds
- **WHEN** a site declares multiple relative or absolute RSS/Atom alternate links
- **THEN** candidates can be compared and individually previewed without creating a subscription

#### Scenario: Confirm direct feed
- **WHEN** a direct valid RSS/Atom URL is previewed and explicitly confirmed
- **THEN** exactly one subscription and initial articles are stored in the selected folder

#### Scenario: Unsafe unavailable or stale input
- **WHEN** a candidate redirects to a private address, is invalid, has no alternate feed, exceeds bounds, or a plan is modified, expired or used in another session
- **THEN** a helpful error is shown without registration or read/star changes
