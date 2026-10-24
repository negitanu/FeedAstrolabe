## Why
UTC-only timestamps make daily use in Japan difficult. Users need a persistent UTC/JST display choice.
## What Changes
- Add a shared display timezone setting with UTC default and JST option.
- Format UI timestamps consistently while keeping storage, API timestamps, exports and UTC query input unchanged.
## Capabilities
### New Capabilities
- `display-timezone`: Persistent UTC/JST display preference.
### Modified Capabilities
None.
## Impact
SQLite schema14, settings UI/API, shared Jinja formatter, timestamp templates, OpenAPI and tests. No new dependency.
