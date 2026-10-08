## 1. Prerequisites

- [ ] 1.1 Verify implementation dependencies, inspect deployed schema and refresh proposal/design/specs against current code before coding.

## 2. Implementation

- [ ] 2.1 Implement immutable evidence/version/source metadata and nullable historical references.
- [ ] 2.2 Hook RSS/SNS/page ingestion into bounded captured representations; label backfilled evidence as captured now.
- [ ] 2.3 Implement verified quotation anchors and evidence pinning from workspaces/notes.
- [ ] 2.4 Implement quota-controlled attachment upload/download and isolated text/PDF extraction after dependency review.
- [ ] 2.5 Extend backup/restore to consistent manifests/blobs; implement unpinned retention and integrity verification.
- [ ] 2.6 Test upstream mutation, subscription delete, expired page history, hash verification, quota/path/MIME attacks and incomplete restore.

## 3. Acceptance and delivery

- [ ] 3.1 Run meaningful acceptance/regression tests mapped to every scenario, including migration/backup, authorization and hostile inputs.
- [ ] 3.2 Verify responsive Japanese UI, live HTTP APIs and container restart/state preservation in isolated test libraries; distinguish fixture versus real external acceptance.
- [ ] 3.3 Update API/operations documentation and verification receipt; strictly validate all OpenSpec artifacts.
- [ ] 3.4 Scan Git candidates/history for credentials, commit/push verified source; mark only actually implemented/verified tasks complete.
- [ ] 3.5 Synchronize completed delta specs and archive this change only after acceptance, retaining any externally blocked verification explicitly.
