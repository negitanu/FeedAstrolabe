## ADDED Requirements
### Requirement: Feed type disclosure
The sidebar SHALL show independently collapsible RSS/Atom, X, Mastodon and page observation groups for existing subscriptions, with folder grouping, subscription counts and unread totals.
#### Scenario: Mixed feeds
- **WHEN** subscriptions have different types and folders
- **THEN** each subscription appears exactly once within its type and folder and empty types are omitted
#### Scenario: Open and close
- **WHEN** a user activates a type summary by mouse, touch or keyboard
- **THEN** its feed links expand or collapse independently without requiring JavaScript
### Requirement: Preserve current feed visibility
The sidebar SHALL keep existing feed navigation and selected styling. It SHALL initially open all groups in the general view and only the selected type when viewing a feed.
#### Scenario: Selected feed
- **WHEN** a user navigates to a feed
- **THEN** its type opens and its link remains highlighted while other types start collapsed
#### Scenario: Empty library
- **WHEN** no subscriptions exist
- **THEN** the existing empty-state and add-feed control remain available

### Requirement: Hide empty unread badges
The sidebar SHALL display unread count badges for feeds and source types only when the count is greater than zero.
#### Scenario: No unread articles
- **WHEN** a feed or source type has zero unread articles or no articles
- **THEN** its unread badge is absent
#### Scenario: New unread articles
- **WHEN** a feed or source type has unread articles
- **THEN** its unread badge shows the positive count
