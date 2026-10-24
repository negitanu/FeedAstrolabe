## Context
Current schema13 stores UTC timestamps and templates append UTC directly.
## Goals / Non-Goals
Goals: persistent UTC/JST choice across all UI timestamps.
Non-goals: changing stored instants, API timestamps, report payloads or datetime form input semantics.
## Decisions
Add settings.display_timezone in transactional schema14 migration, default UTC, CHECK allowing UTC/Asia/Tokyo. Keep existing form clients compatible when field omitted.
Use one request-cached Jinja filter with datetime.fromisoformat and fixed +09:00 timezone (no platform tzdata dependency). Naive database timestamps mean UTC; aware values preserve their instant. Empty values use explicit fallback, invalid dates show unknown.
Apply formatting only to display expressions, never form values or serialized JSON. UTC date input help stays explicit.
## Risks / Trade-offs
Schema upgrade requires updated image for every writer; rollback requires pre-upgrade bundle. Existing migrated preferences and timestamps are preserved. Shared setting applies to all library users.
## Migration Plan
Back up schema13 bundle with writers stopped before deploying schema14. Upgrade all services together. This implementation does not automatically deploy.
