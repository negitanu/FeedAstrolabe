## Why

Malformed reader feed selectors are silently converted to an unscoped selection, allowing bulk read and refresh requests to affect other subscriptions. Oversized database IDs can also raise server errors instead of rejecting input.

## What Changes

- Reject malformed, non-positive and out-of-range reader IDs before queries or state changes; preserve empty selectors as the explicit all-feeds view.
- Reject invalid or repeated reader conditions and search terms longer than 200 characters before bulk mutations.
- Bound database IDs in URL paths across UI and API endpoints.
- Add reproductions for unintended bulk mutation, unintended collection and invalid-input server errors.

## Capabilities

### New Capabilities
- `input-validation`: Consistent database identifier validation at HTTP boundaries.

### Modified Capabilities
None.

## Impact

Reader UI, subscription API and shared URL routing. No database migration, dependency additions or external deployment changes. Existing unfinished local changes remain intact.
