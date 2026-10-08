## Context

schema v4 unifies RSS, X, Mastodon and page subscriptions. API authentication already enforces write scope on mutations. Collection holds refresh.lock and page observation uses revision checks.

## Goals / Non-Goals

**Goals:** partial atomic edits, state-preserving URL repair, API deletion/manual refresh, shared UI/API validation.

**Non-Goals:** source type/SNS identity conversion, full-library bulk deletion, new schema, asynchronous RSS collection, Cloudflare setup and credential issuance through API.

## Decisions

- Use a shared subscriptions module for PATCH/UI editing and deletion. Acquire the existing nonblocking refresh lock, start a SQLite IMMEDIATE transaction, read/validate current configuration and update atomically. Unknown fields, empty patches and invalid types fail without partial writes. Duplicates return409, missing IDs404, busy collection409.
- Edit common folder/enabled/poll_interval (null inherits the global interval). Allow URL for RSS/page and selector/settle_ms/retention_days for pages. SNS identity is immutable; recreate a subscription for a different account. New URL validation rejects credentials, private literal addresses and localhost; DNS is pinned/public-checked during collection, with no fetch during editing.
- RSS URL changes reset conditional headers, check/success/error/backoff state. Existing articles/IDs remain; next collection is unconditional. Page URL/selector/wait changes reset baseline/check state and increment revision; retention/folder/pause edits preserve baseline. Revision prevents in-flight stale observation commits. Preserve observation sequence across edits.
- DELETE204 cascades articles and page jobs under the collection lock. A deleted page's result is discarded by the existing revision/current-row check.
- POST /feeds/{id}/refresh: page202 durable unique reservation; RSS/SNS200 synchronous counts and retrieved feed status. SNS provider cooldown429 with Retry-After; active collection409. Explicit refresh works during pause, respecting provider cooldown. Existing /observe remains compatible.
- UI adds RSS/page URL repair form and uses the same helpers for schedule/page editing and deletion. No custom titles that would be overwritten by RSS refresh.

## Risks / Trade-offs

- URL changes may introduce different entries → preserve old history and explicitly describe that no old articles are removed and GUID identity still applies.
- Synchronous refresh can take time → document client timeout and recommend worker for normal polling.
- Configuration editing during RSS collection returns busy → users retry instead of silently losing changes.
- Deletion removes history → document DELETE semantics; no actual user subscription is deleted during acceptance tests.

## Migration Plan

No DB migration. Back up schema v4, build/restart all existing services, verify existing IDs/read/star and live API in an isolated test library. Roll back application images with compatible v4 DB. Keep renderer boundaries unchanged.
