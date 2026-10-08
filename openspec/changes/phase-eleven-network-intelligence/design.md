## Context

OSINT/network investigations need historical observations of public infrastructure instead of a single current lookup.

Implementation prerequisite: `phase-nine-entities-relations`, `phase-ten-security-intelligence`. This is a planned change; artifact readiness does not mean its prerequisites are implemented.

## Goals / Non-Goals

**Goals:**

- Add read-only public domain/IP/ASN observations using DNS, RDAP, certificate transparency and RIPEstat routing/RPKI data.
- Preserve dated responses, normalized records and field-level change events.
- Join network observations to entities/workspaces and explain uncertainty and coverage.
- Offer manual lookup and scheduled watchlists with provider budgets and retention.

**Non-Goals:**

Multi-user authorization, Cloudflare activation, live X setup, autonomous exploit execution, and unrelated UI polish. Existing credential files and read-only renderer isolation remain mandatory.

## Decisions

1. Reuse the connector contract and identifier outbound policy. Implement providers in order: public DNS/RDAP, RIPEstat routing/RPKI, CT metadata. Review referral/redirect endpoints before allowlisting; do not accept arbitrary URLs from provider payloads.

2. Store TTL/time queried, source timestamp, scope and raw/normalized representation. Missing RRsets/provider coverage are explicit unknown or observed absence, never authoritative global absence. Separate certificate issuance from observed serving endpoints.

3. RPKI status is computed/reported for a specific prefix/origin at a timestamp. Origin changes/shared hosting are events, not automatic hijack or ownership conclusions.

4. Use passive public data; no port scanning, private address probing, mass crawling or router/ROA writes. Per-watchlist frequency, call ceiling and retention are configurable; direct TLS verification is a separate future feature.

Keep Flask/SQLite and small bounded background jobs because current deployment/backup isolation is verified; defer a separate DB/search cluster until measured limits justify it. Prefer additive tables/APIs over repurposing article flags or source identity, preserving existing clients.

## Risks / Trade-offs

- Source records and external APIs change → immutable attributed versions, explicit unknown/stale states, current contract review and retry-safe fixtures.
- Research data may be nonpublic → classification and explicit outbound policy; no secrets in logs/build/Git and no automatic external sending. Classification alone is not per-user access isolation.
- Migrations and file retention may lose research → verified backups, transactional migrations, pinned evidence rules, deletion/rollback tests.
- Scope may expand → deliver listed capability first; refresh this design before implementation if dependencies or contracts change.

## Migration Plan

Before implementing, confirm prerequisite changes and deployed schema, assign the next transactional schema version only if needed, and update maintenance/restore compatibility. Back up DB and any evidence blobs, stop relevant writers for migration, verify existing feed/article IDs and read/star state, then test container recreation. Rollback uses a compatible prior image and pre-change backup.

## Open Questions

Connector/model endpoint quotas, licenses, model runtime choice and required credential files are resolved in the listed research/configuration tasks before enabling that integration. Missing external configuration is reported as unverified, never converted to a successful acceptance check. Initial bounds are design defaults and can be revised with explicit specification updates.
