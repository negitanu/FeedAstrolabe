## ADDED Requirements

### Requirement: Browser-local disclosure state
The reader SHALL save explicit open/close choices for RSS/Atom, X, Mastodon and page groups in the current browser and restore them across reader navigation. Saved values SHALL contain only a version and booleans for known types, without article content, feed IDs or credentials. Missing, invalid or inaccessible storage SHALL preserve the native server-rendered defaults and controls.

#### Scenario: Return to reader
- **WHEN** a user closes one type, opens another and navigates between article details, filters and the library
- **THEN** those saved choices are restored independently in that browser

#### Scenario: Storage unavailable
- **WHEN** storage is denied, corrupted or scripting is disabled
- **THEN** feed links and native keyboard disclosure controls remain usable with the existing defaults

### Requirement: Selected-feed visibility and reset
The reader SHALL open the selected feed type during restoration without overwriting its saved state. It SHALL provide a reset control that clears disclosure preferences and restores the existing defaults while preserving the current reader filters and article state.

#### Scenario: Temporary selected-type override
- **WHEN** a saved-closed type is selected through a feed link and the user returns to the general reader without toggling it
- **THEN** it opens on the feed page and remains saved-closed on the general reader

#### Scenario: Reset preferences
- **WHEN** the user activates the disclosure reset control
- **THEN** saved disclosure values are cleared and the current page returns to its default group layout without changing reader filters, read states or stars

### Requirement: Restricted script execution
The reader SHALL authorize only its enhancement script with a fresh per-response CSP nonce. Other pages SHALL retain script-src 'none'. Article scripts and inline event handlers SHALL remain blocked or removed.

#### Scenario: Safe enhancement
- **WHEN** a reader page loads with an article containing script tags or event handlers
- **THEN** the trusted enhancement runs and the article payload does not execute

#### Scenario: Independent nonces
- **WHEN** two reader responses are fetched
- **THEN** their script elements match their own CSP nonces and the nonces differ
