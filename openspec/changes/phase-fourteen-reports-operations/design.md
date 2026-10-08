## Context

The research workspace needs portable sourced outputs and reliable operations with controlled external delivery.

Implementation prerequisite: `phase-eight-watchlists-triage`, `phase-eleven-network-intelligence`, `phase-twelve-ai-research-tracking`. All prerequisites and phase thirteen are archived and deployed at schema12. This change uses additive schema13.

## Goals / Non-Goals

**Goals:**

- Export sourced workspace Markdown reports, citation manifests and entity/observation JSON/CSV; add a documented STIX2.1 subset after compatibility validation.
- Add previewed optional email/webhook delivery with classification/recipient allowlists and retry/idempotency controls.
- Add worker heartbeat/job-history dashboards, periodic backups, retention and validated offline restore tooling.
- Enable CI when repository workflow permission is available; extend settings/bulk-state/OPML APIs with existing scope/rate protections.

**Non-Goals:**

Multi-user authorization, Cloudflare activation, live X setup, autonomous exploit execution, and unrelated UI polish. Existing credential files and read-only renderer isolation remain mandatory.

## Decisions

1. Exports explicitly select workspace/content/classification; include evidence IDs/hashes and capture times. Never include credentials or restricted records by default. CSV protects formula injection. Define STIX export mapping/limitations with fixtures; do not claim universal STIX/TAXII interoperability.

2. External delivery is opt-in with recipient/endpoint allowlists, previewed payloads, signed webhook option and bounded retry queue. SMTP/webhook secrets are ignored files; use public pinned HTTP for webhooks. Changing a delivery configuration does not itself send historical data.

3. Record safe worker heartbeat/start/end/count/error-code metrics and stale thresholds without article bodies/query credentials. Backups include evidence manifests/blobs and DB consistency with bounded generations; restore requires paused Web/workers and verified archive. Restore UI initially generates offline instructions, not an in-process database replacement.

4. Bulk APIs are bounded (initial100 IDs), atomic where specified, with write scope and per-record errors for partial workflows. Key issuance remains UI-only until a separate delegated-scope design; cannot silently broaden existing keys. CI activation requires current GitHub workflow permission, tracked as an external setup gate.

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

## Refreshed implementation contract (2026-10-08)

- Reports are immutable local snapshots, max100 fixed evidence/20000 chars each and4MiB total, explicit IDs or newest100 pinned records. Public is default; including internal/restricted requires explicit local flag. Shared nonpublic references are excluded from public output. Notes/observations only follow selected evidence. No credential or API-key tables export. Known secret markers fail closed. STIX2.1 subset domain/IP/ASN/CVE plus a sourced note; unsupported entity kinds remain in JSON/CSV, no invented indicator/relationship/TAXII.
- Profiles max20, disabled initially, exact HTTPS443 endpoint without query/fragment/auth or exact email recipient. Ignored owner-only regular credential file selected by operator; webhook secret signs exact UTF-8 JSON payload, SMTP uses pinned TLS465. Preview immutable hash/profile revision with30min expiry; explicit approval creates one durable job. Successful deliveries are never repeated. Max3 attempts, retry only explicit429/503 responses; ambiguous timeout/interruption/SMTP outcome stops for manual investigation, no automatic replay. Receiver must honor stable Idempotency-Key. Remote dispatch rechecks classification/secret/profile under evidence and DB locks.
- Web and worker app lifetimes hold a shared runtime.lock; both restore paths require exclusive lock before replacing any live data. Backups take consistent existing DB/blob bundle, validate it, cap2GiB generation and total quota, keep1..30 validated generations with safe-path checks. Schedule disabled initially, interval1h..7d. Online UI/API only schedules backups or presents offline instructions, never replaces DB. Worker loop start/end metrics and safe error codes, stale10min, history newest100; CLI one-shot jobs retain history.
- Settings PATCH validates complete merged values atomically; bulk state1..100 unique positive IDs validates all before atomic mutation. OPML1MiB/max100 insertion-only atomic import (no inline fetching; regular RSS worker later resolves with public-address checks), returns added/skipped; export excludes non-RSS. CI template stays inactive while current GitHub OAuth lacks workflow permission. No permission expansion, recipient activation or real notifications during acceptance.
