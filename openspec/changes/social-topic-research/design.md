## Context

The worker already schedules RSS, Mastodon accounts, X and page observations. Article/evidence identity and read/star state must survive upgrades. The reader recently adopted compact folder-first navigation.

## Goals / Non-Goals

**Goals:** user-selected topics, bounded official API polling, inspectable rankings/history, reuse reader/evidence and pause/backoff controls, retire X safely.

**Non-Goals:** scraping, private timelines, posting, paid API credentials, globally exhaustive trends, LLM summaries or provider-global popularity claims.

## Decisions

- Use `source_kind=topic` feeds and schema v15 tables for topic window, runs and ranked article snapshots. Add Bluesky to the feeds CHECK constraint while retaining legacy X. Keep latest 30 successful runs per topic and up to 40 ranked results per run. Reader articles follow existing retention policy; deleting a subscription cascades its research rows.
- Mastodon: up to three comma-separated public hashtags on an explicit HTTPS instance, one tag timeline request (40 posts) per tag. No unauthenticated full-text search claim. Existing account adapter remains. Bluesky: fixed `api.bsky.app/xrpc/app.bsky.feed.searchPosts`, one top and one latest request (100 each), no cursor crawl. Deduplicate provider IDs, enforce a configured 1–168 hour publication window locally, ignore boosts/private/invalid dates. Defaults: 24 hours, 1800 seconds; minimum interval 900 seconds, including global/CLI overrides.
- Rank samples by likes + 2×reposts + replies, tie-break by publication time and stable identity. Count each normalized hashtag at most once per sampled post. This is a sample ranking; display scope and coverage limits. Do not compare scores across providers. Snapshot counters, scores and hashtag counts per successful run; failed requests keep last successful results.
- All requests use existing pinned public-address HTTPS, size/deadline limits, no redirects and generic errors. Remove Bearer transport and X secret code entirely. Share 429 cooldowns across Bluesky subscriptions and across Mastodon subscriptions on the same instance. Respect manual cooldown, pause and exponential backoff. Registration/editing never performs network I/O.
- Save a run, article updates and ranked results atomically. Capture evidence afterward through the existing explicit evidence-error tracking. Preserve original article order/read/star state on refresh. Return topic metadata and latest results through the scoped API; UI writes use CSRF.
- Disable existing X subscriptions during migration and prevent re-enabling, new registration or explicit refresh. Saved X articles remain readable, exportable through normal APIs and available to research evidence.

## Risks / Trade-offs

- Public servers may require authentication or omit federated posts → show access errors, allow changing instance via recreating a topic, document sample scope. No scraping fallback.
- Search indexing, incomplete cursors, changing engagement → sample only; snapshots show collection time, window and actual post count. No completeness or growth claims.
- Frequent polling/storage → 15 minute minimum, bounded requests/results/history, existing global pause/backoff. Original articles/evidence remain intentionally durable.
- Migration/backup integrity → transactional feed rebuild, foreign-key checks, v14 fixture, backup/restore and restart tests. Roll back with a pre-upgrade backup and previous image; old app cannot open v15.

## Migration Plan

Back up the data directory, rebuild application images, recreate services. Schema upgrade runs under the existing init lock; X subscriptions become disabled with a visible retirement message. Remove obsolete X token environment plumbing from tracked examples/Compose, without reading or deleting local secrets. Register new topics in the SNS research screen.

## Open Questions

None. Public APIs are sufficient for this initial research feature.

## Primary References

- https://docs.joinmastodon.org/methods/timelines/
- https://docs.joinmastodon.org/methods/search/
- https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/feed/searchPosts.json
