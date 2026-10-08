## Context

Mutable feed entries and page baselines are insufficient for reproducible research and citations after upstream edits or subscription deletion.

Implementation prerequisite: `phase-six-research-workspaces`. This is a planned change; artifact readiness does not mean its prerequisites are implemented.

## Goals / Non-Goals

**Goals:**

- Create immutable captured representations with source URL, publisher, published/observed/captured times, hash and capture method.
- Pin quotations and source-claim annotations to an exact evidence version.
- Support bounded text/Markdown/PDF attachments and safe authenticated downloads.
- Back up/restore evidence blobs together with DB metadata and explicit retention controls.

**Non-Goals:**

Multi-user authorization, Cloudflare activation, live X setup, autonomous exploit execution, and unrelated UI polish. Existing credential files and read-only renderer isolation remain mandatory.

## Decisions

1. Capture feed-content or selected-page-text at ingestion as explicitly derived representations; do not claim full original HTML, retroactive collection or authentic truth. Retain separate immutable versions on change and SHA-256 of exact stored bytes.

2. Evidence records copy source identity/provenance; nullable original feed/article FKs use SET NULL. Evidence pinned to a workspace/note survives subscription deletion and ordinary page article retention. Unpinned items follow an explicit configurable retention policy.

3. Store blobs under private data volume by content hash; no source filenames as paths, symlinks or public static URLs. Enforce10MiB per attachment and configurable library quota (initial500MiB); MIME/magic validation and parsing in a bounded isolated worker. PDF is downloaded as attachment, never rendered as active HTML.

4. Maintain observed_at versus source-published_at and retrieval errors separately. Quotes reference evidence ID/hash/offset and are checked against stored text. Snapshot consistency uses backup manifests/blob hashes; partial restore must fail validation.

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
