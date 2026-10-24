## ADDED Requirements

### Requirement: Consistent task navigation
The application SHALL expose 読む・集める・調べる・まとめる・設定 on every HTML screen, with the current area indicated and all five choices visible without opening a menu on mobile.

#### Scenario: Move between areas
- **WHEN** a user opens a reader, research, settings, or detail screen
- **THEN** the same five destinations are available and the active area is identified

### Requirement: Settings reachable within three clicks
All existing UI settings SHALL be reachable from any screen within three clicks, counting navigation and disclosure expansion but excluding typing, scrolling, saving, and confirmation. Global settings and individual feeds, topics, workspaces, and watches SHALL have direct destinations in the settings index. Environment-only configuration SHALL be clearly described as configured outside the UI.

#### Scenario: Open global settings
- **WHEN** a user selects 設定 and then a settings item
- **THEN** the corresponding form is visible with at most one further disclosure interaction and without requiring JavaScript

#### Scenario: Open an individual setting
- **WHEN** a user selects 設定 and then a registered feed, workspace, or watch
- **THEN** the relevant edit controls are reachable within the remaining one click and no pagination is required in the index

### Requirement: Guided workflows
Task hubs SHALL describe the sequence to collect information, research it, and produce a report, with links to the screens needed for each step.

#### Scenario: Begin collecting
- **WHEN** a user selects 集める
- **THEN** RSS, SNS, and page collection each show where to register, configure, and read results

### Requirement: Preserve existing actions
Navigation changes SHALL preserve existing POST endpoints, CSRF, explicit outbound approvals, stored data, and legacy settings URLs.

#### Scenario: Follow a legacy settings link
- **WHEN** an existing settings URL is opened
- **THEN** its forms remain available and saving continues through the existing protected endpoint
