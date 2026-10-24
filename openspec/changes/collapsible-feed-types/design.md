## Context
The sidebar currently groups all sources by folder. The existing CSP disables scripts.
## Goals / Non-Goals
Goals: independent type collapsing, folder preservation, mobile and keyboard use.
Non-goals: persisting disclosure state between navigations.
## Decisions
Use native details/summary so mouse, touch and keyboard work within current CSP. Show types in RSS, X, Mastodon, page order and omit empty groups. Default all groups open on the general view; when a feed is selected open its group and collapse the others. Within each group preserve folder and title order. Show subscription count and summed unread count with clear labels.
## Risks / Trade-offs
Navigation resets disclosure state → explicitly document initial-open behavior; always expose selected feed. Mobile nav flex rules → dedicated block layout for type groups.
