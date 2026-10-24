## ADDED Requirements

### Requirement: Explicit reader scopes
The system SHALL accept optional feed, article, workspace and tag selectors only as positive signed-64-bit database IDs. Missing or empty optional ID fields SHALL retain their existing unscoped behavior. Malformed, repeated, non-positive or oversized selectors SHALL return HTTP 400 before bulk state changes or collection. Reader conditions SHALL accept a single view from all/unread/starred and a single search term of at most 200 characters; invalid or repeated conditions SHALL return HTTP 400 without changing article states. A specified missing refresh target SHALL return HTTP 404.

#### Scenario: Invalid bulk-read scope
- **WHEN** a bulk-read form contains an invalid or repeated feed selector
- **THEN** HTTP 400 is returned and all read/star states remain unchanged

#### Scenario: Invalid refresh target
- **WHEN** a refresh form contains a malformed, zero, negative or oversized feed ID
- **THEN** HTTP 400 is returned and no feed is fetched or page job queued

#### Scenario: Valid and empty scopes
- **WHEN** a bulk-read or refresh form contains a valid feed ID or an empty selector
- **THEN** the valid ID targets only that feed and the empty selector retains the all-feeds behavior

#### Scenario: Invalid or ambiguous filter
- **WHEN** a bulk-read form contains an unsupported view, an oversized search term or repeated view/query/workspace/tag values
- **THEN** HTTP 400 is returned and all article states remain unchanged

#### Scenario: Missing refresh target
- **WHEN** a refresh form specifies a valid ID with no matching subscription
- **THEN** HTTP 404 is returned without fetching any feed

### Requirement: Bounded route identifiers
The system SHALL reject integer URL identifiers outside 1 through 9223372036854775807 with HTTP 400 before handler database access or side effects. Paths containing more than 19 ID digits SHALL fail routing with HTTP 404 before integer conversion, including arbitrarily long digit strings.

#### Scenario: Oversized identifier paths
- **WHEN** a UI or authenticated API request contains an oversized or zero database identifier
- **THEN** HTTP 400 is returned for numeric bounds errors or HTTP 404 for IDs longer than 19 digits and existing records remain unchanged
