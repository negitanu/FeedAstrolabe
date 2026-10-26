#!/usr/bin/env python3
"""Scan tracked and non-ignored source candidates without opening runtime data."""
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
result = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=root, check=True, capture_output=True)
patterns = [
    ('private key', re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('AWS access key', re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
    ('GitHub token', re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b')),
    ('provider key', re.compile(rb'\bsk-(?:or-v1-|proj-)[A-Za-z0-9_-]{30,}\b')),
]
findings = []
for raw in result.stdout.split(b'\0'):
    if not raw:
        continue
    name = raw.decode()
    path = root / name
    if not path.is_file():
        continue
    body = path.read_bytes()
    if b'\0' in body:
        continue
    for label, pattern in patterns:
        if pattern.search(body):
            findings.append((name, label))
for name, label in findings:
    print(f'{name}: possible {label}')
if findings:
    sys.exit(1)
print('No credential patterns found in Git source candidates (heuristic scan).')
