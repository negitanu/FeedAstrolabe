## ADDED Requirements

### Requirement: Complete adaptive theme
All application pages SHALL support light, dark and system appearance. System SHALL be the default and follow OS changes. The selected preference SHALL persist in the current browser without requiring JavaScript.

#### Scenario: System color change
- **WHEN** system appearance is selected and OS appearance changes
- **THEN** the page colors and form controls update to the matching theme

#### Scenario: Explicit preference
- **WHEN** the user saves dark or light appearance
- **THEN** subsequent pages and reloads use that preference regardless of OS appearance

#### Scenario: Invalid input
- **WHEN** an unsupported theme or missing CSRF token is submitted
- **THEN** the server rejects the update
