## ADDED Requirements

### Requirement: Direct persistent ordering
The application SHALL allow folder ordering using mouse and touch drag handles, persist the final position in the database, and retain keyboard and no-JavaScript alternatives.

#### Scenario: Drop and reload
- **WHEN** a folder is dragged to a different position and dropped
- **THEN** the order is saved and remains visible after reloading and in another session

#### Scenario: Cancel or unchanged drag
- **WHEN** a drag is cancelled or ends in its original position
- **THEN** no order mutation occurs

#### Scenario: Keyboard alternative
- **WHEN** JavaScript is unavailable
- **THEN** up, down and specified position controls still save the order
