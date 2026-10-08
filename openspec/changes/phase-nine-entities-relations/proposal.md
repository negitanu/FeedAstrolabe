## Why

Investigations need to follow identifiers and evidence-backed relationships across many source documents.

## What Changes

- Extract and normalize CVE, domain, IP, ASN, hash and repository identifiers; manually maintain organization/product/model aliases.
- Add source-linked mentions and entity detail pages with cross-workspace filtering.
- Record evidence-backed relationship assertions, corrections and temporal validity.
- Provide a bounded graph view and timeline; support merge/unmerge without losing provenance.

## Capabilities

### New Capabilities

- `entities-relations`: 対象抽出・関係・タイムライン.

### Modified Capabilities

None. Additive capabilities preserve existing RSS/SNS/page and API contracts.

## Impact

Flask/SQLite persistence, Japanese responsive UI, scoped APIs, background jobs and operations documentation. Planned only: no runtime behavior changes in this planning delivery. Dependencies: `phase-seven-evidence-provenance`, `phase-eight-watchlists-triage`.
