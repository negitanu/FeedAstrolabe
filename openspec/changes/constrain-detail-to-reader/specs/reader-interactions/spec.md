## ADDED Requirements

### Requirement: Detail bounded by the article area
The floating detail SHALL start no higher than the article-area heading or the visible lower edge of the global navigation and reader breadcrumb. Its bottom SHALL remain within the viewport and its contents SHALL scroll independently. Its position SHALL update during scrolling, viewport resizing and sidebar layout changes without shrinking or scrolling the list. The global header SHALL remain clickable above the detail.

#### Scenario: Open detail below upper navigation
- **WHEN** a desktop or mobile user opens a detail or loads a detail URL
- **THEN** the panel starts within the article area, does not overlap the global navigation or breadcrumb, and fits above the viewport bottom

#### Scenario: Scroll or resize
- **WHEN** the user scrolls the list, resizes the window or changes mobile sidebar height
- **THEN** detail bounds follow the visible article area and header navigation remains available
