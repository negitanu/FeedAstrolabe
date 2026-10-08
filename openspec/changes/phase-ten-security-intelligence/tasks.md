## 1. Prerequisites

- [ ] 1.1 Verify implementation dependencies, inspect deployed schema and refresh proposal/design/specs against current code before coding.

## 2. Implementation

- [ ] 2.1 Review CISA/EPSS/CVE official contracts and finalize adapter budgets and fixture schemas.
- [ ] 2.2 Implement reusable connector jobs/cache/cooldown/outbound identifier policy and read-only adapters.
- [ ] 2.3 Implement dated vulnerability enrichment and CVE evidence linking.
- [ ] 2.4 Implement vulnerability cards, applicability review and watchlist updates.
- [ ] 2.5 Test stale/unknown states, version ambiguity, provider failures, private redirects, credential confinement and repeat jobs.
- [ ] 2.6 Verify opt-in live public-identifier retrieval; record provider configuration gaps separately.

## 3. Acceptance and delivery

- [ ] 3.1 Run meaningful acceptance/regression tests mapped to every scenario, including migration/backup, authorization and hostile inputs.
- [ ] 3.2 Verify responsive Japanese UI, live HTTP APIs and container restart/state preservation in isolated test libraries; distinguish fixture versus real external acceptance.
- [ ] 3.3 Update API/operations documentation and verification receipt; strictly validate all OpenSpec artifacts.
- [ ] 3.4 Scan Git candidates/history for credentials, commit/push verified source; mark only actually implemented/verified tasks complete.
- [ ] 3.5 Synchronize completed delta specs and archive this change only after acceptance, retaining any externally blocked verification explicitly.
