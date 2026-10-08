## Context

Security news needs vulnerability-centric enrichment with clear separation of severity, observed exploitation and predictions.

Implementation prerequisite: `phase-nine-entities-relations`. Phase nine is archived, pushed and deployed at schema8 with a private pre-migration bundle. This change introduces schema9.

## Goals / Non-Goals

**Goals:**

- Introduce read-only external connector jobs with credential files, cache, cooldown, public pinned transport and provenance.
- Integrate CISA KEV and FIRST EPSS, with authoritative CVE/vendor references.
- Build vulnerability cards linking products, fixes, advisories and manually reviewed PoC references.
- Match watched products with explicit confirmed/possible/unknown applicability; store history and stale-data state.

**Non-Goals:**

Multi-user authorization, Cloudflare activation, live X setup, autonomous exploit execution, and unrelated UI polish. Existing credential files and read-only renderer isolation remain mandatory.

## Decisions

1. Create generic connector contracts (input schema, allowlisted endpoints, identity, cursor, observed time, source version, max bytes, provider budget). Review current official docs/licenses/limits before each adapter; fixtures do not substitute for live acceptance.

2. Represent KEV membership as a dated observation, EPSS as a dated30-day population prediction, and CVSS as source/version-specific severity. Never combine them into an unexplained single certainty score. Missing/stale data is unknown, never safe or zero.

3. Product/version applicability is manual-confirmed or possible until trustworthy version constraints are parsed. Store remediation as attributed vendor claims. PoC collection stores links/metadata only; no automatic clone/execution.

4. Do not expose research notes/attachments to enrichment services. Send only opted-in public identifiers through provider allowlists; cap calls and retries, preserve last good results and log only safe metadata.

Keep Flask/SQLite and small bounded background jobs because current deployment/backup isolation is verified; defer a separate DB/search cluster until measured limits justify it. Prefer additive tables/APIs over repurposing article flags or source identity, preserving existing clients.

## Risks / Trade-offs

- Source records and external APIs change → immutable attributed versions, explicit unknown/stale states, current contract review and retry-safe fixtures.
- Research data may be nonpublic → classification and explicit outbound policy; no secrets in logs/build/Git and no automatic external sending. Classification alone is not per-user access isolation.
- Migrations and file retention may lose research → verified backups, transactional migrations, pinned evidence rules, deletion/rollback tests.
- Scope may expand → deliver listed capability first; refresh this design before implementation if dependencies or contracts change.

## Migration Plan

Before implementing, confirm prerequisite changes and deployed schema, assign the next transactional schema version only if needed, and update maintenance/restore compatibility. Back up DB and any evidence blobs, stop relevant writers for migration, verify existing feed/article IDs and read/star state, then test container recreation. Rollback uses a compatible prior image and pre-change backup.

## Open Questions

Connector/model endpoint quotas, licenses, model runtime choice and required credential files are resolved in the listed research/configuration tasks before enabling that integration. Missing external configuration is reported as unverified, never converted to a successful acceptance check. Initial bounds are design defaults and can be revised with explicit specification updates.

## Final adapter contracts (2026-10-08)

CISA CC0 KEV uses the agency maintained cisagov/kev-data develop JSON mirror at a single fixed raw.githubusercontent.com path, explicitly attributed as a mirror. FIRST public API v1 uses one validated public CVE per request and no credentials; FIRST documents 1000 requests/minute, but our provider budget is 100/day with minimum60-second spacing. Public CVE Services GET /api/cve/{CVE} accepts CVE JSON5.x; containers retain provider attribution and version-specific CVSS/affected versions/references. CVE Terms of Use and copyright links accompany derived cards; FIRST/Empirical Security is attributed. No new library is needed.

Generic jobs accept only registered provider/input contracts plus explicit public-identifier consent; arbitrary endpoints, request bodies, headers and credential values are rejected. Disabled by default, TTL24h (config1h..7d), dailybudget100 (1..1000), sequential batch3, retries3, safe error codes, bounded Retry-After up to7d, public-address validation/TLS DNS pinning, no redirects, identity encoding and5MiB responses. Cache total16MiB, pending100, historical jobs10000, watches100/workspace. Cache replacement occurs only after full adapter validation, preserving last-good data. API/UI expose cooldown, stale/unknown and request metadata without response error bodies. Providers here are public and load no credential files; future authenticated adapters must register a confined credential file contract rather than accepting user headers.

Immutable selected-record observations keep dates, sourceversion, responsehash, evidence anchors, CNA/ADP severity attribution and remediation/reference claims; entire KEV stays only in bounded cache. Missing EPSS is unknown, never zero; old score remains stale on provider failure. Automatic watch matches are possible only for exact casefold product/vendor text; version strings never assert applicability. Confirmed manual applicability requires a same-workspace fixed quotation, expectedrevision and retained assessment history. Watches opt into public CVE requests only; product names/versions/notes/attachments are never transmitted. Refresh evidence is pinned to each active watching workspace so existing keyword watchlists can process it. Manual PoC references require reviewed=true and a fixed quotation; links are metadata only and never fetched/cloned/executed.
