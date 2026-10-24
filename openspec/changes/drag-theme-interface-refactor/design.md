## Context
Current implementation uses schema 17 and server rendered pages. Folder order already has a transactional database implementation. Styles have accumulated overrides and literal colors.

## Goals / Non-Goals
Goals: direct pointer ordering, accessible alternatives, complete adaptive colors, restrained shared page structure, regression coverage.
Non-goals: changing article data or introducing a frontend framework.

## Decisions
- Reuse the validated CSRF-protected position endpoint. Pointer Events support mouse and touch; drag cancellation restores DOM order. Buttons remain available without JavaScript.
- Use a validated browser cookie for appearance, default system. Server renders the preference before paint; CSS media queries respond to OS changes without JavaScript. Browser-local appearance avoids changing another device's chosen mode.
- Extract semantic tokens and component styles into CSS modules. Shared presentation helpers own theme validation and CSP nonce creation.
- Remove decorative headings and duplicated instructions, retain safety notices, field constraints and actionable errors.

## Risks / Trade-offs
- Touch scrolling can conflict with dragging → only dedicated handles capture pointers, with edge scrolling and cancellation.
- Dark colors can hide controls → test semantic colors and representative pages in both modes, with screenshots and contrast checks.
- CSS extraction can alter cascade → preserve component order and run existing layout tests.

## Migration Plan
No database migration. Rebuild services after full tests and verify actual served assets and pages. Rollback code/image leaves persisted folder order intact.
