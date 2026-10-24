## Context

Social research persists bounded successful runs and up to 40 engagement-ranked articles. The existing grounded assistant is Ollama-specific and requires case-level exact previews. Topic extraction instead uses public social samples and explicit global/per-field opt-in, without modifying that assistant's approval contract.

## Goals / Non-Goals

**Goals:** Japanese semantic importance extraction, source-linked explanations, manual/automatic worker execution, predictable limits and safe persistence.

**Non-Goals:** general assistant migration, external browsing/tools, private case processing, autonomous posting or treating generated importance as verified fact.

## Decisions

- Add schema v16: a singleton OpenRouter configuration, topic auto-analysis/criteria/revision fields, immutable analysis jobs and UTC-day budget reservations. Jobs reference collection runs and cascade with their existing 30-run retention. Configuration starts disabled with no model; migration sends nothing.
- Store `OPENROUTER_API_KEY` only in runtime environment, supplied through `.env` to web/worker. No UI/API credential fields or DB storage. A key alone does not enable generation. Models are explicit `provider/model` IDs, with no automatic model choice or model fallback.
- Use pinned public HTTPS only to `openrouter.ai/api/v1/chat/completions`, no redirects, tools, SDK dependency, streaming or automatic POST retries. Limit requests to 32KiB, responses to 1MiB and execution to 90 seconds. Structured JSON schema, `require_parameters=true`, `allow_fallbacks=false`, `data_collection=deny`, and explicit provider token/request price ceilings are always sent. Zero request-based price ceiling rejects per-request charging.
- Select up to 20 ranked posts from the latest successful social run; snapshot article IDs, bounded plain-text excerpts, reaction counts, period and field criteria. Exclude sources associated with internal/restricted cases (feed, article, evidence, notes, quotations) and likely credential strings. Recheck classification under the SQLite write lock immediately before dispatch. Never send annotations, case titles or notes. Stop adding sources before the 32KiB bound; no eligible sources means no model call.
- Ask for at most five grouped topics with title, summary, importance 0–100, reason, uncertainty and source IDs. Validate types/limits/IDs, reject unknown citations and tool/refusal/truncated responses, sort importance descending and render escaped text. Label results unverified and sample-scoped. Keep exact wire/hash, source snapshots, model, usage, estimated reservation and reported cost; never rewrite articles/evidence.
- Queue from manual POST or worker schedule, execute at most one job per worker cycle under `social-ai.lock`. A collection run plus configuration/topic revisions is idempotent, including failures. Reserve a conservative UTF-8-byte input token bound plus configured output ceiling against per-call and UTC-day cost/call caps before dispatch. Interrupted running jobs fail without resending. Failures keep reservations; 429 sets shared cooldown. Disabling or policy/revision changes block queued dispatch. Automatic jobs respect global/feed/topic pause; manual jobs follow normal manual-refresh semantics.
- Default ceilings: 2048 output tokens, 24 calls/day, $0.10/call and $1/day, provider input $1/million and output $3/million tokens. These are selectable ceilings rather than claims about model prices. Actual provider billing remains authoritative. Restore disables AI configuration and automatic topic analysis and fails unfinished jobs; runtime credentials are never in backups.
- Extend existing SNS UI/API with configuration, per-field criteria, queue/status/results and source links. GET never triggers paid work; all mutations use existing CSRF or write-scoped API authorization.

## Risks / Trade-offs

- Hallucinations and prompt injection → text-only untrusted sources, fixed prompt/schema, citation validation, uncertainty field and explicit unverified label. Citation identity does not prove factual accuracy.
- Provider changes or unsupported model parameters → fixed model and fail-closed routing with actionable errors; no silent downgrade.
- Charges despite timeout/crash → durable reservations and no retry for the same run/settings. For another attempt, collect a new run or explicitly change settings.
- Policy edits during dispatch → hold the DB write transaction up to 90 seconds, matching the established assistant serialization pattern; document possible busy writes.
- Sample/engagement bias → show sample size and collection period; this is not a global trend ranking.

## Migration Plan

Back up, rebuild application images and recreate services. Schema v16 upgrades existing data transactionally. Configure `.env`, model and enable generation, then choose per-field auto extraction or manual queue. Roll back using the old image and pre-upgrade backup. Do not auto-archive the change.

## Open Questions

None. The operator chooses the OpenRouter model and account; implementation tests use synthetic responses without spending credits.

## References

- https://openrouter.ai/docs/guides/features/structured-outputs
- https://openrouter.ai/docs/guides/routing/provider-selection
- https://openrouter.ai/docs/api/reference/overview
