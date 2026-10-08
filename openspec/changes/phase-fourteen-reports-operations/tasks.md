## 1. Prerequisites

- [x] 1.1 Verify implementation dependencies, inspect deployed schema and refresh proposal/design/specs against current code before coding.

## 2. Implementation

- [x] 2.1 Implement Markdown/citation-manifest/JSON/CSV exports and classification selection; validate documented STIX subset mapping.
- [x] 2.2 Implement opt-in recipient/endpoint profiles, exact-payload preview, signed webhook delivery and bounded idempotent retries.
- [x] 2.3 Implement safe worker heartbeats/job history and operations UI/API.
- [x] 2.4 Implement scheduled manifest/blob backups, generation retention and verified offline restore instructions.
- [x] 2.5 Implement scoped settings/bulk-state/OPML APIs and document partial/atomic contracts.
- [x] 2.6 Activate existing CI template only when workflow permission is available; preserve explicit external setup status otherwise.
- [x] 2.7 Test secret/restricted export filtering, CSV formulas, webhook SSRF/retries, heartbeat staleness, backup corruption/online restore and API bounds.

## 3. Acceptance and delivery

- [x] 3.1 Run meaningful acceptance/regression tests mapped to every scenario, including migration/backup, authorization and hostile inputs.
- [x] 3.2 Verify responsive Japanese UI, live HTTP APIs and container restart/state preservation in isolated test libraries; distinguish fixture versus real external acceptance.
- [x] 3.3 Update API/operations documentation and verification receipt; strictly validate all OpenSpec artifacts.
- [ ] 3.4 Scan Git candidates/history for credentials, commit/push verified source; mark only actually implemented/verified tasks complete.
- [ ] 3.5 Synchronize completed delta specs and archive this change only after acceptance, retaining any externally blocked verification explicitly.
