## Why

Replace X collection with official-API research on Mastodon and Bluesky so users can periodically discover notable public posts in chosen fields without scraping.

## What Changes

- Add configurable topic subscriptions, bounded periodic sampling, engagement rankings, related hashtag counts and run history.
- Integrate results with the existing reader, folders, evidence, worker and scoped API.
- **BREAKING**: reject new X subscriptions, disable existing X polling and remove X credential plumbing; preserve saved X articles and research state.
- Preserve public Mastodon account subscriptions.

## Capabilities

### New Capabilities
- `social-topic-research`: official API topic collection, research presentation and safe X retirement.

### Modified Capabilities

None. Historical X data remains readable through the existing article contracts.

## Impact

SQLite schema v15, social adapters, worker scheduling, UI/API, Compose optional environment, tests and operational documentation. No new dependencies or network listeners.
