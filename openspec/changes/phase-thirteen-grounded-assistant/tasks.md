## 1. Prerequisites

- [x] 1.1 Verify implementation dependencies, inspect deployed schema and refresh proposal/design/specs against current code before coding.

## 2. Implementation

- [x] 2.1 Review current provider/local runtime options and choose a bounded, documented model adapter without storing credentials in DB/Git.
- [x] 2.2 Implement model profiles, exact-input preview, classification/secret filtering and per-run/daily budgets.
- [x] 2.3 Implement workspace-scoped retrieval and quote/citation validation.
- [x] 2.4 Implement durable summary/translation/compare/QA jobs with safe rendering and model/input lineage.
- [x] 2.5 Implement human review/revision states and clear unsupported-answer behavior.
- [x] 2.6 Create adversarial evaluation set: prompt injection, unsupported citations, conflicting sources, restricted data, cross-workspace retrieval and budget failures.
- [x] 2.7 Verify opt-in live model call or local runtime; mark missing model configuration as unverified, not success.

## 3. Acceptance and delivery

- [x] 3.1 Run meaningful acceptance/regression tests mapped to every scenario, including migration/backup, authorization and hostile inputs.
- [x] 3.2 Verify responsive Japanese UI, live HTTP APIs and container restart/state preservation in isolated test libraries; distinguish fixture versus real external acceptance.
- [x] 3.3 Update API/operations documentation and verification receipt; strictly validate all OpenSpec artifacts.
- [ ] 3.4 Scan Git candidates/history for credentials, commit/push verified source; mark only actually implemented/verified tasks complete.
- [ ] 3.5 Synchronize completed delta specs and archive this change only after acceptance, retaining any externally blocked verification explicitly.
