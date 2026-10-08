## ADDED Requirements

### Requirement: Isolate browser execution
Docker rendering SHALL run without networking, database or credential mounts in a nonroot read-only bounded service, and each browser job SHALL terminate with all descendants after45s.

#### Scenario: Browser bypass attempt
- **WHEN** page code tries direct networking outside brokered HTTP
- **THEN** the Docker network boundary prevents external connections

### Requirement: Broker bounded public requests
The broker SHALL accept only same-origin GET, validate and pin public DNS addresses, reject redirects/authentication, and enforce50 requests,20MiB aggregate,5MiB/request and30s network deadline. Renderer SHALL block service workers, WebSockets, media, downloads and subframes.

#### Scenario: Private DNS or redirect
- **WHEN** a request resolves privately or returns a redirect
- **THEN** it is rejected before private access or redirect follow-up

#### Scenario: Cross-origin resource
- **WHEN** JS requests another origin or attempts POST
- **THEN** the broker refuses the request without sending credentials or request bodies

### Requirement: Safe IPC and errors
Renderer messages SHALL be bounded and validated, and only selected text or fixed error codes SHALL return to the parent. Failure SHALL not print page content, URLs with query values, credentials or raw browser exceptions.

#### Scenario: Malformed renderer message
- **WHEN** the renderer sends invalid or oversized IPC
- **THEN** the observation fails safely without updating its baseline
