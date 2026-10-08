## Context

Summaries and research answers should be traceable to captured evidence and respect nonpublic research boundaries.

Implementation prerequisite: `phase-seven-evidence-provenance`, `phase-nine-entities-relations`, `phase-twelve-ai-research-tracking`. Prerequisites are accepted and archived. Deployed schema11 migrates to schema12.

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

## Refreshed adapter and consent design

Use official Ollama Chat API, local127.0.0.1:11434 or fixed cloud https://ollama.com/api/chat. Both start disabled. No local runtime/model is installed on this host; real-model quality acceptance is explicitly unverified. Do not install models, create accounts or spend credits as part of acceptance. Local profile requires expected model SHA256 and preflight cloud.disabled=true plus matching local /api/tags digest and no remote_host/model; no cloud proxy model is treated as local. Trusted Docker deployment may explicitly configure local service hostname ollama via environment, never browser/API arbitrary endpoints.

Remote cloud token is read from an ignored owner-only regular credential file (or exact Docker secret mount) and never stored in DB, Git or request lineage. Remote profile records dated user-reviewed micro-USD-per-million input/output rates from official pricing, bounded monetary reserve, tokens and daily calls. Conservative UTF8 byte bound plus framing/output limit reserves the maximum planned charge; unknown rate blocks cloud. Response usage/cost is retained, estimated rather than billed. One global generation at a time, 90second total deadline, 1MiB response, no streaming/tools/thinking/search, no automatic retry of POST. Interrupted running job is failed, requiring new approval, because remote billing may already have occurred.

Preview snapshots exact wire JSON payload, hash, profile revision and up to8 evidence excerpts capped1200characters each, within8192input bytes plus conservative framing. Selection is bounded local literal retrieval in the requested workspace; explicit quoted offsets are validated against fixed hashes. Remote requires public workspace, all selected evidence untainted by internal/restricted workspace references, secret checks and explicit approved=true + input hash at queue time. Secret detection is defense in depth, not a guarantee; human exact input review is mandatory. Recheck classification/hash/profile immediately before generation; immutable preview expires30minutes. Model names/prompt are also untrusted strings.

Modes summary/translation/compare/QA use one fixed Japanese prompt template requiring structured answer status, supported statements with selected citation IDs, uncertainties and suggestions. Grounding validates IDs and exact quotation anchors, not semantic truth. No evidence produces deterministic insufficient result without model calls. Any unsupported/malformed citation rejects the generated result; human review appends separate immutable revisions. All generated claims remain unverified, never automatic facts. Output stays escaped plaintext/structured JSON.

Dispatch holds the existing evidence/SQLite writer transaction through the bounded generation to prevent concurrent classification/profile changes racing the approved POST. Other writes may wait or return busy while a model runs; foreground reads remain available. Budgets reserve at approval and again on a different execution UTC day, with no automatic refunds/retries after uncertain failures. Token rates are dated estimates, not provider invoice guarantees.
