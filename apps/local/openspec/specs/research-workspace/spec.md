# research-workspace Specification

## Purpose

FeedAstrolabe-local 0.1.0 の research-workspace に関する現行契約。Go / Electron の独立したローカル実装を定義する。元版との差分は docs/parity.md を参照。

## Requirements

### Requirement: Local cases and notes
The system SHALL create and archive research cases, associate saved articles, and retain note revisions with optimistic concurrency checks.

#### Scenario: Conflicting save
- **WHEN** a stale note revision is submitted
- **THEN** the save is rejected without overwriting the newer note

### Requirement: Evidence and reports
The system SHALL save immutable article snapshots with URL, timestamp and SHA-256 and export Markdown reports containing notes and cited evidence.

#### Scenario: Source changes
- **WHEN** an article changes after evidence was captured
- **THEN** the evidence text and hash remain unchanged
