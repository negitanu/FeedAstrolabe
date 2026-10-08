## Context

Summaries and research answers should be traceable to captured evidence and respect nonpublic research boundaries.

Implementation prerequisite: `phase-seven-evidence-provenance`, `phase-nine-entities-relations`, `phase-twelve-ai-research-tracking`. This is a planned change; artifact readiness does not mean its prerequisites are implemented.

## Goals / Non-Goals

**Goals:**

- Provide opt-in Japanese summary/translation, cross-document comparison and workspace question answering.
- Cite immutable evidence/quote anchors and distinguish supported facts, uncertainty and suggestions.
- Record model/prompt/input/result lineage, cost/token budgets and reviewed status.
- Support explicit local or approved remote model profiles without autonomous external actions.

**Non-Goals:**

Multi-user authorization, Cloudflare activation, live X setup, autonomous exploit execution, and unrelated UI polish. Existing credential files and read-only renderer isolation remain mandatory.

## Decisions

1. Keep provider choice undecided until official runtime/API/privacy/price review at implementation. AI is off by default; local/remote profile, data classification and outbound identifier/text policy are explicit. Remote requests preview exact selected excerpts; secrets/restricted content are blocked by default.

2. Use deterministic retrieval over scoped evidence initially; embeddings/vector DB are optional follow-up after evaluated need. Store retrieval chunks by evidence hash and validate citation IDs/offsets. Never retrieve across the requested workspace accidentally.

3. Evidence text is untrusted data. No shell, browser, arbitrary URL fetch or configuration-write tools for the model. Outputs are sanitized, grounded claims marked as generated; ungrounded questions produce insufficient evidence instead of fabricated references.

4. Bound selected documents/context/output/concurrency/time and per-run/daily budget. Record model/version, prompt-template hash, input evidence IDs/hashes, usage and output for reproducibility. Human edits/review are independent revisions, never silently replace evidence.

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
