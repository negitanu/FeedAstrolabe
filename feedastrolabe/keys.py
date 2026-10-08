from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import time
from flask import abort, g, request
from .collection import now
from .db import get_db
from .preferences import preferences, bounded_int


def issue_key(name, scope, days):
    if scope not in ('read', 'write'):
        raise ValueError('API キーの権限が不正です。')
    name = name.strip()
    if not name or len(name) > 80:
        raise ValueError('API キー名は 1〜80 文字で入力してください。')
    days = bounded_int(days, 1, 365, '有効期間（日）')
    token = 'faa_' + secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    with db:
        key_id = db.execute('INSERT INTO api_keys(name,prefix,token_hash,scope,created_at,expires_at) VALUES(?,?,?,?,?,?)',
                            (name, token[:12], hashlib.sha256(token.encode()).hexdigest(), scope, now(), expires)).lastrowid
    return key_id, token


def authenticate_api():
    auth = request.headers.get('Authorization', '')
    parts = auth.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer' or len(parts[1]) > 256:
        abort(401, description='Bearer API key required')
    digest = hashlib.sha256(parts[1].encode()).hexdigest()
    db = get_db()
    # BEGIN IMMEDIATE prevents revocation/rate-limit races across Web processes.
    db.execute('BEGIN IMMEDIATE')
    try:
        key = db.execute('SELECT * FROM api_keys WHERE token_hash=? AND revoked_at IS NULL AND expires_at>?', (digest, now())).fetchone()
        if key is None:
            abort(401, description='Invalid or expired API key')
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and key['scope'] != 'write':
            abort(403, description='Write scope required')
        window = int(time.time()) // 60
        count = key['rate_count'] + 1 if key['rate_window'] == window else 1
        limit = preferences()['api_rate_limit']
        if count > limit:
            abort(429, description='API rate limit exceeded')
        db.execute('UPDATE api_keys SET rate_window=?,rate_count=?,last_used_at=? WHERE id=?', (window, count, now(), key['id']))
        db.commit()
        g.api_key_id = key['id']
    except BaseException:
        db.rollback()
        raise
