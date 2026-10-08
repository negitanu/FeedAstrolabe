## Why

Articles and subscriptions are stored in one library, but research goals, questions and conclusions cannot be organized alongside them.

## What Changes

- Add research workspaces with purpose, questions, status and archive state.
- Associate existing subscriptions/articles with multiple workspaces without duplicating or deleting them.
- Add versioned Markdown notes, fact/source-claim/hypothesis labels and shared tags.
- Expose Japanese responsive UI and scoped paginated APIs; define public/internal/restricted outbound classification.

## Capabilities

### New Capabilities

- `research-workspaces`: 調査案件・メモの基盤.

### Modified Capabilities

None. Additive capabilities preserve existing RSS/SNS/page and API contracts.

## Impact

Flask/SQLite persistence, Japanese responsive UI, scoped APIs, background jobs and operations documentation. Planned only: no runtime behavior changes in this planning delivery. Dependencies: existing phases one to five.
