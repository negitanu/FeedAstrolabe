## Context

Mutable feed entries and page baselines are insufficient for reproducible research and citations after upstream edits or subscription deletion.

Implementation prerequisite: `phase-six-research-workspaces`. Verified implemented prerequisite: schema v5 research workspaces (archived 2026-10-08). This change upgrades to v6.

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


## Concrete implementation contract

- Schema v6: evidence immutable metadata/text records, blobs keyed by SHA-256, workspace/note evidence pins and exact quotations. Source FKs SET NULL; copy publisher/source identity, publication/capture/observation timestamps. Methods feed-derived, page-selected-text, article-backfill-now and attachment-text/markdown/pdf. Title/publisher/method are distinct provenance; hashes prove byte consistency only.
- Capture feed/SNS representations after upsert, page-selected text including initial baseline, and explicitly capture existing articles on demand. Content-identical retries reuse the same source version; content changes including reverting create new versions. Stored text max160000 characters; feed capture over bounds/quota records a separate bounded capture error while ordinary collection survives. No retroactive capture during migration.
- Quota default500MiB, attachment max10MiB, extracted text max100000 characters, retention default90 days for unpinned evidence; configurable via UI/write API. Pins and quotes prevent retention deletion. Explicit retention CLI never deletes pinned records.
- Use network-isolated renderer IPC for text/Markdown/PDF parsing in per-job fork with CPU15s, memory384MiB and hard wall45s (native renderer is process isolation only; address-space bound is Linux-only, Docker is required for the verified network/filesystem/memory boundary). pypdf6.19.0 (https://pypi.org/project/pypdf/) pinned; encrypted PDF rejected, max200 pages, decompressed content per page4MiB, no OCR/scripts/actions/embedded-file execution. MIME/extension/magic and UTF-8 checks mandatory; extraction failure does not publish evidence. Web gains IPC mount, renderer retains no DB or credentials and network_mode:none.
- GET /evidence, /evidence/{id}, /evidence/{id}/download; POST /articles/{id}/evidence (backfill-now), POST /workspaces/{id}/attachments multipart file. POST/DELETE /workspaces/{id}/evidence/{eid} and /notes/{id}/evidence/{eid}; POST /workspaces/{id}/quotations with evidence_id,start,end,quote and optional note_id. Anchors use Unicode code-point offsets and exact text/hash; quotations immutable and pinned. Existing bearer scopes/CSRF and archived parent checks apply. Bounded cursor lists; JSON objects reject unknown fields.
- UI evidence list/detail, workspace pins/upload/quote forms and article capture action. Download Content-Disposition attachment + application/octet-stream, filename sanitized; authenticated API download and UI same current access policy, never static URLs.
- Content-addressed private blob store with symlink refusal, atomic writes and hash verification. All evidence writes/pin/retention/backup/restore serialize under evidence.lock plus SQLite transactions; no externally supplied storage paths.
- Bundle backup is explicit `backup-bundle`/`restore-bundle` (directory, DB + manifest + blobs). Lock writers, validate every referenced size/hash and foreign keys, staged restore with rollback, refuse missing/extraneous/path-traversal/symlink blobs before replacing any live DB. Legacy DB-only backup/restore remains for v1-v5 and evidence-free v6; refuse evidence-bearing DB-only backup/restore with a clear bundle requirement. Rollback to prior image uses pre-phase-seven v5 backup.
