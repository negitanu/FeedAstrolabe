## ADDED Requirements
### Requirement: Persistent display timezone
The system SHALL allow UTC or Asia/Tokyo (JST) through settings UI and scoped settings API, default existing libraries to UTC, and reject unsupported values atomically.
#### Scenario: Set JST
- **WHEN** the user saves Asia/Tokyo and reloads settings
- **THEN** JST remains selected
#### Scenario: Invalid timezone
- **WHEN** an unsupported timezone is submitted alongside other changes
- **THEN** all settings remain unchanged
### Requirement: Format UI timestamps without changing instants
The system SHALL render UI timestamps using the selected timezone and label, keep database/API/export timestamps and UTC date inputs unchanged, and safely handle missing dates.
#### Scenario: Date rollover
- **WHEN** JST is selected and an article has UTC timestamp 2026-10-08 18:30:00
- **THEN** its display is 2026-10-09 03:30 JST and stored/API timestamp remains unchanged
#### Scenario: Switch back
- **WHEN** UTC is selected again
- **THEN** UI timestamps display their original UTC instant
#### Scenario: Missing timestamp
- **WHEN** a timestamp is absent
- **THEN** the UI displays its missing-value label without a misleading timezone suffix
