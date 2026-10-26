const { spawnSync } = require('node:child_process');
const { mkdirSync } = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
mkdirSync(path.join(root, 'bin'), { recursive: true });
const target = path.join(
  root,
  'bin',
  process.platform === 'win32' ? 'feedastrolabe.exe' : 'feedastrolabe',
);
const result = spawnSync('go', ['build', '-trimpath', '-o', target, './cmd/feedastrolabe'], {
  cwd: root,
  stdio: 'inherit',
  env: { ...process.env, CGO_ENABLED: '0' },
});
process.exit(result.status ?? 1);
