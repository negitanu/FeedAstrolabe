## MODIFIED Requirements

### Requirement: Article browsing
The system SHALL provide a responsive Japanese UI, newest-first article lists, article detail, HTTP(S) original links, configurable pagination of 10–100 articles (default 30) and combined feed, unread, starred and text search filters. Opening a detail page SHALL NOT mutate read state; marking read SHALL require an explicit POST.

#### Scenario: Search and filter
- **WHEN** a user selects unread articles and searches for a title or content fragment
- **THEN** only matching unread articles are listed

#### Scenario: Browse empty list
- **WHEN** no articles match the selected view
- **THEN** a meaningful empty state is displayed

