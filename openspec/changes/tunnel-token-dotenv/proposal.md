## Why

The operator explicitly wants all required Tunnel deployment inputs in .env rather than a separate token file. The current Compose secret and instructions prevent that workflow.

## What Changes

- **BREAKING**: Replace the Tunnel token file setting with required TUNNEL_TOKEN in .env, passed only to cloudflared's environment.
- Remove the Tunnel secret mount and temporary verification token file; retain fail-closed configuration, Access validation and container isolation.
- Update operator input files, documentation and tests without displaying or replacing real credentials.

## Capabilities

### New Capabilities

### Modified Capabilities

- `local-operation`: Support a required dotenv Tunnel token without a separate credential file.

## Impact

compose.yml, .env.example, ignored local .env, Compose verification helper/tests, README and deployment/security documentation. No application code, dependency or live deployment changes.
