## Purpose

Provide the verified phase-one article-reader capability.

## Requirements

### Requirement: Article browsing
The system SHALL provide a responsive Japanese UI, newest-first article lists, article detail, HTTP(S) original links, pagination of 30 articles and combined feed, unread, starred and text search filters. Opening a detail page SHALL NOT mutate read state; marking read SHALL require an explicit POST.

#### Scenario: Search and filter
- **WHEN** a user selects unread articles and searches for a title or content fragment
- **THEN** only matching unread articles are listed

#### Scenario: Browse empty list
- **WHEN** no articles match the selected view
- **THEN** a meaningful empty state is displayed

### Requirement: Persistent reading state
The system SHALL persist individual read/unread and starred/unstarred state and allow marking all articles in the current filter read.

#### Scenario: Persist state
- **WHEN** an article is marked read and starred and the application restarts
- **THEN** both states remain unchanged

#### Scenario: Scoped bulk read
- **WHEN** a filtered view is marked read
- **THEN** only articles matching that view become read
