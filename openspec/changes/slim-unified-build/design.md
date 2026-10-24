## Context

The application image pins 20 packages; development adds five test packages and renderer adds four browser packages. Versions are duplicated across five files. Two Dockerfiles repeat base, user and dependency setup. The verified arm64 images currently occupy 248,264,500 bytes (app) and 1,914,317,096 bytes (renderer).

## Goals / Non-Goals

**Goals:** One requirements.txt and one Dockerfile; preserve pinned versions and features; smaller images and isolated role-specific dependencies; measurable before/after evidence.

**Non-Goals:** Updating dependency/base-image versions, removing features, weakening renderer isolation or deploying to production.

## Decisions

- Use requirements.txt as the single set of 29 exact pins, usable as a complete development install or as pip constraints. Standard PEP 735 groups in the existing pyproject.toml select unversioned direct roots for app, renderer (app + Playwright) and test (renderer + pytest). No custom requirements parser or duplicate version declarations.
- One Dockerfile has a shared dependency/runtime stage, then renderer and app targets. App is the last/default target. Copy application source only after dependency installation so source edits do not invalidate browser installation layers.
- Compose explicitly selects app for web/worker/observer and renderer for its isolated service. Retain all network, volume, credential, UID and resource constraints.
- Install Chromium with --only-shell because renderer uses headless=True without a browser channel. Avoid full Chromium duplication, bytecode compilation and pip/APT cache residue; keep required browser OS dependencies and fonts.
- Verify dependency closure and absence of pytest/browser packages in app, headless shell presence without full Chromium in renderer, pip consistency, existing real IPC/browser/container checks, and image byte sizes on the same base/architecture.

## Risks / Trade-offs

- Incomplete role closure → pip resolves dependencies under the unified pins; compare installed package names/versions with expected groups and run pip check.
- Older native pip lacks --group → document pip 25.1+ for selective installs; ordinary -r requirements.txt remains supported for a complete development environment.
- Browser reduction breaks extraction → run real Chromium observation and text/Markdown/PDF IPC checks in the built image.

## Migration Plan

Replace old requirements references in current docs/CI and select build targets in compose.yml. Rebuild with the usual docker compose command. Existing named volumes and app behavior remain unchanged; no production restart is performed during verification.
