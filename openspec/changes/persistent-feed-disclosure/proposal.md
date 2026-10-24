## Why

Feed type disclosures reset whenever users open an article, change filters or return to the reader. Remembering those choices makes long subscription lists easier to use across visits.

## What Changes

- Remember each feed type's open/closed state in the current browser and restore it on reader navigation.
- Keep the selected feed type visible without overwriting its saved preference during restoration.
- Offer a reset to the existing default layout and retain native disclosures when scripting or storage is unavailable.
- Permit only the reader's nonce-authorized enhancement script while keeping other pages script-free.

## Capabilities

### New Capabilities
- `persistent-feed-disclosure`: Browser-local reader layout preferences with selected-feed visibility, reset and safe fallback.

### Modified Capabilities
None. The existing server-rendered and no-script disclosure defaults remain available.

## Impact

Reader template, one small static script and reader-only CSP nonce. No database migration, API change or third-party dependencies.
