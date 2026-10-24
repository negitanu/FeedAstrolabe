## Context

The operator explicitly chose Cloudflare-side login enforcement. Cloudflare documents Protect with Access as a supported alternative to origin-side JWT validation. The old configuration conflates Tunnel credentials with origin JWT configuration.

## Goals / Non-Goals

**Goals:** Only TUNNEL_TOKEN required locally; explicit tunnel mode; retain optional strict cloudflare mode and native local mode; preserve token isolation and application protections.

**Non-Goals:** Unauthenticated public deployment, provisioning Cloudflare policies, changing network/address allocation, changing API authorization or dependencies.

## Decisions

- Compose defaults web to tunnel mode via FEEDASTROLABE_ACCESS_MODE; Access team/AUD/hosts interpolate to empty optional values. Explicit cloudflare mode still validates all three at app startup; it never falls back to tunnel on invalid input.
- Tunnel mode sets Secure cookies and delegates allowed hostnames and JWT validation to Cloudflare's published route, Access policies and Protect with Access. It accepts routed Host headers without a local allowlist because the public hostname is managed remotely. Local mode retains its loopback allowlist; cloudflare mode retains its explicit hosts and JWT verification.
- Web publishes no host ports, has no host networking or elevated networking capability, and uses the private project bridge. Tunnel is the only public entry point. All routes, including API, must be covered by Cloudflare protection. Tunnel mode is not appropriate for direct publication or untrusted containers on the same bridge.
- Minimal .env.example contains only TUNNEL_TOKEN as an active required entry, with optional app-side JWT configuration commented. Preserve real local values; update explanations without printing credentials or deploying.
- UI reports delegated authentication accurately. Tests cover token-only Compose, real application creation with empty Access inputs, public Host headers, Secure cookie, CSRF and independent API key enforcement; existing cloudflare rejection tests remain.

## Risks / Trade-offs

- Missing remote Access policy would expose UI → state Access and Protect with Access prerequisites in README/deployment and external acceptance checks. This trust delegation was explicitly selected by the user; no live publication is performed.
- App cannot attest to remote policy correctness from its Tunnel token → report this verification boundary and require unauthenticated/unauthorized external checks before use.
- Optional strict mode may be selected accidentally → preserve fail-closed startup with clear missing configuration error.

## Migration Plan

Keep TUNNEL_TOKEN in .env. Default to tunnel unless the user explicitly selects cloudflare. Configure the public route to http://web:5000 with Access policy and Protect with Access in Cloudflare; local team/AUD/hosts are optional. Rebuild using the standard Compose command after configuration. Existing data volumes remain unchanged.
