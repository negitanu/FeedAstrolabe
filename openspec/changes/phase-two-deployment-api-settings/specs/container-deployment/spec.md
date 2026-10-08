## ADDED Requirements

### Requirement: Durable container runtime
The system SHALL provide non-root Web and worker containers with a shared persistent volume, healthcheck and an explicit localhost-only override. The default Compose configuration SHALL NOT publish origin ports. A backup CLI SHALL produce a consistent SQLite snapshot.

#### Scenario: Restart and restore
- **WHEN** containers are recreated using the same volume or a database backup is restored
- **THEN** subscriptions and read/star state remain intact

### Requirement: Access-protected origin
Cloudflare mode SHALL verify Access RS256 signature, issuer, audience, expiry and issued-at using the configured team JWKS before serving UI or API content. Invalid/missing tokens and key retrieval failure SHALL deny access. Production cookies SHALL be secure and accepted Host values explicit.

#### Scenario: JWT authentication
- **WHEN** an expired, forged, wrong-audience or missing Access JWT is submitted
- **THEN** the origin denies the request even if an application API key is supplied

#### Scenario: Public deployment
- **WHEN** an operator configures the real domain, Tunnel and Access policies
- **THEN** permitted users can access the application and other users cannot, without direct origin exposure
