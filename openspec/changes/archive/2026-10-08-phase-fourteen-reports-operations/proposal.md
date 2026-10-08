## Why

The research workspace needs portable sourced outputs and reliable operations with controlled external delivery.

## What Changes

- Export sourced workspace Markdown reports, citation manifests and entity/observation JSON/CSV; add a documented STIX2.1 subset after compatibility validation.
- Add previewed optional email/webhook delivery with classification/recipient allowlists and retry/idempotency controls.
- Add worker heartbeat/job-history dashboards, periodic backups, retention and validated offline restore tooling.
- Enable CI when repository workflow permission is available; extend settings/bulk-state/OPML APIs with existing scope/rate protections.

## Capabilities

### New Capabilities

- `reports-operations`: レポート・通知・バックアップ・運用.

### Modified Capabilities

None. Additive capabilities preserve existing RSS/SNS/page and API contracts.

## Impact

Flask/SQLite persistence, Japanese responsive UI, scoped APIs, background jobs and operations documentation. Implementation refresh: additive schema13 after verified schema12 backup. Dependencies: `phase-eight-watchlists-triage`, `phase-eleven-network-intelligence`, `phase-twelve-ai-research-tracking`.
