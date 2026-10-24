## 1. Consolidation

- [x] 1.1 Merge all deployment services and optional integration settings into compose.yml; remove superseded files.
- [x] 1.2 Update setup, credentials, observation and backup/restore documentation to single-file commands and migration instructions.

## 2. Verification

- [x] 2.1 Adapt isolated container acceptance scripts to the unified base without production credentials, tunnels or host ports.
- [x] 2.2 Test resolved Compose security/data/configuration contracts and run isolated runtime verification where available.
- [x] 2.3 Run regression, secret checks, strict OpenSpec and diff validation; record results and remaining deployment limits.
