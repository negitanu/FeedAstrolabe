## ADDED Requirements

### Requirement: Single Tunnel-first Compose deployment
The repository SHALL provide exactly one production Compose file named compose.yml. Ordinary docker compose startup SHALL include web, worker, observer, renderer and cloudflared tunnel, require Cloudflare Access configuration for web and publish no host ports. It SHALL retain the feedastrolabe project name, reader-data and renderer-ipc volumes, bridge networking and renderer network isolation, resource bounds and socket-only mounts.

#### Scenario: Default startup model
- **WHEN** the required Cloudflare settings are supplied and the default Compose model is resolved
- **THEN** all five services are present without overlays or profile activation, web uses Cloudflare authentication and no service exposes a host port

#### Scenario: Preserve the library and isolation
- **WHEN** an existing installation adopts compose.yml
- **THEN** its existing named volumes are reused and renderer has neither application data, credentials nor network access

### Requirement: Optional integrations without overlays
The deployment SHALL support optional X, Ollama cloud and delivery file paths for web/worker through environment settings. Leaving these unconfigured SHALL NOT require optional credential files or activate integrations. Configured files SHALL retain existing owner-only file validation and remain outside images and tracked source.

#### Scenario: Base installation
- **WHEN** only the Tunnel credential and required Access settings are configured
- **THEN** the model requires no X, Ollama or delivery credential mount

#### Scenario: Configure an integration
- **WHEN** the operator supplies an app-owned private-volume credential file and its container path
- **THEN** web and worker can use it without a second Compose file

### Requirement: Isolated deployment verification
Container acceptance scripts SHALL use compose.yml with temporary test-only overrides and *-verify project names, ignore operator deployment settings, disable the tunnel and avoid published host ports. They SHALL preserve production volumes and credentials.

#### Scenario: Verify without Cloudflare credentials
- **WHEN** acceptance scripts are run for an isolated verification project
- **THEN** synthetic settings and a temporary unused Tunnel secret resolve the model and only the targeted local test services start

#### Scenario: Reject production project
- **WHEN** a verification script is given a project name without the -verify suffix
- **THEN** it refuses before starting or modifying any container
