## 1. Prerequisites

- [ ] 1.1 Verify implementation dependencies, inspect deployed schema and refresh proposal/design/specs against current code before coding.

## 2. Implementation

- [ ] 2.1 Implement saved-search/watchlist/rule persistence and bounded AST validation.
- [ ] 2.2 Implement indexed filtering and incremental versioned matching worker.
- [ ] 2.3 Implement exact duplicate grouping with provenance and manual undo.
- [ ] 2.4 Add priority explanations, match inbox, daily digest and scoped APIs.
- [ ] 2.5 Test literal query escaping, excessive rules, exclusion precedence, reprocessing/idempotency and state-preserving duplicate groups.

## 3. Acceptance and delivery

- [ ] 3.1 Run meaningful acceptance/regression tests mapped to every scenario, including migration/backup, authorization and hostile inputs.
- [ ] 3.2 Verify responsive Japanese UI, live HTTP APIs and container restart/state preservation in isolated test libraries; distinguish fixture versus real external acceptance.
- [ ] 3.3 Update API/operations documentation and verification receipt; strictly validate all OpenSpec artifacts.
- [ ] 3.4 Scan Git candidates/history for credentials, commit/push verified source; mark only actually implemented/verified tasks complete.
- [ ] 3.5 Synchronize completed delta specs and archive this change only after acceptance, retaining any externally blocked verification explicitly.
