## Context

Seven Compose files currently separate base services, localhost publication, Cloudflare, observation and optional integrations. Optional file-backed secrets would become mandatory missing-file mounts if simply merged. Existing acceptance scripts also rely on the old local configuration and need a safe test-only authentication override.

## Goals / Non-Goals

**Goals:** One default Tunnel-first deployment file; retain all five services, data identity and isolation; keep optional integrations configurable without extra files; update executable examples and isolated acceptance tests.

**Non-Goals:** Publishing a real hostname, changing credentials, restarting production, changing native development authentication or adding new external integrations.

## Decisions

- Replace all seven files with `compose.yml`. Keep project `feedastrolabe`, volumes `reader-data`/`renderer-ipc`, network `reader` with explicit bridge driver, existing pinned images and hardening. Only renderer uses network_mode none. No service publishes host ports.
- Web requires the existing Cloudflare team domain, AUD and hostname variables; tunnel receives only its file-backed secret and connects to web:5000. Workers use their existing CLI-only local access mode and do not expose HTTP listeners.
- Merge observer/renderer into the default service set so attachments and page observation work without overlays. Retain renderer CPU/memory/PID limits and its socket-only mount.
- Replace optional host-secret overlays with optional file-path environment settings for web/worker. Operators place app-owned 0600 files in the existing private /data volume; blank variables keep features unconfigured. This avoids requiring unused secret files and avoids sharing the Tunnel token directory with the app. Document migration from old secret mounts and the existing private-volume notification setup.
- Acceptance scripts generate a temporary, untracked verification override: web local authentication only, tunnel behind an inactive profile, synthetic Cloudflare values, a temporary dummy secret, optional credential paths blank and no host ports. Restrict project names to *-verify, ignore the operator's .env and explicitly start only selected services; never connect a real Tunnel. Keep production compose.yml as their base.

## Risks / Trade-offs

- Default-file precedence or stale instructions → delete old files and update all executable/documentation references.
- Accidental new library → preserve project and named volume keys and test resolved volume names.
- Optional credential path change → document copying owner-only files into the private volume and setting container paths in .env; never read or copy real credentials automatically.
- Verification accidentally uses production settings → explicit env-file and project, fixed test values, disabled tunnel and tests of the resolved verification model.

## Migration Plan

Back up the existing library, update .env and optional credential locations if used, then run docker compose config --quiet and docker compose up --build -d --wait. Existing volumes are reused. Production restart and real Cloudflare acceptance remain operator actions. Restore instructions stop web, worker and observer, then recreate the default service set after offline restore.
