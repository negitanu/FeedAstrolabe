## 1. Prerequisites

- [x] 1.1 Verify implementation dependencies, inspect deployed schema and refresh proposal/design/specs against current code before coding.

## 2. Implementation

- [x] 2.1 Implement v4 upgrade, associations, tag tables and archive semantics with backup/restore support.
- [x] 2.2 Implement workspace and note CRUD, optimistic revision conflict handling and strict bounds.
- [x] 2.3 Implement scoped paginated API and cross-workspace article/tag filtering.
- [x] 2.4 Build Japanese workspace/detail/note UI with sanitized Markdown and explicit classification explanation.
- [x] 2.5 Test migration/state preservation, multi-workspace association, archive, note conflicts, XSS, CSRF and API scope.

## 3. Acceptance and delivery

- [x] 3.1 Run meaningful acceptance/regression tests mapped to every scenario, including migration/backup, authorization and hostile inputs.
- [x] 3.2 Verify responsive Japanese UI, live HTTP APIs and container restart/state preservation in isolated test libraries; distinguish fixture versus real external acceptance.
- [x] 3.3 Update API/operations documentation and verification receipt; strictly validate all OpenSpec artifacts.
- [x] 3.4 Scan Git candidates/history for credentials, commit/push verified source; mark only actually implemented/verified tasks complete.
- [x] 3.5 Synchronize completed delta specs and archive this change only after acceptance, retaining any externally blocked verification explicitly.
