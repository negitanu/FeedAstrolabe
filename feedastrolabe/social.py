"""Social source adapters and durable per-page collection."""
import html
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import bleach
from flask import current_app
from .db import get_db
from .fetch import normalize_url, safe_link
from .opml import transfer_url
from .social_http import SocialError, request_json

ID = re.compile(r'[0-9]{1,32}\Z')
X_ID = re.compile(r'[0-9]{1,19}\Z')
CURSOR = re.compile(r'[a-zA-Z0-9_-]{1,2048}\Z')


def x_token():
    file = current_app.config.get('X_TOKEN_FILE') or os.environ.get('FEEDASTROLABE_X_TOKEN_FILE')
    if not file:
        raise SocialError('X トークンファイルが未設定です。SNS 連携手順を確認してください。')
    fd = None
    try:
        fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(fd)
        # Docker file-backed secrets are readable by the app UID. Native secrets
        # must be owned by the app user and readable only by that user.
        mounted = Path(file).absolute() == Path('/run/secrets/feedastrolabe_x_token')
        if not stat.S_ISREG(info.st_mode) or info.st_size > 8192 or info.st_size == 0:
            raise ValueError()
        if not mounted and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise ValueError()
        token = os.read(fd, 8193).decode('ascii').strip()
        if not re.fullmatch(r'[A-Za-z0-9%._~+/=-]{16,8192}', token):
            raise ValueError()
        return token
    except Exception:
        raise SocialError('X トークンファイルを安全に読み込めません。配置と権限を確認してください。') from None
    finally:
        if fd is not None:
            os.close(fd)


def source_values(source_type, kind, target, instance_url=''):
    if not all(isinstance(v, str) for v in (source_type, kind, target, instance_url)):
        raise ValueError('SNS 設定は文字列で入力してください。')
    target = target.strip().removeprefix('@')
    if source_type == 'x':
        if instance_url.strip():
            raise ValueError('X の API 取得先は固定です。サーバー欄は空欄にしてください。')
        if kind == 'account' and re.fullmatch(r'[A-Za-z0-9_]{1,15}|[0-9]{1,19}', target):
            target = target.lower()
            url = 'https://x.com/' + target if not X_ID.fullmatch(target) else 'https://x.com/i/user/' + target
        elif kind == 'list' and X_ID.fullmatch(target):
            url = 'https://x.com/i/lists/' + target
        else:
            raise ValueError('X はユーザー名・ユーザー ID、または数値のリスト ID を指定してください。')
        return url, target, ''
    if source_type == 'mastodon' and kind == 'account' and re.fullmatch(r'[A-Za-z0-9_]{1,64}', target):
        origin = normalize_url(instance_url.strip())
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or parsed.path != '/' or parsed.query:
            raise ValueError('Mastodon サーバーは公開 HTTPS の origin を指定してください。')
        transfer_url(origin)  # Reject literal private IP and local names, no lookup.
        origin = origin.rstrip('/')
        target = target.lower()
        return origin + '/@' + target, target, origin
    raise ValueError('対応 SNS と取得対象の種類を選択してください。')


def add_social(source_type, kind, target, instance_url='', folder=''):
    from .collection import now, refresh_lock
    url, target, origin = source_values(source_type, kind, target, instance_url)
    if not isinstance(folder, str):
        raise ValueError('フォルダーは文字列で入力してください。')
    db = get_db()
    with refresh_lock(), db:
        if db.execute('SELECT id FROM feeds WHERE url=?', (url,)).fetchone():
            raise ValueError('この情報源は登録済みです。')
        title = ('X リスト ' if kind == 'list' else 'X @') + target if source_type == 'x' else '@' + target + '@' + urlsplit(origin).hostname
        result = db.execute('''INSERT INTO feeds(url,title,folder,created_at,source_type,source_kind,target,instance_url)
          VALUES(?,?,?,?,?,?,?,?)''', (url, title, folder.strip()[:80], now(), source_type, kind, target, origin))
        return result.lastrowid


def cooldown(feed):
    from .collection import now
    row = get_db().execute('SELECT retry_at FROM provider_cooldowns WHERE provider=?', (feed['source_type'],)).fetchone()
    times = [value for value in (feed['retry_at'], row['retry_at'] if row else None) if value]
    return max(times) if times and max(times) > now() else None


def record_retry(feed, retry_at):
    if not retry_at:
        return
    db = get_db()
    with db:
        db.execute('UPDATE feeds SET retry_at=? WHERE id=?', (retry_at, feed['id']))
        if feed['source_type'] == 'x':
            db.execute('''INSERT INTO provider_cooldowns(provider,retry_at) VALUES('x',?)
              ON CONFLICT(provider) DO UPDATE SET retry_at=max(retry_at,excluded.retry_at)''', (retry_at,))


