## ADDED Requirements

### Requirement: Persistent folder disclosure
The reader SHALL provide native keyboard-accessible folder disclosure within each feed source type, including unclassified feeds, showing feed counts and nonzero unread counts. Folder preferences SHALL be independent by source and raw folder name, persist within the same browser/origin, and be cleared by disclosure reset. The selected feed's source and folder SHALL be revealed without overwriting saved closed preferences. Existing source preferences SHALL remain compatible. Storage failure or disabled JavaScript SHALL preserve native disclosure behavior.

#### Scenario: Persist independent folders
- **WHEN** the user closes one folder and navigates or reloads
- **THEN** that folder remains closed while other folders and same-named folders in other sources retain their own state

#### Scenario: Reveal selected feed
- **WHEN** a selected feed belongs to a saved closed folder
- **THEN** its folder and source open for that view, and returning to the overall list restores the saved closed preference

#### Scenario: Reset or unavailable storage
- **WHEN** the user resets disclosure preferences or browser storage is unavailable
- **THEN** folders use native default-open disclosure and remain operable by keyboard/touch

### Requirement: Selectable article layouts
The reader SHALL offer standard, single-line and tile article layouts, preserving article order, filters, pagination, detail/sequence links and explicit read/star POST behavior. Layout selection SHALL persist within the same browser/origin and have accessible selected-state controls. All layouts SHALL fit desktop, narrow detail panes and mobile viewports without horizontal page overflow. Invalid or inaccessible storage SHALL fall back to standard and allow current-page switching. Without JavaScript, standard reading SHALL remain available and inert layout controls SHALL remain hidden. Content sanitization and nonce-scoped CSP SHALL remain unchanged.

#### Scenario: Switch and retain layout
- **WHEN** the user selects line or tiles and navigates through articles, filters or pages
- **THEN** the same layout is restored with unchanged result order and reading state

#### Scenario: Dense and tile presentation
- **WHEN** layouts are shown at desktop or mobile widths with long titles
- **THEN** single-line titles truncate visually, tiles form a responsive grid, and read/star controls and pagination remain usable

#### Scenario: Unavailable or invalid storage
- **WHEN** persisted layout data is invalid or storage cannot be accessed
- **THEN** standard is the initial layout and supported controls still switch the current page without errors
