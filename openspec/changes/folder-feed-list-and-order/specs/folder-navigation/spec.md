## ADDED Requirements
### Requirement: Folder article list
Selecting a folder name SHALL open the chronological article list from exactly the feeds in that folder. Unread, starred, search, workspace, tag, pagination, article navigation and read-all operations SHALL preserve the folder scope. Folder selection and disclosure SHALL be independent. Selecting a folder or a feed SHALL preserve its saved disclosure state without automatically expanding it. Empty-folder identity SHALL remain distinct from a folder literally named 未分類.
#### Scenario: Choose and open a folder
- **WHEN** a user selects a folder name on desktop or mobile
- **THEN** the folder article list opens with its name and articles only from its member feeds, and the selected folder is identified in the sidebar
#### Scenario: Toggle without navigation
- **WHEN** a user activates the folder disclosure arrow by pointer or keyboard
- **THEN** only the child feed visibility changes and the current URL remains unchanged
#### Scenario: Missing and special folders
- **WHEN** the user opens a missing folder, or a folder with empty or HTML-like characters in its name
- **THEN** missing folders return 404 and existing names match exactly and render as escaped text
### Requirement: Persistent arbitrary folder order
Users SHALL be able to move any folder up, down or to any valid position, including the uncategorized folder. The order SHALL persist across reloads and sessions and SHALL be shared by the sidebar and the ordering screen. Newly added folders SHALL appear after saved folders; removed folders SHALL not appear.
#### Scenario: Move and reload
- **WHEN** a user changes a folder position and reloads in another session
- **THEN** the chosen order is preserved in the sidebar and ordering screen without changing feed membership or article state
#### Scenario: No JavaScript and touch input
- **WHEN** a user operates folder selection or ordering with JavaScript disabled, a keyboard, or a mobile touch screen
- **THEN** they can complete the operation using visible links and form controls
#### Scenario: Invalid mutation
- **WHEN** ordering is submitted without CSRF, with an unknown folder or an invalid position
- **THEN** the request is rejected or shows a clear validation message and no partial order is saved
### Requirement: Folder regression verification
Verification SHALL cover folder identity, arbitrary saved order, database migration and backup restoration, desktop/mobile workflows, and regression of article read/star/search and disclosure persistence.
#### Scenario: Deploy verified changes
- **WHEN** the change is delivered
- **THEN** final regression tests and strict specification validation pass and rebuilt containers serve the new folder screens

### Requirement: Scoped reading continuity
Folder scope SHALL remain exact across empty names, Unicode names and all article interactions.
#### Scenario: Read and advance
- **WHEN** the user opens an article and reads the next item in a folder
- **THEN** the successor and return list remain within that folder
#### Scenario: Bulk read
- **WHEN** the user marks the currently filtered folder articles read
- **THEN** only articles matching that folder and the other active filters are updated
