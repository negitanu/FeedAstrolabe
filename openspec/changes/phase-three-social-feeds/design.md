## Context

Schema v2 has feeds/articles, a shared refresh lock, preferences and scoped API keys. The operator defers Cloudflare live setup and authorizes a push to the public GitHub remote.

## Goals / Non-Goals

**Goals:** Follow X accounts/lists and public Mastodon accounts through the existing UI/API; incremental collection, stable post identity, safe authentication and repository hygiene.

**Non-Goals:** Posting, direct messages, private Mastodon feeds, browser scraping, full historical archives, paid API provisioning and Cloudflare live setup.

## Decisions

- Add source_type (rss/x/mastodon), target, instance_url, provider_id, since_id, page_cursor, pending_newest and retry_at to feeds. Keep table names and IDs to preserve API compatibility; articles already implement the common entry model. Separate source tables would add migration and joins without a current benefit.
- X accepts usernames or numeric account IDs and numeric list IDs. X uses only https://api.x.com, file-loaded Bearer token with the required read permissions, official v2 endpoints and max_results=100. Mastodon accepts an HTTPS origin and local username, lookup ID and public statuses (limit 40). User-supplied API URLs and credentials are rejected.
- The first poll takes one page as a recent-post baseline. Incremental account polls use a fixed since_id; X lists do not accept since_id, so the adapter stops at the saved post ID locally. Incremental polls use the fixed lower bound and at most three pages; page cursor and pending newest ID persist until completion. Every successful page commits entries and continuation atomically; a later failure retains progress. This avoids dropping posts when a polling batch fills. Provider history retention and expired cursors may still require operator intervention; do not silently reset cursors.
- HTTP JSON requests reuse public-address validation and DNS pinning with TLS, 30-second/5-MiB bounds and no redirects. Status-only errors omit response bodies and exception details. Retry-After and rate reset impose a persisted delay shared by X sources using the same token, including manual refresh. Missing credentials/auth failures use the existing exponential backoff; no token is passed in URLs.
- Secrets are loaded from FEEDASTROLABE_X_TOKEN_FILE; an optional Compose overlay mounts only the X secret read-only. Native files require regular non-symlink files and private mode; Docker secret files allow vendor-compatible readable mode in a private parent directory. No UI token input or JSON token property.
- API feed records expose source metadata but omit internal pagination state. POST /api/v1/feeds accepts explicit source_type/target/instance_url; existing RSS requests remain valid. OPML exports RSS only because SNS records cannot be imported as RSS.
- Repository checks inspect staged content and all historical blobs without printing matching values. Ignore DBs, keys, secret directories, dotenv variants and local exports. Provide a SHA-pinned GitHub CI template for tests, OpenSpec and secret checks. The existing OAuth credential lacks workflow scope; automatic CI activation is deferred without expanding authentication permissions.

## Risks / Trade-offs

- [X API charges/permissions] → starts with no configured subscriptions, documents official pricing and token provisioning; no paid calls without operator setup.
- [Provider rate limits] → persisted retry gates and shared X cooldown; bounded page counts.
- [Long polling gaps] → durable incremental cursors, explicit errors on rejected cursors; no claim of archive completeness or deletion synchronization.
- [Federated content safety] → sanitize HTML, do not fetch embedded media, public-address enforcement on every request.

## Migration Plan

Back up running container DB before deploying v3. Transactionally migrate v1/v2 to v3 without changing entry IDs or states. Both services share the upgraded image and volume. Rollback requires stopping both services and restoring the v2 backup with the previous image.

## Open Questions

Operator X plan/token and desired accounts/lists remain unspecified; deterministic tests cover X and real paid verification remains pending. Public Mastodon requires an instance exposing unauthenticated account/status endpoints.
