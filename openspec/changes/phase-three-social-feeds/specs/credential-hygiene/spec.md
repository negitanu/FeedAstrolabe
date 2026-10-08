## ADDED Requirements

### Requirement: Confine provider authentication
The system SHALL load X authentication only from a configured read-only secret file, send it only to api.x.com over TLS, refuse redirects and omit tokens, provider bodies and raw exceptions from UI/API/log errors.

#### Scenario: Redirect or hostile error
- **WHEN** a provider redirects or returns an error containing secret text
- **THEN** the redirect is not followed and only a safe status error is retained

#### Scenario: Missing or unsafe file
- **WHEN** the token file is missing, a symlink or insecure native file
- **THEN** the source reports a safe configuration error and no authenticated request is made

### Requirement: Preserve network fetch bounds
SNS JSON requests SHALL enforce public-IP DNS pinning, TLS, response size and time limits and SHALL never follow provider pagination links as URLs.

#### Scenario: Private instance resolution
- **WHEN** a Mastodon origin resolves to a private address
- **THEN** the request is rejected before connection

### Requirement: Inspect before publication
Git publication SHALL exclude runtime data, credentials and local environment files and SHALL scan staged and historical blobs for common credential patterns without printing secret values.

#### Scenario: Credential in candidate content
- **WHEN** the scanner detects a private key or credential pattern
- **THEN** it exits unsuccessfully with only file/rule identifiers and push does not proceed
