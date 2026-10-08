## 1. Prerequisites

- [x] 1.1 Verify implementation dependencies, inspect deployed schema and refresh proposal/design/specs against current code before coding.

## 2. Implementation

- [x] 2.1 Review DNS/RDAP referral, RIPEstat and CT official data contracts/coverage/limits.
- [x] 2.2 Implement public DNS/RDAP adapters and dated normalized records.
- [x] 2.3 Implement read-only routing/RPKI and CT metadata adapters with validated redirects/referrals.
- [x] 2.4 Implement field-level change events, watchlist scheduling and retention.
- [x] 2.5 Build network entity history/detail UI and scoped observation APIs.
- [x] 2.6 Test TTL/coverage/absence semantics, prefix-origin interpretation, budget/private target attacks and fixture/live acceptance.

## 3. Acceptance and delivery

- [x] 3.1 Run meaningful acceptance/regression tests mapped to every scenario, including migration/backup, authorization and hostile inputs.
- [x] 3.2 Verify responsive Japanese UI, live HTTP APIs and container restart/state preservation in isolated test libraries; distinguish fixture versus real external acceptance.
- [x] 3.3 Update API/operations documentation and verification receipt; strictly validate all OpenSpec artifacts.
- [ ] 3.4 Scan Git candidates/history for credentials, commit/push verified source; mark only actually implemented/verified tasks complete.
- [ ] 3.5 Synchronize completed delta specs and archive this change only after acceptance, retaining any externally blocked verification explicitly.
