## ADDED Requirements

### Requirement: Minimal remotely protected Tunnel deployment
Default Compose deployment SHALL require only TUNNEL_TOKEN in .env and SHALL use tunnel access mode, delegating allowed public hostnames and Access JWT validation to Cloudflare Access and cloudflared Protect with Access. Tunnel mode SHALL accept routed public Host headers and set Secure session cookies while retaining CSRF and API Bearer authentication. Origin ports SHALL remain unpublished and renderer SHALL remain network-isolated. Documentation SHALL require remote Access policy and Protect with Access before publication and describe independent external acceptance checks. Native local mode and explicitly selected strict cloudflare mode SHALL retain their existing protections.

#### Scenario: Token-only configuration
- **WHEN** .env contains only a nonempty TUNNEL_TOKEN
- **THEN** Compose resolves and web starts in tunnel mode without team domain, AUD or public hostname settings

#### Scenario: Delegated public request
- **WHEN** a public Host request reaches tunnel mode after Cloudflare validation
- **THEN** the UI can respond without local Access inputs, session cookies are Secure, POSTs require CSRF and API requests require a scoped API key

#### Scenario: Explicit strict validation
- **WHEN** cloudflare mode is explicitly selected with incomplete Access inputs
- **THEN** application startup rejects configuration without silently changing authentication mode

#### Scenario: Verify remote boundary
- **WHEN** an operator follows deployment acceptance instructions
- **THEN** unauthenticated and unauthorized public requests are checked for rejection and local tests are not represented as proof of remote policy correctness
