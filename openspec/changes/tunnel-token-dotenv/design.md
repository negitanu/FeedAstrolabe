## Context

Compose currently mounts a file-backed Tunnel secret. The user requests .env as the only input location for the Tunnel token. Cloudflared officially supports TUNNEL_TOKEN.

## Goals / Non-Goals

**Goals:** Required dotenv token, no token file, only tunnel receives the value, preserve operator entries and isolated verification.

**Non-Goals:** Changes to other integration credentials, Access authentication, network allocation, live deployment or token provisioning.

## Decisions

- Pass required ${TUNNEL_TOKEN:?Set Tunnel token in .env} as the tunnel service's explicit TUNNEL_TOKEN environment. Remove --token-file and Compose secrets. Avoid env_file injection into all services and token interpolation in command arguments.
- Include an empty TUNNEL_TOKEN in .env.example and add it to the ignored local .env without replacing operator values. Keep local .env at mode 0600 and excluded from Git/build context.
- Verification overrides inherited tokens with a synthetic unused fixture and disables tunnel. Remove its temporary dummy token file. Test dotenv loading using temporary synthetic inputs, missing/empty rejection and absence from other services.

## Risks / Trade-offs

- Environment values are visible to Docker administrators and unredacted compose config output → document config --quiet for validation and keep the token out of command arguments, logs and build context. This is the user's chosen storage mode.
- Operator inputs could be overwritten → edit only configuration comments/legacy path directives and add an empty token key only when absent; never print real values.

## Migration Plan

Set TUNNEL_TOKEN in .env and remove the old FEEDASTROLABE_TUNNEL_TOKEN_FILE directive. Validate quietly then recreate using the documented Compose command. No separate token file is needed. No live services are started as part of implementation.
