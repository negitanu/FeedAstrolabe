## ADDED Requirements

### Requirement: Consistent restrained interface
Shared layouts SHALL use semantic color tokens and concise labels without decorative English subtitles or redundant instructions. Safety notices, errors and essential field guidance SHALL remain available.

#### Scenario: Navigate settings
- **WHEN** a user opens a setting from any page
- **THEN** its named controls are available within three clicks and share the common layout and theme

#### Scenario: Narrow viewport
- **WHEN** pages are viewed on a mobile screen in either theme
- **THEN** navigation, controls and content remain readable without page-level horizontal overflow
