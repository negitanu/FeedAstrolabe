## Why

OSINT/network investigations need historical observations of public infrastructure instead of a single current lookup.

## What Changes

- Add read-only public domain/IP/ASN observations using DNS, RDAP, certificate transparency and RIPEstat routing/RPKI data.
- Preserve dated responses, normalized records and field-level change events.
- Join network observations to entities/workspaces and explain uncertainty and coverage.
- Offer manual lookup and scheduled watchlists with provider budgets and retention.

## Capabilities

### New Capabilities

- `network-intelligence`: DNS・証明書・経路の観測.

### Modified Capabilities

None. Additive capabilities preserve existing RSS/SNS/page and API contracts.

## Impact

Flask/SQLite persistence, Japanese responsive UI, scoped APIs, background jobs and operations documentation. Planned only: no runtime behavior changes in this planning delivery. Dependencies: `phase-nine-entities-relations`, `phase-ten-security-intelligence`.
