## ADDED Requirements

### Requirement: Unified reproducible lean builds
The repository SHALL provide exactly one requirements.txt containing each pinned Python dependency once and exactly one Dockerfile with app and renderer targets. Compose SHALL select the appropriate target per service. App SHALL exclude test and browser packages; renderer SHALL include the required headless Chromium shell without a full Chromium installation. Existing features, pinned versions, non-root operation and renderer isolation SHALL be retained.

#### Scenario: Build ordinary application
- **WHEN** the default Dockerfile target or app Compose services are built
- **THEN** the app dependencies use the unified pins and pytest, Playwright and browser binaries are absent

#### Scenario: Build renderer
- **WHEN** the renderer target is built
- **THEN** headless observation and text/Markdown/PDF extraction work with headless shell while full Chromium and test packages are absent

#### Scenario: Install development dependencies
- **WHEN** the unified requirements file is installed for development
- **THEN** the existing pinned app, browser and test dependency set is available without the deleted requirements files

#### Scenario: Verify shrink
- **WHEN** images are compared against the previous verified images on the same architecture and base
- **THEN** both image sizes and their reduction are recorded after functional and isolation checks
