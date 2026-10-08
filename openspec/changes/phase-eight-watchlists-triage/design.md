## Context

Large mixed-topic feeds require repeatable triage and explanations for why an item is relevant.

Implementation prerequisite: `phase-six-research-workspaces`, `phase-seven-evidence-provenance`. Both prerequisites are implemented, accepted and archived; deployed schema is v6.

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

## Implementation contract (2026-10-08)

Schema v7 adds workspace watchlists (kind saved-search/watchlist), immutable rule revisions, per-revision evidence cursor, durable included/excluded matches, exact duplicate fingerprints/groups and a bounded scan cursor. Evidence IDs become AUTOINCREMENT to prevent retention from reusing a processed ID. No article flags are repurposed.

A query is a shallow JSON AST with all/any/none arrays of predicates {field,op,value}. Maximum total40 predicates across include and exclusion, serialized JSON2000 characters each, value200 characters. Fields: title/text/publisher/url/source_type/tag/published_at/captured_at. Text uses literal Unicode casefold contains/eq; date uses eq/gte/lte with real UTC timestamps; source_type and tag use eq. No SQL or regex is compiled from user input. Query evaluation uses indexed ID ranges and workspace associations (direct article, linked feed, pinned evidence/note or quotation). Mutable tags and new associations require explicit reprocessing of existing evidence.

At most100 lists per workspace,20 current enabled lists per worker tick ordered by oldest processing time,100 evidence records per list,100 duplicate fingerprint records. Automatic processing pauses archived workspaces; explicit reprocessing also refuses archived parents and resets the cursor while preserving unique revision/evidence matches. Rule changes require expected_revision and create a new revision/cursor. Preview is read-only, bounded and reports its cursor.

Inclusion and exclusion are evaluated independently. Exclusion wins but both matching predicate explanations are retained. Empty exclusion disables exclusion. Priority low/normal/high/critical and a human reason (500 characters) are deterministic rule metadata. Inbox lists all verdicts with per-event seen state; digest for a real UTC date lists included matches, with no external delivery. Match events keep their evidence via restrictive FK and are retention pins until a future explicit event-retention feature.

Duplicates use nonempty exact text SHA-256 or a canonical HTTP(S) URL. Canonicalization removes only utm_* (case-insensitive), fbclid and gclid, drops fragments and sorts remaining query pairs preserving duplicates and blank values. A URL match is labelled same URL and is not asserted to be same text. Two distinct source identities are required; revisions of one source alone do not create a group. Fingerprints retain every evidence version. Group undo is durable suppression; worker retries do not restore suppressed groups, and explicit redo is available. Evidence/source/read/star records are untouched. No fuzzy duplicate matching is implemented.

All processing is transactional under evidence.lock then SQLite; events/groups retain evidence through FK RESTRICT, and blob-aware backup accepts v6/v7 while restore upgrades to v7. Worker polls the triage task after collection and an explicit triage --once command is available. No FTS dependency or external calls are introduced.
