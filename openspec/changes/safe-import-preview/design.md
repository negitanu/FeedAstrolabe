## Context

OPML already uses defusedxml but registers immediately on the UI upload POST and reverses document order with its stack traversal. Feedparser accepts declared XML entities. Existing Flask/itsdangerous signing, CSRF, refresh locks and atomic inserts can support a safe preview without schema changes.

## Goals / Non-Goals

**Goals:** Review and cancel subscription imports; preserve source order; distinguish existing/file duplicates; reject unsafe or structurally excessive external XML before feedparser or registration; keep source URLs unfetched during import.

**Non-Goals:** Account isolation, persistent import jobs, API redesign, external network access during preview, dependency upgrades without advisory evidence.

## Decisions

- Split OPML parsing, classification and atomic entry registration so the UI can preview while the authenticated API retains its explicit one-step import. Recheck uniqueness at confirmation using the existing database constraint.
- Store the normalized plan only in the preview response, using a timed serializer with an import-specific salt and a SHA-256 binding to the current CSRF session. Limit token size, verify signature and 15-minute age, check session binding and revalidate entry shape/URLs before a write. A server-side import table was rejected because a transient bounded plan needs no new persistence or cleanup.
- Reject unsafe XML with a streaming defusedxml validation pass. RSS/Atom: at most 5 MiB, 100,000 elements and depth 64; OPML: at most 1 MiB, 10,000 elements and depth 64, plus the existing 100-feed limit. Clear completed elements during validation. Fail closed on malformed XML before the existing parser.
- Use native forms and escaped responsive lists with script-src 'none'. Preview reveals subscription metadata to the same authorized UI user; no URLs/titles are copied into cookies, flash messages or logs.
- Keep API import semantics and all-or-nothing registration, using a write transaction and refresh lock. Replaying a valid confirmation only skips duplicates and never overwrites existing subscriptions.

## Risks / Trade-offs

- Legacy malformed/DTD-dependent feeds → deliberate rejection with a safe error; valid RSS/Atom encodings and built-in/numeric references receive regression tests.
- XML parsing CPU/memory → byte, depth and element limits plus streaming cleanup before feedparser.
- Plan tampering, reuse in another session, expiration → signed scoped payload, CSRF binding and age validation before mutation.
- Library changes after preview → apply database uniqueness at confirmation and report actual added/skipped counts.

## Migration Plan

Rebuild server/templates together. No database migration or new runtime dependency. Rollback restores the prior UI upload behavior. Verify temporary libraries, real Chromium and pinned dependency advisories before any live deployment.
