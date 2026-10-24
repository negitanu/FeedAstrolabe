## Purpose

Provide the implemented reader-interactions capability from reader-platform-provider-refresh.

## Requirements

### Requirement: Persistent disclosure without reset control
The reader SHALL remove the disclosure-reset button and its event handling while retaining stored folder disclosure preferences and arrow-only toggling.

#### Scenario: Existing collapsed folder
- **WHEN** a user revisits a folder that was collapsed before the update
- **THEN** it remains collapsed, no reset control is offered, and selecting its name displays articles without expanding it

### Requirement: Pause and resume subscriptions in context
Every supported feed kind SHALL offer 購読停止 or 購読再開 through its right-click and ellipsis menus. A stop SHALL disable subsequent scheduled and user-triggered collection for that feed, preserve its registration and historical data, and exclude it from global manual refresh. Resume SHALL restore eligibility using the saved interval and source configuration. Already running requests MAY complete; the stop SHALL NOT be presented as cancellation of an in-flight network request.

#### Scenario: Stop without deleting
- **WHEN** a user stops an enabled RSS, supported SNS or page feed
- **THEN** it remains readable, its articles/read/star values and source settings are unchanged, and no new collection job is dispatched for it

#### Scenario: Resume
- **WHEN** a user resumes a stopped feed
- **THEN** it becomes eligible for the normal scheduler, the menu changes to 購読停止 and the action itself does not fetch articles

#### Scenario: Queued collection and stopped SNS automation
- **WHEN** a feed is stopped while collection or automatic extraction work is queued
- **THEN** queued work is prevented from starting or is cancelled, and workers recheck eligibility before outbound execution

#### Scenario: Unsupported source and validation
- **WHEN** resume is attempted for retired X collection, a missing feed, invalid values, duplicate parameters or a request without CSRF
- **THEN** the mutation is rejected and other settings or feeds are not changed

### Requirement: Prominent scoped bulk read
The bulk-read control SHALL use the exact visible label 全て既読 and primary theme-aware styling. It SHALL mark all articles in the active filter as read, including articles not yet rendered.

#### Scenario: Bulk read before all cards load
- **WHEN** a user chooses 全て既読 in a folder/search/unread/workspace/tag filter
- **THEN** all matching articles become read, articles outside that filter keep their state, and loaded content is reconciled with the result

#### Scenario: Light dark and system appearance
- **WHEN** the app uses light, dark or system appearance
- **THEN** the button remains visually prominent with visible keyboard focus and text contrast of at least 4.5:1
