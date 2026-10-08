## Why

Security news needs vulnerability-centric enrichment with clear separation of severity, observed exploitation and predictions.

## What Changes

- Introduce read-only external connector jobs with credential files, cache, cooldown, public pinned transport and provenance.
- Integrate CISA KEV and FIRST EPSS, with authoritative CVE/vendor references.
- Build vulnerability cards linking products, fixes, advisories and manually reviewed PoC references.
- Match watched products with explicit confirmed/possible/unknown applicability; store history and stale-data state.

## Capabilities

### New Capabilities

- `security-intelligence`: 脆弱性・セキュリティ情報連携.

### Modified Capabilities

None. Additive capabilities preserve existing RSS/SNS/page and API contracts.

## Impact

Flask/SQLite persistence, Japanese responsive UI, scoped APIs, background jobs and operations documentation. Adds schema v9 after verified/deployed v8 entities and relations. All new providers default disabled; existing collection contracts remain unchanged.
