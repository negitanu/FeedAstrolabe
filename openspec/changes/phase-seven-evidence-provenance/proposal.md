## Why

Mutable feed entries and page baselines are insufficient for reproducible research and citations after upstream edits or subscription deletion.

## What Changes

- Create immutable captured representations with source URL, publisher, published/observed/captured times, hash and capture method.
- Pin quotations and source-claim annotations to an exact evidence version.
- Support bounded text/Markdown/PDF attachments and safe authenticated downloads.
- Back up/restore evidence blobs together with DB metadata and explicit retention controls.

## Capabilities

### New Capabilities

- `evidence-provenance`: 根拠保存・出典管理.

### Modified Capabilities

None. Additive capabilities preserve existing RSS/SNS/page and API contracts.

## Impact

Flask/SQLite persistence, Japanese responsive UI, scoped APIs, background jobs and operations documentation. Planned only: no runtime behavior changes in this planning delivery. Dependencies: `phase-six-research-workspaces`.
