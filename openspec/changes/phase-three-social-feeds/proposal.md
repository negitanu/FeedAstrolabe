## Why

Readers need to follow social posts alongside RSS using the existing read/star/search workflow. Cloudflare live setup is deferred by the operator; SNS implementation can proceed independently.

## What Changes

- Add X account/list and public Mastodon account adapters with bounded incremental pagination.
- Reuse feeds/articles as source/entry records with provider metadata, cursor and rate-limit state; preserve RSS and API compatibility.
- Add SNS registration and status in settings and scoped API registration/filtering.
- Load X credentials only from an ignored read-only file; never accept or expose credentials through source configuration or errors.
- Harden Git exclusions, scan staged files and history for secrets, and push to the designated GitHub repository.

## Capabilities

### New Capabilities

- `social-feeds`: SNS subscriptions, collection, pagination, read/star/API integration and failure handling.
- `credential-hygiene`: file-based credentials, safe HTTP and errors, exclusions and pre-push secret checks.

### Modified Capabilities

None. Existing RSS behavior remains supported.

## Impact

SQLite schema version 3; collection, HTTP transport, settings, API/OpenAPI, backup tooling and optional Compose secret mount. No new runtime dependencies. X live verification requires operator-provided API access and targets; unit/integration tests use deterministic provider responses. Cloudflare live acceptance remains deferred.
