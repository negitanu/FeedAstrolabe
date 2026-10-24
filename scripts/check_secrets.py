#!/usr/bin/env python3
"""Inspect Git candidates/history; report locations and rules, never secret values.

A conservative pattern check, not a guarantee that every secret is detectable.
No allowlist for entire files: fixtures should build synthetic values at runtime.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    'private-key': rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'aws-access-key': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'github-token': rb'\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{50,255})\b',
    'slack-token': rb'\bxox[baprs]-[A-Za-z0-9-]{20,}\b',
    'google-api-key': rb'\bAIza[A-Za-z0-9_-]{35}\b',
    'jwt': rb'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{20,}\b',
    'literal-credential': rb'''(?i)(?:bearer[_-]?token|api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[=:]\s*["']([A-Za-z0-9%+/=_-]{32,})["']''',
    'credential-url': rb'https?://[^\s/"\'<>:]+:[^\s/"\'<>@]{8,}@',
}
RULES = {name: re.compile(pattern) for name, pattern in PATTERNS.items()}
SENSITIVE = re.compile(r'(^|/)(?:instance|secrets|backups|\.aws|\.ssh)/|(^|/)\.env(?:\.|$)|\.(?:sqlite3?|db|pem|key|p12|pfx|jks)(?:-(?:wal|shm))?$', re.I)


def findings(data):
    return [name for name, rule in RULES.items() if rule.search(data)]


def git(*args):
    return subprocess.check_output(['git', *args])


def inspect(data, label):
    matches = findings(data)
    for name in matches:
        print(f'{label}: {name}', file=sys.stderr)
    return bool(matches)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--staged', action='store_true')
    parser.add_argument('--worktree', action='store_true')
    args = parser.parse_args()
    if not any((args.history, args.staged, args.worktree)):
        args.staged = True
    failed = False
    count = 0
    if args.staged or args.worktree:
        paths = git('ls-files', '-z').decode().split('\0')
        for path in filter(None, paths):
            if args.worktree and not Path(path).exists():
                # A tracked deletion has no worktree content to inspect.
                continue
            # Exactly this example is non-secret configuration.
            if path != '.env.example' and SENSITIVE.search(path):
                print(f'{path}: sensitive-file-path', file=sys.stderr)
                failed = True
            data = Path(path).read_bytes() if args.worktree else git('show', ':' + path)
            failed = inspect(data, path) or failed
            count += 1
    if args.history:
        # Every reachable object on every local ref, including earlier versions.
        for line in git('rev-list', '--objects', '--all').decode().splitlines():
            oid = line.split(' ', 1)[0]
            if git('cat-file', '-t', oid).strip() != b'blob':
                continue
            label = line.split(' ', 1)[1] if ' ' in line else oid[:12]
            if label != '.env.example' and SENSITIVE.search(label):
                print(f'history/{label}: sensitive-file-path', file=sys.stderr)
                failed = True
            failed = inspect(git('cat-file', 'blob', oid), 'history/' + label) or failed
            count += 1
    if failed:
        print('Secret check failed. Values were not printed. Resolve findings before push.', file=sys.stderr)
        return 1
    print(f'Secret check passed: {count} candidates; values not printed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
