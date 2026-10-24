## Context

The reader uses permissive Flask integer coercion for feed and article selectors. Failed conversion falls back to no selector, including on state-changing forms. SQLite accepts only signed 64-bit IDs, while Werkzeug's default URL integer converter accepts larger values. Malformed subscription source types were investigated but already return 400, so no change is needed there.

## Goals / Non-Goals

**Goals:** Reject invalid selectors before mutation or fetch, bound route IDs consistently, preserve valid UI/API behavior, and verify each regression against the original code.

**Non-Goals:** External integration setup, schema changes, live-data mutations and changes to unrelated in-progress work.

## Decisions

- Add a shared positive SQLite-ID URL converter, registered before blueprint routes. Its bounded ASCII digit pattern rejects huge strings before Python conversion with 404. Zero and out-of-range matched IDs return 400, preserving the existing research API validation contract; valid missing IDs retain existing behavior.
- Parse optional reader IDs explicitly. Missing and empty form fields retain the all-feeds behavior; malformed, non-positive and oversized values return 400. Repeated selectors are rejected to avoid ambiguous scopes. Refresh rejects missing target records instead of reporting a successful empty run.
- Apply single-value validation to every reader condition (feed, view, query, workspace and tag). Reject invalid view choices and oversized search terms instead of silently replacing or truncating them; workspace/tag resolution still distinguishes invalid IDs from missing records.
- Use behavior tests that prove state and collection targets remain unchanged on rejection, including valid scoped and empty-selector controls.

## Risks / Trade-offs

- Clients relying on ignored invalid selectors now receive 400 → document the validation contract and retain the normal empty-selector behavior.
- Global ID routing affects many blueprints → check every integer route and run the complete regression suite.
- Sandbox Unix-socket restrictions obscure renderer results → run socket-dependent verification outside that restriction.

## Migration Plan

No data migration. Deploy through the existing image rebuild process; rollback source/image only. Keep production data and external integration settings untouched during tests.
