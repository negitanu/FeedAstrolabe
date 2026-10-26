## 1. Specification and migration

- [x] 1.1 Define/strictly validate shared protocol and native parity contract in both repositories
- [x] 1.2 Add consistent migration backup and journal/schema initialization on both sides

## 2. Synchronization

- [x] 2.1 Implement Web journal, validation, merge and exchange endpoint
- [x] 2.2 Implement compatible Go journal, atomic apply, cursor and replay handling
- [x] 2.3 Add Electron main transport, Access login, optional settings and status/retry UI
- [x] 2.4 Test cross-language HTTP, offline conflict, deletion, malformed responses and restart

## 3. Native feature parity

- [ ] 3.1 Port research tags/classification, attachment provenance and citation workflows
- [ ] 3.2 Port isolated page observation and safe image acquisition
- [ ] 3.3 Port watchlists, triage, saved searches, inbox, digests and duplicate provenance
- [ ] 3.4 Port entities, relations, aliases, corrections, merge, graph and timeline
- [ ] 3.5 Port KEV/EPSS/CVE security intelligence
- [ ] 3.6 Port DNS/RDAP/CT/routing/RPKI network intelligence
- [ ] 3.7 Port arXiv/GitHub/model-card research intelligence
- [ ] 3.8 Complete named assistant profiles, policy/citation propagation and budget compatibility
- [ ] 3.9 Port approved notifications, reports, generation backups and scoped public API
- [ ] 3.10 Port full settings export, source migration and remaining reader/UI compatibility

## 4. Acceptance

- [ ] 4.1 Verify desktop/narrow UI and light/dark/system themes, save/return flows
- [x] 4.2 Run regression, dependency checks and OpenSpec strict validation
- [x] 4.3 Update canonical specs, README, user guide, parity map and verification results
- [x] 4.4 Rebuild/restart affected running environment and verify health/HTTP when deployment is performed

## 5. Reported synchronization failure

- [x] 5.1 Align activation checkbox with its label and verify saved enabled/disabled behavior
- [x] 5.2 Add read-only readiness check and separate Access/missing API/network diagnostics
- [x] 5.3 Verify UI and failure paths with generated HTTP fixtures
- [x] 5.4 Back up the running library, rebuild/restart affected containers, verify health and deployed route
