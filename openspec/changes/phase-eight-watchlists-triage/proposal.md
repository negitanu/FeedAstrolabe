## Why

Large mixed-topic feeds require repeatable triage and explanations for why an item is relevant.

## What Changes

- Add per-workspace saved searches and watchlists for products, organizations, topics and identifiers.
- Apply bounded include/exclude rules and explainable priority labels without deleting collected source records.
- Group exact duplicates while retaining distinct provenance and read/star state.
- Add durable in-app matching events and daily digest view, with reprocessing and idempotency.

## Capabilities

### New Capabilities

- `watchlists-triage`: ウォッチリスト・保存検索・整理.

### Modified Capabilities

None. Additive capabilities preserve existing RSS/SNS/page and API contracts.

## Impact

Flask/SQLite persistence, Japanese responsive UI, scoped APIs, background jobs and operations documentation. Planned only: no runtime behavior changes in this planning delivery. Dependencies: `phase-six-research-workspaces`, `phase-seven-evidence-provenance`.
