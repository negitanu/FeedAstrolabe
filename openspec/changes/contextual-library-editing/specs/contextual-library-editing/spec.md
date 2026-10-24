## ADDED Requirements

### Requirement: Direct folder ordering
The UI SHALL expose persistent folder ordering in the sidebar and SHALL remove the standalone display-order page and links.

#### Scenario: Pointer or keyboard reorder
- **WHEN** a user drags a sidebar folder handle or moves it with arrow keys
- **THEN** the order is saved across reloads and sessions without navigating away or changing disclosure state

#### Scenario: Cancel or failed save
- **WHEN** a drag is cancelled or a save fails
- **THEN** the prior order remains visible and failures are announced

### Requirement: Contextual object editing
Folders, feeds and registered workspaces/watches SHALL offer contextual actions through right-click and an accessible menu control. Object settings SHALL open in a shared dialog in the current screen.

#### Scenario: Edit from the reader
- **WHEN** a user chooses feed settings from its menu
- **THEN** settings open without navigation, saves use existing validation, and closing restores the reading context

#### Scenario: Touch and keyboard
- **WHEN** a user taps the menu button or invokes Shift+F10 and navigates with arrows
- **THEN** the same actions are available and Escape dismisses the menu or dialog with focus restored

#### Scenario: Invalid editor input
- **WHEN** a save fails validation or the network fails
- **THEN** an error is displayed and entered values remain available for correction

### Requirement: Atomic folder rename
Folder rename SHALL update all member feeds and persistent order atomically while preserving article and disclosure state. Duplicate, invalid or missing identities SHALL NOT mutate data.

#### Scenario: Rename selected folder
- **WHEN** a user renames the currently selected folder
- **THEN** the article list remains scoped to the renamed folder, its order and open/closed state are retained, and read/star values are unchanged

#### Scenario: Name collision
- **WHEN** the destination name already identifies another folder
- **THEN** the operation reports an error without merging folders

### Requirement: Independent reading and disclosure
Folder selection SHALL display that folder's articles; only the disclosure arrow or its keyboard equivalent SHALL toggle the sidebar folder.

#### Scenario: Context action on collapsed folder
- **WHEN** a user opens a context menu or edits a collapsed folder
- **THEN** it remains collapsed and article navigation continues to work
