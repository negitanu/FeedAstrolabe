## ADDED Requirements

### Requirement: Isolated desktop lifecycle
The desktop SHALL start one authenticated loopback Go child and close it on exit; the renderer SHALL have no Node.js access or API credential.

#### Scenario: Start and close
- **WHEN** the desktop starts and then quits
- **THEN** the UI becomes ready and the child terminates

#### Scenario: Reject unauthorized access
- **WHEN** a client supplies no valid bearer or sends an Origin header
- **THEN** the API rejects the request

### Requirement: Restricted renderer bridge
The desktop SHALL allow only named application operations from its own renderer and SHALL deny navigation, new windows and permission requests.

#### Scenario: External content
- **WHEN** an article contains HTML scripts or remote resources
- **THEN** it is displayed as inert text

#### Scenario: External link
- **WHEN** the user opens a valid HTTP(S) original article
- **THEN** the system browser opens the URL
