## Why

OPML uploads currently register subscriptions immediately, without showing duplicates or allowing cancellation. RSS/Atom parsing accepts DTD-defined entity expansion; importing external XML needs an explicit bounded safety check before tolerant feed parsing.

## What Changes

- Preview OPML titles, URLs, folders and duplicate status before a separate confirmation POST; preserve document order and avoid fetching source URLs during import.
- Bind signed confirmation plans to the initiating session and expire them after 15 minutes. Revalidate and import atomically, safely skipping duplicates introduced since preview.
- Reject DTDs, declared entities, external references, malformed XML, excessive depth and excessive elements before RSS/Atom parsing or OPML registration.
- Record an OSV check of pinned dependencies and regression evidence for the security boundaries.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `feed-collection`: Add a reviewable UI subscription import with explicit confirmation.
- `local-operation`: Add bounded external XML validation before parsing or mutation.

## Impact

Collection and OPML parsing, settings routes/templates and focused security/browser tests. Existing authenticated API OPML import remains a single explicit write operation. No schema migration or new runtime dependency. DTD-dependent and malformed feeds will now be rejected intentionally.
