## Context

AI research needs traceable connections between papers, model versions, code releases, licenses and evaluation conditions.

Implementation prerequisite: `phase-nine-entities-relations`, `phase-ten-security-intelligence`. This is a planned change; artifact readiness does not mean its prerequisites are implemented.

## Goals / Non-Goals

**Goals:**

- Add arXiv query/version and GitHub release connectors with incremental collection.
- Link papers, repositories, model cards and model versions through reviewed references.
- Store attributed licenses, use constraints, hardware/context claims and benchmark conditions.
- Record user reproduction notes/results separately from vendor or paper claims.

**Non-Goals:**

Multi-user authorization, Cloudflare activation, live X setup, autonomous exploit execution, and unrelated UI polish. Existing credential files and read-only renderer isolation remain mandatory.

## Decisions

1. Use official APIs with current rate/license review, version-aware IDs and explicit cursors. GitHub token remains an optional ignored credential file; initially observe releases, not clone/execute repositories or download model weights.

2. Paper versions and model/release versions are separate immutable records. Links require explicit URLs/identifiers or manual review, never name similarity alone.

3. Card fields are sourced facts/claims with captured date; absent licenses/costs/hardware are unknown. Pricing claims need currency/unit/date and source, with no automatic spending.

4. Benchmark records include dataset/version/split, metric direction/unit, harness/settings and result provenance. Comparisons flag incompatible conditions and distinguish claimed/reproduced/unverified status.

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
