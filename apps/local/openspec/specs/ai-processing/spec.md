# ai-processing Specification

## Purpose

FeedAstrolabeのフル移植に向けた0.2.0のSNS/AI契約。元仕様と残差は docs/full-port-plan.md と docs/parity.md で追跡する。

## Requirements

### Requirement: Provider isolation and opt-in
The system SHALL preserve independent revisioned configurations for OpenRouter, OrcaRouter and Ollama local/cloud, default to disabled with no default model, and never expose credentials to renderer, DB or exports.

#### Scenario: Switch provider
- **WHEN** a user switches active provider while a job is queued
- **THEN** the old job retains its original provider/configuration and daily accounting

### Requirement: Durable budgets and no replay
The system SHALL reserve conservative integer micro-USD costs and daily calls before dispatch, deduplicate identical operations, process one generation at a time, never replay possibly charged POSTs and retain reservations on failure.

#### Scenario: Restart after interruption
- **WHEN** the process restarts with a running job
- **THEN** the job becomes failed and is not sent again

#### Scenario: Budget exhausted
- **WHEN** a reservation exceeds the shared UTC daily budget
- **THEN** no generation is queued or sent

### Requirement: Grounded topics
The system SHALL extract up to five structured topics from at most twenty eligible public posts, validate article citations, usage, finish and costs, and retain a previous valid result if a new job fails.

#### Scenario: Invalid citation
- **WHEN** the model cites an article not in the frozen input
- **THEN** the result is rejected

#### Scenario: Automatic extraction
- **WHEN** a successful scheduled topic run has explicit auto-AI enabled
- **THEN** one job is reserved for its run and configuration

### Requirement: Exact-preview assistance
The system SHALL provide summary/translation/compare/qa over selected immutable case evidence with an exact-body preview, 30-minute expiry, explicit approval hash and revision/privacy revalidation before transmission.

#### Scenario: Stale approval
- **WHEN** the case classification or profile changed after preview
- **THEN** no input is transmitted

#### Scenario: No evidence
- **WHEN** a case has no selected evidence
- **THEN** insufficient evidence is returned without model execution

### Requirement: Local identity and private evidence
The system SHALL validate local Ollama cloud-disabled status and model digest, restrict cloud processing to public cases and inputs unreferenced by private cases, treat evidence instructions as inert data, and preserve independent human review revisions.

#### Scenario: Local runtime mismatch
- **WHEN** the local Ollama model digest changed or cloud is enabled
- **THEN** generation is blocked before selected text is sent

#### Scenario: Private cross reference
- **WHEN** selected evidence is also referenced by an internal case
- **THEN** cloud submission is rejected

#### Scenario: Review
- **WHEN** a user reviews or corrects output
- **THEN** the model output and original evidence remain immutable
