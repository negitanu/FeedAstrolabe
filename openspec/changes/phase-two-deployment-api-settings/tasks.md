## 1. Persistence and settings

- [x] 1.1 Add transactional version2 migration and consistent backup/restore tooling.
- [x] 1.2 Implement global and per-feed settings UI and validation.
- [x] 1.3 Implement due scheduling, pause and exponential error backoff.

## 2. API and subscription transfer

- [x] 2.1 Implement hashed scoped expiring keys, issuance/revocation UI and atomic rate limiting.
- [x] 2.2 Implement feed/article JSON endpoints, cursor pagination and state/subscription mutations with API documentation.
- [x] 2.3 Implement safe OPML import/export and round-trip verification.

## 3. Deployment

- [x] 3.1 Implement fail-closed Cloudflare Access verification, trusted hosts and secure cookies.
- [x] 3.2 Add non-root Dockerfile, Web/worker Compose, local/cloudflare overrides, secrets and healthchecks.
- [x] 3.3 Build and run containers, verify restart persistence and backup restoration locally.

## 4. Verification and delivery

- [x] 4.1 Test migration, scheduling, key lifecycle, API permission/pagination/rate limit, OPML and Access JWT rejection.
- [x] 4.2 Validate OpenSpec, inspect settings UI, document deployment/API and commit source.
- [ ] 4.3 Configure real Cloudflare domain/Tunnel/Access and verify permitted/denied external requests after required operator settings are supplied.

Operator decision (2026-10-08): task 4.3 is explicitly deferred until after subsequent implementation phases.
