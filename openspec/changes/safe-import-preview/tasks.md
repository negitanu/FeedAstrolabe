## 1. Safety and import model

- [x] 1.1 Add streaming bounded XML validation before RSS/Atom parsing and OPML processing.
- [x] 1.2 Separate ordered OPML parsing, duplicate classification and atomic registration; add signed session-bound expiring confirmation plans.

## 2. Interface

- [x] 2.1 Add native preview, confirm and cancel UI with escaped responsive entries and safe confirmation errors; retain API compatibility.

## 3. Verification

- [x] 3.1 Verify unsafe XML/encoding/shape limits, valid feed compatibility and preservation of prior data.
- [x] 3.2 Verify preview side effects, duplicates, tampering, expiration, cross-session rejection and atomic confirmation in server/browser tests.
- [x] 3.3 Run full regression, record dependency/security checks, document behavior and pass strict OpenSpec/diff validation.
