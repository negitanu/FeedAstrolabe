## MODIFIED Requirements

### Requirement: Detailed literal search form
The normal reader SHALL expose title/body/both, additional any-of phrases, exclusion phrases, a publication calendar-date range and multiple information sources in a keyboard/touch-operable form. Any-of and exclusion controls SHALL be single-line inputs accepting comma-separated phrases with CSV quoting. Existing newline-based search URLs SHALL retain their meaning. Sources SHALL use a collapsed dropdown containing checkboxes with multiple selections, preserved submitted selections and no-script access. Existing q semantics SHALL remain a single literal phrase. Groups SHALL combine with AND, any-of phrases with OR and exclusions with NOT. Dates SHALL use the library display timezone and exclude unknown original publication times. All request values SHALL be bounded and duplicate/conflicting or invalid parameters rejected. Details, mutations and no-script access SHALL preserve the complete condition.

#### Scenario: Combine conditions
- **WHEN** a user searches body text with any-of phrases, excludes a phrase and selects a date range and two sources
- **THEN** only articles satisfying the complete condition appear, including every continuation batch and bulk read

#### Scenario: Invalid conditions
- **WHEN** a date is invalid or reversed, source is missing, scope is unknown or parameters conflict
- **THEN** no mutation occurs and an explanatory error is shown

#### Scenario: Compact fields and dropdown
- **WHEN** a desktop or mobile user expands detailed search
- **THEN** phrase controls occupy one input line, sources precede search scope in DOM and visual order, all six controls share one row when the advanced search area is at least 600 CSS pixels wide, source choices appear only after opening the dropdown, and selected sources survive search and subsequent reader actions

#### Scenario: Legacy and literal punctuation
- **WHEN** legacy newline parameters or CSV input with quoted commas and quotes are used
- **THEN** the original literal phrases and bounds are preserved and conflicting input forms are rejected
