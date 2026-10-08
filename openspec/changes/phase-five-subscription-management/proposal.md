## Why

The reader supports all four source types but API clients cannot edit, delete or manually refresh subscriptions. Users also cannot repair changed RSS/page URLs while preserving their library state.

## What Changes

- Add write-scoped PATCH/DELETE subscription APIs and a common manual refresh API.
- Add public RSS/page URL editing, folders and polling settings through shared atomic validation; page selector/wait/retention become editable through API.
- Preserve subscription/article IDs and read/star state; reset RSS validators or page baselines when their targets change.
- Serialize RSS configuration/deletion with collection and reject stale page captures via revisions.
- Document scope, synchronous RSS/SNS refresh versus queued page observation, and source identity limits.

## Capabilities

### New Capabilities

- `subscription-management`: safe partial edits, deletion and manual refresh across UI/API.

### Modified Capabilities

None. Existing read/registration contracts remain compatible.

## Impact

Flask routes, subscription persistence helpers, settings UI, API/OpenAPI, meaningful regression tests and operations documentation. No schema migration or dependency changes. Cloudflare connection and live X credential setup remain deferred.
