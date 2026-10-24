## ADDED Requirements

### Requirement: Folder-first feed navigation
The reader SHALL display folders as the top-level feed groups, with all feed kinds within each folder and a source label on each feed. Counts SHALL aggregate across those feeds. Exact folder names, including empty and literal unclassified names, SHALL retain distinct identities. Native disclosure, persistent preferences, selected-feed reveal, reset and escaped names SHALL remain available. Valid previous source/folder preferences SHALL migrate conservatively so new or mixed-kind groups are visible.

#### Scenario: Mixed folder
- **WHEN** RSS, X and other feeds share a folder
- **THEN** a single folder group displays all of them with source labels and combined counts

#### Scenario: Migrate disclosure
- **WHEN** only previous per-source folder preferences exist
- **THEN** the merged folder is closed only if all its current kinds were saved closed, and explicit new folder choices persist independently

### Requirement: Compact themed reader
The reader SHALL present project/tag/search fields and article actions/layout choices in aligned theme-consistent controls and reduce reader-only spacing to increase visible content. It SHALL preserve filters, pagination, article actions, accessible labels, visible focus and usable mobile targets. Mobile navigation SHALL have a labeled native disclosure and default to collapsed when JavaScript is available. Desktop navigation SHALL remain visible. Without JavaScript the navigation and standard reading SHALL remain usable. All modes SHALL avoid horizontal page overflow, including long names and detail panes.

#### Scenario: Dense desktop view
- **WHEN** the same populated reader is compared at 1440x900 before and after
- **THEN** articles start higher and more complete cards fit in the viewport with aligned project/tag/search controls

#### Scenario: Mobile reading
- **WHEN** the reader opens at 390x844
- **THEN** the user can see articles in the first viewport and open navigation with its labeled summary

#### Scenario: Maintain operations
- **WHEN** users search, select projects/tags, change layout, navigate details or submit read/star actions
- **THEN** their result scopes and persisted reading state retain the existing behavior
