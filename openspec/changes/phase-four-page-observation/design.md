## Context

Schema v3 stores RSS/SNS in feeds/articles. Chromium rendering introduces untrusted code execution and network requests. The GitHub remote is configured and publication is authorized.

## Goals / Non-Goals

**Goals:** Public text observation with JS rendering, durable baselines/diffs, common reading/API, configurable schedules and retention, safe separate browser service.

**Non-Goals:** Login/session storage, CAPTCHA bypass, form submissions, cross-origin resources, screenshots and full visual diff. These need separate requirements if requested.

## Decisions

- Rebuild feeds transactionally to extend source_type CHECK with page. Preserve all IDs/FKs and add selector, settle_ms, snapshot, observation_seq, revision and retention_days. A canonical URL fragment derived from selector allows separate selectors on one target URL; target stores the real URL. Restore accepts v1-v4.
- Initial success stores a baseline without creating an article. Normalize Unicode NFKC and whitespace per nonempty line; preserve line order. Changes generate monotonically numbered page:<sequence> entries with escaped before/after unified diff. A→B→A creates two events. Store one current baseline; prune unstarred page articles older than configurable 1-365 days, default90. Starred entries survive retention.
- Web/API registration never launches a browser. Manual refresh queues page jobs in a unique-per-source table. A dedicated observer worker processes explicit jobs or due sources, serially under a separate lock; RSS/SNS workers skip pages. Failed jobs are consumed and retry through normal backoff. Configuration revision prevents an in-flight result from overwriting an edited/deleted source.
- Observer parent holds DB and performs HTTP broker requests. A renderer service has no network in Docker, no DB/secrets mounts and only a Unix socket volume shared with the observer. Bidirectional framed JSON passes a render job and broker request/results. The renderer has no credentials. Each job runs in a new process group/browser context and is killed after45s, including Chromium descendants.
- Chromium uses a dead proxy as defense in depth, route interception for all HTTP, blocked service workers/WebSockets/media/fonts/frames/popups/downloads, and no persistent browser state. Broker enforces GET, same exact scheme/host/port as target, public IP/DNS pinning on each request, no redirects or cookies/auth headers, max50 requests and20MiB total,5MiB/request and30s total network budget. Only selected text is returned; no provider error body/raw exception reaches logs/UI. Native mode has these application controls but lacks Docker's OS network isolation.
- Optional observer Compose builds Playwright1.63.0/Chromium in a separate image. Renderer is nonroot, read-only, cap_drop ALL, no-new-privileges, network_mode none, memory512MiB/CPU1/pids128. Chromium's own sandbox is not claimed; network and mount boundaries are container-enforced. Observer uses the lightweight image with DB+IPC, no X token mount.

## Risks / Trade-offs

- [Sites need cross-origin resources/auth] → fail visibly; document same-origin public-only contract.
- [Dynamic text settles late] → configurable0-10s wait after DOMContentLoaded, wait for nonempty CSS match; no guarantee of arbitrary app readiness.
- [Browser hangs or renderer crashes] →45s hard process-group timeout, parent socket deadline, no baseline/state update on failure.
- [Article retention removes unstarred history] → explicit setting/hint, preserve starred articles and current baseline.

## Migration Plan

Back up v3 before restarting Web/RSS worker and adding observer/renderer services. Transactional FK-checked v4 migration. Rollback needs previous image plus stopped-service backup restore. No user observation is configured without operator selection.

## Open Questions

Operator target URLs/selectors and login/screenshot needs are unspecified. Implement public text defaults and verify JS fixture plus a real public example without adding test subscriptions to the actual library.
