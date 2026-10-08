## 1. Foundation

- [x] 1.1 Create Python package, pinned dependencies, SQLite schema and persistent signing key.
- [x] 1.2 Document local startup, data backup and the four ordered delivery phases.

## 2. Feed collection

- [x] 2.1 Implement bounded public-only HTTP fetching, DNS pinning, redirects and conditional requests.
- [x] 2.2 Implement RSS/Atom ingestion, deduplication, error isolation and refresh locking.
- [x] 2.3 Implement subscriptions, folders, manual refresh and periodic worker.

## 3. Reader

- [x] 3.1 Implement Japanese responsive UI with sidebar, paginated filters, search and article detail.
- [x] 3.2 Implement CSRF-protected read/star operations and scoped bulk read with safe HTML.

## 4. Verification

- [x] 4.1 Verify RSS/Atom, duplicate ingestion, persistent states, filters, pagination, 304, errors and security limits with automated tests.
- [x] 4.2 Validate OpenSpec, inspect browser UI, record verification and commit source in Git.
