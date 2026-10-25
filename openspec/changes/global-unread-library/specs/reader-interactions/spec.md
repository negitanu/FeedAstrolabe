## ADDED Requirements

### Requirement: Global unread library entry
The library 未読 navigation SHALL open unread articles across the entire library, clearing folder, feed, search and other selected scopes. Its badge SHALL always show the global unread article count, including after detail visit updates. A folder- or feed-scoped unread view SHALL NOT mark the global unread entry as active. Explicit folder and search filters SHALL remain available after entering global unread.

#### Scenario: Leave a selected folder
- **WHEN** a user selects 未読 while viewing a folder, feed or scoped search
- **THEN** unread articles from all folders including unclassified feeds appear, the URL contains no previous scope and the global unread entry is active

#### Scenario: Consistent unread badge
- **WHEN** a user views a folder and opens one of its unread articles
- **THEN** the badge decreases from the library-wide unread count while folder result counts remain scoped

#### Scenario: Scoped unread and bulk read
- **WHEN** a user explicitly chooses a folder within unread or marks the selected folder read before choosing global 未読
- **THEN** the folder retains its filter while selected, and choosing global 未読 still includes remaining unread articles outside that folder
