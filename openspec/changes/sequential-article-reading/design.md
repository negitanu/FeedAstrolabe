## Context

The reader orders articles by published_at DESC, id DESC and supports combined feed, view, query, workspace and tag filters. Article details currently keep the requested list page even if it does not contain the article. Read state changes are explicit POSTs.

## Goals / Non-Goals

**Goals:** Read consecutive filtered articles with native controls, cross page boundaries correctly, and mark only the current article read while advancing without skips.

**Non-Goals:** Automatic read tracking, keyboard shortcut interception, account preferences, database/API changes or client-side fetching.

## Decisions

- Share a database navigation query using window functions over the existing filter and deterministic date/ID order. Return only the current rank and adjacent IDs, without loading all article bodies. Page-local navigation was rejected because it cannot cross page boundaries reliably.
- Align the list page to the selected article's filtered rank, and generate adjacent links with every selected filter and an article-detail fragment for mobile readers. When a detail no longer matches the filter, show that state and omit sequential controls.
- For the new UI POST, validate the existing filter inputs, acquire a SQLite write transaction, check current membership, choose the successor, then mark the current article read. Recompute the successor's page after mutation. A precomputed client target or page increment could skip articles when the unread list shrinks.
- Return HTTP 303 to the next matching detail, or to the filtered list when no successor exists. Missing articles return 404; stale membership returns 409 before mutation. Existing explicit read/unread/star actions remain available.
- Use ordinary anchors/forms and existing CSRF protection. Keep CSP and the disclosure script unchanged.

## Risks / Trade-offs

- Equal timestamps → break ties by article ID in every navigation query.
- Concurrent article/state changes → choose and update under one write transaction; validate membership before mutation.
- Filtered rank changes after marking read → recompute the target rank and page inside the transaction.
- Ranking scans filtered IDs → query metadata only and reuse the existing ordering index; avoid storing a reading snapshot.

## Migration Plan

Deploy Python, templates and CSS together through the normal rebuild. No schema migration; rollback removes only the added reading controls and endpoint. Verify using temporary libraries before deployment.
