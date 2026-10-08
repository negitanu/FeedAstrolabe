## Context

Investigations need to follow identifiers and evidence-backed relationships across many source documents.

Implementation prerequisite: `phase-seven-evidence-provenance`, `phase-eight-watchlists-triage`. This is a planned change; artifact readiness does not mean its prerequisites are implemented.

## Goals / Non-Goals

**Goals:**

- Extract and normalize CVE, domain, IP, ASN, hash and repository identifiers; manually maintain organization/product/model aliases.
- Add source-linked mentions and entity detail pages with cross-workspace filtering.
- Record evidence-backed relationship assertions, corrections and temporal validity.
- Provide a bounded graph view and timeline; support merge/unmerge without losing provenance.

**Non-Goals:**

Multi-user authorization, Cloudflare activation, live X setup, autonomous exploit execution, and unrelated UI polish. Existing credential files and read-only renderer isolation remain mandatory.

## Decisions

1. Start deterministic extraction; preserve original spelling and normalization version. Canonicalize domain IDNA/case, IP textual forms and identifier formats without DNS lookups. Do not auto-merge organizations/products/models solely by name.

2. Store assertions with evidence/quote, recorded_at, observed_at, optional valid_from/valid_to, author, fact/source-claim/hypothesis and unknown/low/medium/high confidence. Confidence is asserted assessment, not calibrated probability.

3. Shared IP/certificate is an observed relation, never proof of ownership or attacker attribution. Manual merge/unmerge records audit events and retains original IDs/aliases.

4. Default graph depth2 and maximum200 visible nodes with pagination beyond; list/timeline is available on narrow screens. Only evidenced records enter the graph; inferred links are clearly marked and separately reviewable.

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
