## Why

Object settings require leaving the working context, while folder ordering has a redundant settings page. Users need direct actions on the folder, feed or registered item they are working with.

## What Changes

- Remove the folder display-order settings page and navigation links; keep durable ordering through sidebar drag and keyboard controls.
- Add folder rename and contextual menus for folders, feeds and registered objects, with visible menu buttons for touch and keyboard access.
- Open existing object editors in one shared dialog, preserving the current reading/research location and validating saves in place.
- Preserve arrow-only folder disclosure, article filtering, theme support and CSRF protection.

## Capabilities

### New Capabilities
- `contextual-library-editing`: Direct sidebar ordering, atomic folder rename and shared contextual object editing.

### Modified Capabilities

None. Earlier unarchived navigation changes are superseded for object editing and folder-order UI.

## Impact

Flask presentation/routes, shared Jinja templates, sidebar scripts/styles, folder transactions, browser and backend regression tests. No new dependencies or database schema changes.
