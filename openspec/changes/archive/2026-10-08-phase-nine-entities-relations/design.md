## Context

Investigations need to follow identifiers and evidence-backed relationships across many source documents.

Implementation prerequisite: `phase-seven-evidence-provenance`, `phase-eight-watchlists-triage`. Both prerequisites are implemented, accepted and archived; deployed schema is v7.

## Goals / Non-Goals

**Goals:**

- Extract and normalize CVE, domain, IP, ASN, hash and repository identifiers; manually maintain organization/product/model aliases.
- Add source-linked mentions and entity detail pages with cross-workspace filtering.
- Record evidence-backed relationship assertions, corrections and temporal validity.
- Provide a bounded graph view and timeline; support merge/unmerge without losing provenance.

**Non-Goals:**

Multi-user authorization, Cloudflare activation, live X setup, autonomous exploit execution, and unrelated UI polish. Existing credential files and read-only renderer isolation remain mandatory.

## Decisions

1. Start deterministic extraction; preserve original spelling and normalization version. Canonicalize domain IDNA/case, IP textual forms and identifier formats without DNS lookups. Do not auto-merge organizations/products/models solely by name.

2. Store assertions with evidence/quote, recorded_at, observed_at, optional valid_from/valid_to, author, fact/source-claim/hypothesis and unknown/low/medium/high confidence. Confidence is asserted assessment, not calibrated probability.

3. Shared IP/certificate is an observed relation, never proof of ownership or attacker attribution. Manual merge/unmerge records audit events and retains original IDs/aliases.

4. Default graph depth2 and maximum200 visible nodes with pagination beyond; list/timeline is available on narrow screens. Only evidenced records enter the graph; inferred links are clearly marked and separately reviewable.

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

Schema v8 adds entities, reviewed aliases, immutable original mention anchors with versioned correction/audit, quoted relation revisions and audit/entity associations plus extraction cursors. Stable evidence IDs from v7 are reused. Evidence referenced by mentions/assertions/audit is retained. v6/v7/v8 bundle validation and upgrade remain supported.

Identifier kinds cve/domain/ip/asn/hash/repository share a unique normalized identity. Organization/product/model are manual records with opaque identities, allowing homonymous names to remain separate. Normalization rules-v1 uses strict syntactic CVE prefix/year/4+sequence digits (bounded32 sequence digits, no claim of registration), Python ipaddress compressed IP without zone suffixes, AS decimal0..4294967295 (including reserved identifiers without asserting allocation), lowercase32/40/64 hex without claiming an algorithm, nontransitional IDNA2008/UTS46 domain labels with idna3.20 and lowercase GitHub owner/repo identity. Domain normalization is explicitly IDNA2008 with nontransitional UTS46 and STD3 rules; original spelling is always retained. No DNS, API or file downloads occur. References reviewed: Python ipaddress docs, idna package/Unicode UTS46 specifications, CVE syntax guidance, IANA ASN registry, GitHub repository REST parameters.

Extraction scans only fixed evidence.text, never HTML or source instructions. At most20 evidence records per batch and500 mentions per evidence, candidates are unreviewed. Only bounded fixed regexes are used; normalization validates every candidate and offsets/hash/bytes are checked. A per-evidence extraction marker is retry-safe. Explicit reprocessing retries a fixed evidence version, leaves reviewed/rejected/corrected mentions intact and preserves idempotency. Manual mentions require exact fixed-text range and expected_revision for corrections. Original entity/spelling/anchor are immutable; current entity and candidate/confirmed/rejected assessment can change with audit.

Aliases are explicit reviewed metadata, at most100 per entity,200 characters, and the same alias may describe multiple different entities. Aliases are not used to infer identity or automatically extract name mentions. Merge/unmerge requires write scope, reason, reviewer attribution, expected_revision and same kind. Merge sets a root pointer without rewriting any original mention, relation, alias or ID. Roots only may merge; cycles and chains beyond20 are rejected. Unmerge clears only the selected source pointer and records audit. Name similarity never triggers a merge. Shared IP or certificate never causes ownership/attacker inference.

Relations are workspace-scoped human assertions with source/target entities, predicate80 characters, quotation_id from that workspace, fact/source-claim/hypothesis, unknown/low/medium/high confidence, asserted author100 characters, recorded_at, optional UTC observed_at and valid_from/valid_to. A quotation is mandatory and verified. Edits create immutable revisions with expected_revision; archive is reversible. All input is validated before transaction mutations. Confidence and author are human assertions, not calibrated probability or verified login identity.

Entity search/list/detail/mentions and audit timeline accept workspace filtering through evidence associations or workspace relation/audit records. Lists use bounded cursor pagination; search escapes literal percent/underscore. Graph defaultsdepth2/max200nodes and caps400edges; only current nonarchived quoted assertions enter. Original endpoints remain visible with merge targets and source anchors. Dense or merged-family exploration signals truncation and offers paginated relation/timeline views, never falsely claiming all results were shown. Narrow-screen UI uses SVG plus readable relation/timeline lists, with no external graph library or scripts.

Writes and background extraction use evidence.lock then BEGIN IMMEDIATE. RSS worker invokes extraction after triage; an explicit extract-entities single-batch command is available. Nothing is sent to third-party services. Update rollback uses pre-v8 bundle with prior image, and all existing IDs/state are compared after migration.

Normalization dependency review: idna3.20 (BSD-3-Clause, Python>=3.9) is pinned in native and production locks. Nontransitional mapping preserves the distinction between faß.de and fass.de; using the standard-library IDNA2003 codec would lose this identity distinction. No live v8 entity data exists before this implementation delivery.
