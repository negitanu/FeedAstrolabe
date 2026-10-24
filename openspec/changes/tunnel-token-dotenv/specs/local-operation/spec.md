## ADDED Requirements

### Requirement: Dotenv Tunnel credential
The deployment SHALL accept a required TUNNEL_TOKEN from .env without requiring a separate token file. Only the tunnel container SHALL receive the token, through cloudflared's supported environment variable. The token SHALL NOT be interpolated into command arguments or sent to application containers or builds. Missing or empty tokens SHALL cause configuration validation to fail. Operator instructions SHALL describe the dotenv entry and quiet validation. Isolated verification SHALL use a synthetic token without launching tunnel or using the operator's credential.

#### Scenario: Load dotenv input
- **WHEN** .env contains the Access settings and a Tunnel token
- **THEN** Compose resolves with the token in tunnel's environment and no Tunnel token file or secret mount

#### Scenario: Reject missing credential
- **WHEN** TUNNEL_TOKEN is absent or empty
- **THEN** Compose rejects configuration before startup

#### Scenario: Bound token scope
- **WHEN** Compose resolves a configured deployment
- **THEN** web, worker, observer and renderer do not receive TUNNEL_TOKEN and command arguments do not contain its value

#### Scenario: Verify without operator token
- **WHEN** the isolated acceptance configuration is resolved with an operator token in the parent environment
- **THEN** tunnel remains disabled and only a synthetic unused token is used
