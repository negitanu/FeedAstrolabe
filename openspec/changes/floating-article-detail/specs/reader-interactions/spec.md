## ADDED Requirements

### Requirement: Floating article detail and original access
The reader SHALL open article details on ordinary selection in a right-aligned floating panel without shrinking or scrolling the retained list. The panel SHALL fit mobile viewports and scroll independently using theme colors. Middle-clicking a card outside its state controls SHALL open its original HTTP(S) URL in a new tab without selecting or marking the article read, including appended cards and mark-read-on-open mode. Missing original URLs SHALL NOT open a tab. The detail title SHALL link to the original in a new tab with noopener noreferrer when available, and remain plain text otherwise. The separate original button and upper previous/count/next navigation SHALL be removed; footer navigation and explicit read-next SHALL remain.

#### Scenario: Open and close floating detail
- **WHEN** a user selects and closes an article on desktop or mobile
- **THEN** list geometry, loaded cards and scroll position remain unchanged and the detail fits the viewport

#### Scenario: Middle click original
- **WHEN** a user middle-clicks an initial or appended card with either read-on-open setting
- **THEN** its original opens in a new tab with no detail selection or read-state mutation

#### Scenario: Simplified detail header
- **WHEN** a detail has an original URL
- **THEN** its title opens that URL in a new tab, no separate original button or upper sequence appears, and footer navigation remains

#### Scenario: Missing original
- **WHEN** an article has no original URL
- **THEN** its detail title is plain text and middle click opens no new tab
