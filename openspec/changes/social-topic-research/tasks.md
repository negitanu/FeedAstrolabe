## 1. Storage and retirement

- [x] 1.1 Add v15 migration and topic/run/ranking tables with safe X retirement and v14 fixture.
- [x] 1.2 Remove active X adapters/credentials and enforce retirement in registration, editing and manual refresh.

## 2. Research collection

- [x] 2.1 Implement validated topic registration/editing and bounded Mastodon/Bluesky official API adapters.
- [x] 2.2 Implement window filtering, deduplication, rankings, hashtag summaries and atomic snapshots with evidence capture.
- [x] 2.3 Integrate periodic scheduling, minimum intervals, instance-scoped cooldowns, pause and last-good behavior.

## 3. UI and API

- [x] 3.1 Add compact topic creation/editing, latest rankings, collection history and reader navigation.
- [x] 3.2 Expose topic settings/results through scoped APIs and update OpenAPI.
- [x] 3.3 Replace X onboarding and optional Compose credential plumbing; document setup and provider scope.

## 4. Verification

- [x] 4.1 Test migration, backup/restore, restart and preservation of historical article state.
- [x] 4.2 Test adapter validation, window/ranking/deduplication, failure atomicity, limits and provider cooldowns.
- [x] 4.3 Verify UI/API authorization and desktop/mobile browser flows.
- [x] 4.4 Run full regression, strict OpenSpec, secret/diff checks and document evidence.
