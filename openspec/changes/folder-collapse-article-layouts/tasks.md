## 1. Reader controls

- [x] 1.1 Add native folder disclosure/counts and browser persistence with selected reveal/reset and safe fallback.
- [x] 1.2 Add accessible standard/line/tile controls, persistent layout script and responsive styles.

## 2. Verification and documentation

- [x] 2.1 Add meaningful render/browser tests for identities, persistence, actions, filters, fallback and narrow layouts; visually inspect desktop/mobile screenshots.
- [x] 2.2 Update reader documentation, run full regression and strict OpenSpec/secret/diff checks and record results.

Verification: all 397 regression tests passed with real Chromium enabled and no skips. Existing source preferences are retained even if that source temporarily has no subscriptions. Desktop/mobile/detail screenshots were inspected; documentation is in docs/verification-folder-layouts.md. All 28 OpenSpec items, diff whitespace checks, tracked/untracked secret checks and Gitleaks source/tests/docs checks passed. No production data or Tunnel was used or restarted.
