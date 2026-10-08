## Context

AI research needs traceable connections between papers, model versions, code releases, licenses and evaluation conditions.

Implementation prerequisite: `phase-nine-entities-relations`, `phase-ten-security-intelligence`. Prerequisites are implemented and archived. Current deployment is schema10; this change uses schema11.

## Goals / Non-Goals

**Goals:**

- Add arXiv query/version and GitHub release connectors with incremental collection.
- Link papers, repositories, model cards and model versions through reviewed references.
- Store attributed licenses, use constraints, hardware/context claims and benchmark conditions.
- Record user reproduction notes/results separately from vendor or paper claims.

**Non-Goals:**

Multi-user authorization, Cloudflare activation, live X setup, autonomous exploit execution, and unrelated UI polish. Existing credential files and read-only renderer isolation remain mandatory.

## Decisions

1. Use official APIs with current rate/license review, version-aware IDs and explicit cursors. GitHub token remains an optional ignored credential file; initially observe releases, not clone/execute repositories or download model weights.

2. Paper versions and model/release versions are separate immutable records. Links require explicit URLs/identifiers or manual review, never name similarity alone.

3. Card fields are sourced facts/claims with captured date; absent licenses/costs/hardware are unknown. Pricing claims need currency/unit/date and source, with no automatic spending.

4. Benchmark records include dataset/version/split, metric direction/unit, harness/settings and result provenance. Comparisons flag incompatible conditions and distinguish claimed/reproduced/unverified status.

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

## Refreshed implementation bounds

Use unauthenticated GitHub release API (official version 2026-03-10) and arXiv Atom metadata only. Credentials are unnecessary for this public-only phase and not added. Registered inputs: arXiv id (new/legacy optional vN) or one of cs.AI/cs.CL/cs.LG/cs.CV/stat.ML with an optional literal title term; GitHub normalized owner/repository. No arbitrary query expressions. Serialized query includes a bounded page 0..19 with 50 results. Resume the same page until validated cache records and cursor commit atomically; repeat from page0 each polling cycle and deduplicate immutable version+projection hash. Observe latest paper revisions returned by search, not a guarantee of all intervening revisions. Dynamic pagination can shift; retain scope and a 1000-record cycle cap rather than claim exhaustive coverage.

Existing sequential global connector lock and minimum60s/provider exceed arXiv's single-request/3-second minimum and bound unauthenticated GitHub's60/hour. Existing daily100 budget/cache/retry apply. GitHub403 rate-limit-reset and429 preserve prior data. arXiv Atom parsing uses existing defusedxml with bounded bytes/nodes/entries; no entity expansion or PDF/asset retrieval. Metadata license and paper/code/model licenses are separate; unknown source fields remain unknown.

Append-only model card versions and manually reviewed paper/repository/model-card links require same-case fixed quotations. Benchmarks keep dataset/version/split, metric/unit/direction, harness/settings, hardware/context and author provenance. Claimed entries require quotation; user reproductions require notes and remain user-reported. Compare conditions exactly, missing fields qualify and differing fields are incompatible. No automatic ranking, spending, execution or inference from name similarity. API/UI search filters and triage use captured fixed projections. Up to100watches/case,1000cards/case,100links/card,1000benchmarks/card,10000versions/watch.
