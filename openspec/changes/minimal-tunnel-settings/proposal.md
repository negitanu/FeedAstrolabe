## Why

Compose currently requires app-side Access JWT configuration even when the operator only needs a remotely managed Tunnel. The user explicitly selected Cloudflare-side Access and Protect with Access, with only the Tunnel token required in .env.

## What Changes

- Default Compose web access to a new tunnel mode that delegates hostname authorization and JWT validation to Cloudflare Access/cloudflared.
- Require only TUNNEL_TOKEN in .env; retain explicit cloudflare mode for optional app-side JWT verification.
- Preserve Secure cookies, API Bearer authentication, CSRF, no published origin ports and renderer isolation.
- Simplify dotenv and deployment instructions, state the Cloudflare protection prerequisites, and test both modes.

## Capabilities

### New Capabilities

### Modified Capabilities

- `local-operation`: Minimal token-only Tunnel configuration with explicitly delegated authentication.

## Impact

Compose, access configuration, settings UI status, dotenv inputs, docs, verification helper and tests. No dependency/schema changes or live publication.
