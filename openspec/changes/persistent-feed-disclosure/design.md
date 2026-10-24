## Context

The reader has native details/summary feed type groups. Each response restores server defaults (all groups open on the general view; only the selected type open on a feed view). The application forbids scripts through CSP.

## Goals / Non-Goals

**Goals:** Remember layout across navigation and browser restarts; expose the selected feed; preserve keyboard, mobile and no-script operation; retain the existing content safety boundary.

**Non-Goals:** Shared account settings, database/API changes, external scripts and storage of article text or credentials.

## Decisions

- Progressive enhancement with a small same-origin external script. Store only booleans for four known feed types under a versioned localStorage key. Validate storage contents and tolerate unavailable/corrupt storage.
- Restore saved values, then force the currently selected type open for this page. Track the resulting initial state before handling native toggle events so restoration cannot overwrite saved choices; later explicit toggles are saved.
- Keep server-rendered defaults as fallback. Provide a script-enabled reset button that clears the saved values and restores those defaults without reloading or changing article filters.
- Generate a fresh nonce per reader response and authorize only the matching script element. All other endpoints retain script-src 'none'. Sanitized article content cannot supply this nonce.
- Verify native toggle events, cross-navigation restoration, selected-type overrides, reset, storage failures and CSP in a real Chromium browser using an ephemeral test library.

## Risks / Trade-offs

- Native toggle events can be queued during restoration → compare against the restored baseline before persisting.
- Storage may be disabled → catch storage errors and preserve native controls; no HTTP or database side effects.
- Reader CSP changes → authorize by unpredictable per-response nonce, keep inline handlers and untrusted scripts blocked, and test malicious content execution.
- Same browser profiles share layout at one origin → document browser-local scope; saved values contain no feed IDs or personal data.

## Migration Plan

No schema migration. Deploy template, script and server together through the normal rebuild. Rolling back removes the enhancement; the localStorage value is harmless and can be reset before rollback.
