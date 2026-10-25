## MODIFIED Requirements

### Requirement: Floating article detail and original access
The reader SHALL open article details on ordinary selection in a right-aligned floating panel without shrinking or scrolling the retained list. The panel SHALL fit mobile viewports and scroll independently using theme colors. Middle-clicking a card outside its state controls SHALL open its original HTTP(S) URL in a new tab without selecting or marking the article read, including appended cards and mark-read-on-open mode. Missing original URLs SHALL NOT open a tab. The detail title SHALL link to the original in a new tab with noopener noreferrer when available, and remain plain text otherwise. The separate original button and upper previous/count/next navigation SHALL be removed; footer navigation SHALL remain and explicit read-next controls SHALL be removed.

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

### Requirement: Content-first article detail
The detail SHALL present an optional hero image, linked title, timestamp, read/star controls, a horizontal separator, sanitized article description, a horizontal separator, research/tag and evidence controls, and footer previous/count/next navigation in that order. The source/close bar SHALL remain available. All read-next controls SHALL be removed.

#### Scenario: Read before research
- **WHEN** a user opens an article
- **THEN** description precedes research/evidence controls with explicit horizontal separators and no read-next control is displayed


## ADDED Requirements

### Requirement: Mark displayed article as read
The reader SHALL persist read state together with the CSRF-protected visit POST after displaying an article detail, independently of legacy read-on-open preferences. GET requests and middle-click original access SHALL NOT mutate read state. Successful saves SHALL update the matching retained card, detail state controls and scoped counts without closing the detail or losing loaded cards and scroll position. Failed saves SHALL display an error without claiming success. Explicitly marking the displayed article unread SHALL remain possible without immediately marking it read again.

#### Scenario: Select unread article
- **WHEN** a user opens an unread article in any list using mouse, touch or keyboard
- **THEN** the displayed article becomes read, its star remains unchanged, the unread count updates and the detail stays open even in the unread view

#### Scenario: Navigate and fail
- **WHEN** the user navigates to another detail or returns through browser history
- **THEN** the displayed detail is recorded as read; a failed detail fetch or failed visit save does not claim a successful read update

#### Scenario: Explicit unread and middle click
- **WHEN** the user marks the current detail unread or middle-clicks another article
- **THEN** that explicit unread state is preserved and middle-click changes no read state
