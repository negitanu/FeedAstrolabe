## Why

AI research needs traceable connections between papers, model versions, code releases, licenses and evaluation conditions.

## What Changes

- Add arXiv query/version and GitHub release connectors with incremental collection.
- Link papers, repositories, model cards and model versions through reviewed references.
- Store attributed licenses, use constraints, hardware/context claims and benchmark conditions.
- Record user reproduction notes/results separately from vendor or paper claims.

## Capabilities

### New Capabilities

- `ai-research-tracking`: 生成 AI の論文・モデル・実装追跡.

### Modified Capabilities

None. Additive capabilities preserve existing RSS/SNS/page and API contracts.

## Impact

Flask/SQLite persistence, Japanese responsive UI, scoped APIs, background jobs and operations documentation. Prerequisite stages nine and ten are accepted; deployed schema10 will migrate transactionally to schema11. Dependencies: `phase-nine-entities-relations`, `phase-ten-security-intelligence`.
