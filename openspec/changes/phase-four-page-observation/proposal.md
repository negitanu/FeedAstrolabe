## Why

Public pages without RSS need change observation in the existing reading workflow. Phase three is implemented; the operator requests phase four while deferring Cloudflare live setup.

## What Changes

- Register public page URLs, CSS selectors, settling time, polling interval and article retention through settings and write-scoped API.
- Render JavaScript using Playwright Chromium in a separate network-isolated service; broker bounded same-origin GET requests through the existing public-IP/DNS-pinned transport.
- Store a normalized initial baseline and emit a new diff article only on change; retain read/star state and repeated transitions.
- Add a dedicated queued/scheduled observation worker, status/errors, bounded browser lifecycle and container resources.
- Document local/container operation, verification and remaining operator settings; scan and push to the existing GitHub remote.

## Capabilities

### New Capabilities

- `page-observation`: configuration, scheduling, baselines, diffs, retention and shared UI/API integration.
- `isolated-page-rendering`: browser/network separation, request bounds and safe failure reporting.

### Modified Capabilities

None. RSS/SNS workflows continue unchanged.

## Impact

SQLite v4 migration, page job queue and source metadata; optional pinned Playwright/Chromium dependency and Compose services. Web and RSS/SNS worker stay lightweight. Page observation supports public text without login or screenshots. Native rendering uses route interception and a dead proxy; Docker adds an OS network boundary and no data/secrets mounts. CI remains a template due to the existing OAuth scope.
