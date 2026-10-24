## Context

The server already owns validation and all object settings forms. Sidebar ordering is persistent, but duplicated by a settings page. Navigation and folder disclosure are independent.

## Goals / Non-Goals

**Goals:** Direct manipulation and contextual editing throughout registered feeds, workspaces and watches; touch/keyboard parity; preserve reading state and existing validation.

**Non-Goals:** Change global integration configuration, introduce a client framework, or alter collection/data schemas.

## Decisions

- Reuse object form partials in a shared native dialog requested with a context-editor header. Normal links retain a no-JavaScript fallback. Existing save endpoints and CSRF tokens remain authoritative. Inline errors retain entered values; successful saves refresh the editor and refresh the underlying page on close.
- Use one shared menu controller with delegated target detection, arrow-key navigation, Escape dismissal and visible ellipsis controls. Explicit metadata identifies sidebar folders/feeds; registered-object links use a centralized route mapping. Ordinary navigation remains unchanged.
- Remove the order page and its links. Pointer/touch drag and keyboard handles stay in the sidebar; legacy GET redirects to the reader.
- Rename all members of an exact folder identity atomically under the collection lock, updating persisted ordering in the same transaction. Reject collisions rather than implicitly merging folders; preserve article IDs, read/star state and disclosure state. Unclassified (empty name) can be named.
- Keep global settings separate from contextual object editing, and retain concise safety-critical deletion and external-sharing information.

## Risks / Trade-offs

- Failed/ambiguous saves → visible error without silently losing input, no automatic POST retry.
- Stale folder identity → return 404; duplicate name → validation error without mutation.
- Editor accessibility → native modal focus trap, explicit close button, keyboard menu and touch buttons; test desktop/mobile and both themes.
- Save changes parent membership → validate return destination on close; fall back to reader if removed.

## Migration Plan

No schema migration. Run backend and browser regression tests, rebuild/restart Compose services, verify health and deployed assets. Existing persistent order is retained.
