## 1. Implementation

- [x] 1.1 Add explicit delegated tunnel access mode, token-only default Compose and accurate settings status.
- [x] 1.2 Simplify dotenv inputs and document Cloudflare prerequisites plus optional strict mode.

## 2. Verification

- [x] 2.1 Test token-only dotenv/Compose and application startup, public Host, Secure cookies, CSRF and API auth; retain strict/local tests.
- [x] 2.2 Verify the built image in an isolated container, run relevant/full regression and strict spec/secret/diff checks; record verification limits.

Verification (2026-10-21): 50 focused tests and all 381 regression tests passed with real browser enabled and no skips. The final startup error wording was checked again by all seven tunnel-mode tests. Token-only temporary dotenv resolution and actual local dotenv quiet validation passed. Built app image feedastrolabe-minimal-tunnel-verify:local and ran a temporary non-root/read-only/network-none container without published ports or operator data. Actual Waitress HTTP checks passed for empty Access inputs, public Host UI 200, Secure cookie, CSRF 400, API missing key 401, read key 200 and write denial 403. All 27 OpenSpec items passed strict validation; diff and tracked/untracked secret pattern checks plus Gitleaks docs/scripts/tests checks passed. Local token/optional values were preserved without displaying them. No real Tunnel or production service was started. Cloudflare Access/Protect with Access and external unauthorized-user rejection require operator-side acceptance; local tests do not verify that remote policy.
