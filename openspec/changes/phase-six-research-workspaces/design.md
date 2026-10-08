## Context

Articles and subscriptions are stored in one library, but research goals, questions and conclusions cannot be organized alongside them.

Implementation prerequisite: implemented phases one to five (schema v4). This is a planned change; artifact readiness does not mean its prerequisites are implemented.

## Goals / Non-Goals

**Goals:**

- Add research workspaces with purpose, questions, status and archive state.
- Associate existing subscriptions/articles with multiple workspaces without duplicating or deleting them.
- Add versioned Markdown notes, fact/source-claim/hypothesis labels and shared tags.
- Expose Japanese responsive UI and scoped paginated APIs; define public/internal/restricted outbound classification.

**Non-Goals:**

Multi-user authorization, Cloudflare activation, live X setup, autonomous exploit execution, and unrelated UI polish. Existing credential files and read-only renderer isolation remain mandatory.

## Decisions

1. Keep a single-user shared library. Workspace is organizational scope, not a per-user authorization boundary; every currently authorized user/key retains library access.

2. Add workspaces, workspace_feeds, workspace_articles, notes, note_revisions, tags and association tables in a transactional migration from v4. Article links cascade; workspace archive never deletes feeds or articles.

3. Notes use optimistic revision checks (expected_revision); conflicts return409. Render sanitized Markdown without raw HTML, scripts or remote images. API writes keep existing write scope/CSRF separation.

4. Bound titles to120 characters, note bodies to100000 characters and API pages to100 records; validate archive/status/classification enums. New workspaces default internal; classification controls future outbound operations, not encryption or user isolation.

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

## Initial UI/API Contract

- UI: workspace list/detail, article association action, note editor/history and tags; existing library remains the default landing view.
- GET/POST /api/v1/workspaces; GET/PATCH /api/v1/workspaces/{id} for title,purpose,questions,status,archived,classification. Status values: active,paused,completed; archive is separate from completed.
- Workspace article/feed association POST/DELETE operations validate existing IDs and never change source ownership. Archived workspaces retain readable content, reject ordinary edits until unarchived, and remain explicitly queryable.
- GET/POST /api/v1/workspaces/{id}/notes and GET/PATCH /api/v1/notes/{id}; PATCH requires expected_revision, label and Markdown body with atomic validation. Note revision history is immutable and authenticated.
- Tags use a bounded name (1-80 characters), explicit rename and workspace/article/note association. Paginated list filters use validated workspace/tag IDs and the existing cursor convention.
- Scope baseline: API reads require read or write keys; all mutations require write keys. UI POST requires CSRF. No mass deletion in this phase; archives are reversible.
