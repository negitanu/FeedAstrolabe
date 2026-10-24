## Context

The server-rendered reader has source-type details, browser-local persistence under a versioned key, nonce-scoped scripts and one shared article DOM. Folder labels are currently static. Reading actions and filters already work through links/forms.

## Goals / Non-Goals

**Goals:** Independent source/folder disclosure and three useful layouts, keyboard/touch controls, persistent browser choices, graceful storage failure and mobile/detail responsiveness.

**Non-Goals:** Feedly integration, external thumbnails, data migrations, new dependencies, changing sorting/filtering or article state.

## Decisions

- Render native nested details for folders, including unclassified feeds; summarize feed count and nonzero unread count. Identity is source type plus the raw escaped folder name, keeping identical folder names in different sources and empty versus literal unclassified names independent.
- Extend existing disclosure handling with a separate versioned folder storage key. Bound stored JSON, validate boolean entries, restrict restoration to visible groups and prune stale keys on writes. Preserve the existing source storage format and selected-group override; reset clears both disclosure keys. Default folders open, and selection reveals its parent source/folder without overwriting the user's saved closed preference.
- Standard/line/tiles controls alter only the existing article list's data attribute. A small nonce-authorized external script stores a validated layout choice in a separate versioned localStorage entry. Keep all article links, POST actions, filter URLs and pagination identical. No HTML from storage is inserted.
- Use grid-based one-line rows with ellipsis and retained actions, and responsive text tiles using existing excerpts. Keep metadata where space permits, constrain narrow layouts and give pagination/empty state full grid width. No remote image requests are introduced.
- JavaScript-disabled clients keep native folder/source disclosure and standard article layout; hide unusable layout controls until the script initializes. Denied storage still allows switching within the current page.

## Risks / Trade-offs

- Nested toggle events may overwrite source preferences → bind each details element directly and track restored/reset state before queued toggle events arrive.
- Long/unusual folder names, empty folder identities and malformed storage → escaped data attributes, JSON tuple identities, bounded validated Maps and browser tests.
- Dense rows may overflow when detail is open or on mobile → responsive container styles, real measured browser geometry and screenshots at desktop/mobile sizes.
- Layout persistence is browser/origin specific → document scope; no change to shared library preferences.

## Migration Plan

Existing source disclosure preferences remain compatible. Folders default open and layout defaults to standard. New settings are browser-only and removable with disclosure reset or standard layout selection. No server data migration is required.
