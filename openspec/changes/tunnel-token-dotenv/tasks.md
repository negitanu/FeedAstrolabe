## 1. Implementation

- [x] 1.1 Replace Tunnel secret file with required dotenv environment input and update isolated verification.
- [x] 1.2 Update local/example dotenv and operator documentation while preserving existing values.

## 2. Verification

- [x] 2.1 Test real Compose dotenv loading, missing/empty rejection, credential scope and verification isolation.
- [x] 2.2 Run strict OpenSpec, secret and diff checks and record results.

Verification (2026-10-19): 17 Compose tests passed, including real temporary dotenv loading, absent/empty rejection for all four required inputs, token scope, command arguments, no secret file, and isolated acceptance configuration. All 26 OpenSpec items passed strict validation. git diff --check, tracked/untracked secret pattern checks and Gitleaks docs/scripts/tests checks passed. Local .env remains ignored and mode 0600; values were preserved without printing. No real Tunnel or production services were started.
