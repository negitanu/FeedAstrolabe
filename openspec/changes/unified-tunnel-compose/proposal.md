## Why

Cloudflared Tunnel is now the standard deployment path, but starting the application requires combining several Compose files. Consolidating them removes ambiguous startup combinations and makes the network and authentication boundaries visible in one place.

## What Changes

- **BREAKING**: Replace the base and six overlay files with one `compose.yml`, discovered by ordinary `docker compose` commands.
- Start web, worker, observer, renderer and tunnel together; require Cloudflare Access configuration for the web service and retain no published host ports.
- Preserve bridge networking, renderer network isolation, existing volume/project names, resource limits and container hardening.
- Configure optional X/Ollama/delivery credential paths through `.env`, using owner-only files in the private application volume so unused integrations need no extra credential files or Compose overlays.
- Update operational instructions, restore/backup commands and isolated acceptance scripts to the single deployment file.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `local-operation`: Add a single Tunnel-first Compose deployment contract and safe isolated verification.

## Impact

Compose files, `.env.example`, deployment/integration documentation and container acceptance scripts/tests. Native development behavior, database schema, API contracts and existing named-volume identity remain unchanged. Running production services will not be restarted by this change.