def numeric_id(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise SocialError('SNS 応答の投稿・アカウント ID が不正です。')
    return value


def cursor_value(value):
    if value is not None and (not isinstance(value, str) or not CURSOR.fullmatch(value)):
        raise SocialError('SNS 応答のページ情報が不正です。')
    return value


def resolve_provider(feed, token):
    if feed['provider_id']:
        return numeric_id(feed['provider_id'])
    if feed['source_type'] == 'x':
        if feed['source_kind'] == 'list' or X_ID.fullmatch(feed['target']):
            return feed['target']
        data, _ = request_json('https://api.x.com/2/users/by/username/' + feed['target'], token)
        value = data.get('data') if isinstance(data, dict) else None
    else:
        data, _ = request_json(feed['instance_url'] + '/api/v1/accounts/lookup?' + urlencode({'acct': feed['target']}))
        value = data
    if not isinstance(value, dict):
        raise SocialError('SNS アカウントの応答形式が不正です。')
    return numeric_id(value.get('id'))


def page(feed, provider_id, token):
    if feed['source_type'] == 'x':
        group = 'lists' if feed['source_kind'] == 'list' else 'users'
        params = {'max_results': 100, 'post.fields': 'created_at,author_id,text'}
        if feed['since_id'] and group == 'users':
            params['since_id'] = feed['since_id']
        if feed['page_cursor']:
            params['pagination_token'] = feed['page_cursor']
        data, _ = request_json(f'https://api.x.com/2/{group}/{provider_id}/tweets?' + urlencode(params), token)
        if not isinstance(data, dict) or data.get('errors'):
            raise SocialError('X API の応答にエラーがあります。権限・取得対象を確認してください。')
        rows = data.get('data', [])
        meta = data.get('meta', {})
        if not isinstance(rows, list) or len(rows) > 100 or not isinstance(meta, dict):
            raise SocialError('X API の投稿応答が不正です。')
        next_cursor = cursor_value(meta.get('next_token'))
    else:
        params = {'limit': 40}
        if feed['since_id']:
            params['since_id'] = feed['since_id']
        if feed['page_cursor']:
            params['max_id'] = feed['page_cursor']
        rows, _ = request_json(feed['instance_url'] + f'/api/v1/accounts/{provider_id}/statuses?' + urlencode(params))
        if not isinstance(rows, list) or len(rows) > 40:
            raise SocialError('Mastodon API の投稿応答が不正です。')
        next_cursor = min((numeric_id(r.get('id')) for r in rows if isinstance(r, dict)), key=int) if len(rows) == 40 else None
    for row in rows:
        if not isinstance(row, dict):
            raise SocialError('SNS 投稿の応答形式が不正です。')
        numeric_id(row.get('id'))
    # List timelines lack since_id. Stop locally at the committed boundary.
    if feed['source_type'] == 'x' and feed['source_kind'] == 'list' and feed['since_id']:
        if any(int(r['id']) <= int(feed['since_id']) for r in rows):
            next_cursor = None
        rows = [r for r in rows if int(r['id']) > int(feed['since_id'])]
    if next_cursor and (not rows or next_cursor == feed['page_cursor']):
        raise SocialError('SNS のページ情報が進みません。再試行しても続く場合は取得対象を確認してください。')
    return rows, next_cursor


def entries(feed, rows):
    from .collection import now, sanitize
    result = []
    for row in rows:
        if feed['source_type'] == 'x':
            text = row.get('text')
            if not isinstance(text, str):
                raise SocialError('X 投稿本文の形式が不正です。')
            content = '<p>' + html.escape(text).replace('\n', '<br>') + '</p>'
            link = 'https://x.com/i/web/status/' + row['id']
            title = text[:160] or 'X 投稿'
        else:
            # Only public/unlisted posts. Private posts are never persisted.
            if row.get('visibility') not in ('public', 'unlisted'):
                continue
            content = row.get('content')
            if not isinstance(content, str):
                raise SocialError('Mastodon 投稿本文の形式が不正です。')
            warning = row.get('spoiler_text', '')
            if not isinstance(warning, str):
                raise SocialError('Mastodon 投稿の形式が不正です。')
            if warning:
                content = '<p><strong>' + html.escape(warning) + '</strong></p>' + content
            title = html.unescape(bleach.clean(content, tags=[], strip=True))[:160] or 'Mastodon 投稿'
            link = safe_link(row.get('url', ''), feed['instance_url'])
        content = sanitize(content)
        plain = html.unescape(bleach.clean(content, tags=[], strip=True))
        try:
            published = datetime.fromisoformat(row.get('created_at', '').replace('Z', '+00:00'))
            if published.tzinfo is None:
                raise ValueError()
            published = published.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        except (TypeError, ValueError, AttributeError):
            published = now()
        result.append((feed['id'], feed['source_type'] + ':' + row['id'], title, link, content, plain, published))
    return result


def refresh_social(feed):
    from .collection import now
    feed = dict(feed)
    token = x_token() if feed['source_type'] == 'x' else None
    provider_id = resolve_provider(feed, token)
    db = get_db()
    with db:
        db.execute('UPDATE feeds SET provider_id=? WHERE id=?', (provider_id, feed['id']))
    initial = not feed['success_at']
    for _ in range(1 if initial else 3):
        rows, next_cursor = page(feed, provider_id, token)
        items = entries(feed, rows)
        newest = max([v for v in [feed['pending_newest'], feed['since_id']] if v] + [r['id'] for r in rows], key=int, default=None)
        if initial:
            next_cursor = None  # Recent baseline, not a historical archive.
        with db:
            db.executemany('''INSERT INTO articles(feed_id,guid,title,link,content,search_text,published_at)
              VALUES(?,?,?,?,?,?,?) ON CONFLICT(feed_id,guid) DO UPDATE SET
              title=excluded.title,link=excluded.link,content=excluded.content,search_text=excluded.search_text''', items)
            db.execute('''UPDATE feeds SET since_id=?,page_cursor=?,pending_newest=?,checked_at=?,success_at=?,error=NULL,failures=0,retry_at=NULL WHERE id=?''',
                       (feed['since_id'] if next_cursor else newest, next_cursor, newest if next_cursor else None, now(), now(), feed['id']))
        feed['page_cursor'] = next_cursor
        feed['pending_newest'] = newest if next_cursor else None
        if not next_cursor:
            break
