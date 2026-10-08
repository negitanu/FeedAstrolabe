## Context

Articles and subscriptions are stored in one library, but research goals, questions and conclusions cannot be organized alongside them.

Implementation prerequisite: implemented phases one to five (schema v4). Prerequisites verified: deployed schema v4; phases one to five are implemented. This change upgrades to schema v5.

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

## Implementation contract refinement

- Schema v5 adds only tables/indexes; old source/article IDs, flags and renderer isolation remain intact. Restore accepts v1-v5 and upgrades old backups.
- A workspace article view is the distinct union of direct article links and current/future articles from associated feeds. Removing a direct link does not hide an article still included through a feed. Archive retains these live associations; immutable evidence capture is phase seven.
- Archive allows only a PATCH containing `archived:false` to reopen. All workspace associations, note edits and note archive changes reject archived parents with409. Global article read/star and global tag rename remain shared-library operations.
- Notes have title (1-120), body (0-100000), label (`fact`, `source-claim`, `hypothesis`, default hypothesis), archived boolean and revision starting at1. PATCH requires positive integer expected_revision plus at least one changed field; archival is the reversible delete operation. Each successful mutation records a full immutable revision, including archive state. No hard DELETE for workspaces/notes.
- Purpose/questions bounds are10000 characters each; title/tag strings trim and reject control characters; Markdown preserves newlines. Status active/paused/completed; classification public/internal/restricted default internal. No external sending is implemented.
- Association routes POST/DELETE `/workspaces/{id}/feeds/{feed_id}`, `/workspaces/{id}/articles/{article_id}`, and `/workspaces/{id}/tags/{tag_id}`; `/articles/{id}/tags/{tag_id}` and `/notes/{id}/tags/{tag_id}` for shared tags. Links are idempotent and changes atomic. GET workspace feeds/articles are paginated.
- GET/POST `/tags`, GET/PATCH `/tags/{id}` (name only); names use SQLite NOCASE uniqueness (ASCII case insensitive; other Unicode exact matching). GET workspace notes and GET note revisions use the same limit/before_id/after_id convention as articles (revision history cursors use revision numbers). GET `/articles?workspace={id}&tag={id}` uses EXISTS without duplicate rows. Workspace/tag IDs must exist.
- List workspaces/notes hide archived records by default, with archived=true/false query parameters; detail remains readable. UI pages bound size to30 and validate page identifiers. Note editor on conflict returns409 and preserves the submitted text for recovery.
- Markdown3.11 is pinned (https://pypi.org/project/Markdown/); escape user HTML before conversion then Bleach allowlists structural tags and http/https links. Images are omitted; no script or remote image rendering.

- Tag associations are bounded to100 per workspace/article/note; duplicate link retries remain successful at the bound. UI filters retain a selected older ID within the100 options.
