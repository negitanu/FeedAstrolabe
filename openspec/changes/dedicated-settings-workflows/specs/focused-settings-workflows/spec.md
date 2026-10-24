## ADDED Requirements
### Requirement: Dedicated and truthful settings destinations
Every settings index item SHALL open a page whose primary heading and selected navigation identify that setting. Global and individual settings SHALL use dedicated URLs without relying on fragments in unrelated feature screens.
#### Scenario: OpenRouter destination
- **WHEN** a user chooses OpenRouter from settings
- **THEN** /settings/openrouter opens with the OpenRouter heading and fields, settings selected, and no SNS registration or results forms
#### Scenario: Other settings
- **WHEN** a user chooses models, connectors, delivery, backup or an individual feed/watch/workspace
- **THEN** only the selected setting is presented in the settings shell with a route back to the index and to its associated work
### Requirement: Save continuity and validation
Successful settings updates SHALL return to the same dedicated setting with feedback. Invalid OpenRouter input SHALL preserve user-entered values without saving partial changes or enabling external execution.
#### Scenario: Save and correct OpenRouter
- **WHEN** valid or invalid values are submitted
- **THEN** the user stays in OpenRouter settings, sees feedback, and valid saved values or invalid attempted values respectively
### Requirement: First use and task completion
Information source registration SHALL have a separate page per source type with prerequisites and the next step after registration. Empty work screens SHALL provide a concrete starting action. Research workflows SHALL carry the selected workspace and provide named choices where IDs were required to start a watch.
#### Scenario: First SNS investigation
- **WHEN** a new user starts SNS collection from the collection hub
- **THEN** they can register a topic, see its result page, collect posts, edit that topic and return to results without encountering unrelated model forms
### Requirement: Semantic and regression verification
Verification SHALL cover desktop/mobile, navigation identity, absence of unrelated forms, successful and invalid saves, CSRF, first-use workflows, and regression tests after final changes.
#### Scenario: Settings in three clicks
- **WHEN** a user starts from any feature page
- **THEN** all UI settings are available in at most three navigation/disclosure actions with the expected primary heading visible
