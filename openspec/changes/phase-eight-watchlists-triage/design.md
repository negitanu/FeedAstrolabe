## Context

Large mixed-topic feeds require repeatable triage and explanations for why an item is relevant.

Implementation prerequisite: `phase-six-research-workspaces`, `phase-seven-evidence-provenance`. This is a planned change; artifact readiness does not mean its prerequisites are implemented.

## Goals / Non-Goals

**Goals:**

- Add per-workspace saved searches and watchlists for products, organizations, topics and identifiers.
- Apply bounded include/exclude rules and explainable priority labels without deleting collected source records.
- Group exact duplicates while retaining distinct provenance and read/star state.
- Add durable in-app matching events and daily digest view, with reprocessing and idempotency.

**Non-Goals:**

Multi-user authorization, Cloudflare activation, live X setup, autonomous exploit execution, and unrelated UI polish. Existing credential files and read-only renderer isolation remain mandatory.

## Decisions

1. Use a validated query AST for text/source/tag/workspace/date filters. No user SQL or arbitrary regular expressions. Cap query terms40 and input length2000; index or FTS5 only after runtime capability checks.

2. Match on new/changed evidence using versioned rules and unique (rule_version,evidence_version) keys. Archived workspaces pause automatic matches. Reprocessing is explicit and never reissues duplicate events.

3. Deduplicate exact canonical public URL/content hashes; ignore only a defined set of tracking parameters, preserving meaningful queries. Grouping never deletes sources or automatically merges similar claims; near-duplicate suggestions await human review.

4. Priority is a deterministic rule result with matched fields and reason. Notification MVP is an in-app event/digest; external delivery is deferred to the outbound-policy/operations stage.

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
