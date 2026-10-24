## ADDED Requirements

### Requirement: Content-first article detail
The detail SHALL present an optional hero image, linked title, timestamp, read-next/read/star controls, a horizontal separator, sanitized article description, a horizontal separator, research/tag and evidence controls, and footer previous/count/next navigation in that order. The source/close bar SHALL remain available. The duplicate footer read-next control SHALL be removed.

#### Scenario: Read before research
- **WHEN** a user opens an article
- **THEN** description precedes research/evidence controls with explicit horizontal separators and the only read-next control precedes description

### Requirement: Optional bounded hero image
The reader SHALL attempt to obtain an Open Graph or Twitter Card image from the saved original URL without delaying the detail HTML response. It SHALL render a successfully loaded image before the title at 480 CSS pixels, constrained by available width. Missing or failed images SHALL leave no visible placeholder. Original page and image requests SHALL reuse public-address validation, DNS pinning, redirect validation and time/size limits. Only PNG, JPEG, GIF and WebP image signatures SHALL be served through a same-origin article endpoint; SVG and non-image responses SHALL be rejected. Successes and failures SHALL be cached with bounded entries and lifetime. Existing CSP and access controls SHALL be preserved.

#### Scenario: Image metadata exists
- **WHEN** the original page declares a usable og:image or twitter:image including relative URLs
- **THEN** the image is fetched with the existing network protections and appears above the title without overflowing mobile viewports

#### Scenario: Image unavailable or unsafe
- **WHEN** the article has no URL, metadata, a successful image response, or points to a blocked address or unsupported format
- **THEN** the article remains readable and no broken-image placeholder appears
