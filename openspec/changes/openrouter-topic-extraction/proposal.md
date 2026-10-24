## Why

Engagement scores do not identify which developments matter within a research field. Use OpenRouter to group collected public posts into important topics with explanations and traceable source articles.

## What Changes

- Add optional OpenRouter model, budget and per-field importance criteria configuration.
- Add manual and opt-in automatic extraction after successful Mastodon/Bluesky collections.
- Show Japanese topic titles, importance scores, summaries, reasons, uncertainties and source articles alongside existing rankings.
- Add durable, idempotent worker jobs, bounded inputs, provider price ceilings, daily budgets, safe failures and backup/restore support.
- Configure the API key through `.env`; no new dependency or service.

## Capabilities

### New Capabilities
- `openrouter-topic-extraction`: bounded semantic extraction of important topics from public social research samples.

### Modified Capabilities

None. Existing collection and Ollama assistant behavior remain compatible.

## Impact

Schema v16, SNS research UI/API, worker, new fixed-endpoint OpenRouter transport, Compose optional environment, scoped APIs, tests and documentation.
