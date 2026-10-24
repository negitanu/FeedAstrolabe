"""Social source adapters and durable per-page collection."""
import html
import re
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit

import bleach
from .db import get_db
from .fetch import normalize_url, safe_link
from .opml import transfer_url
from .social_http import SocialError, request_json

ID = re.compile(r'[0-9]{1,32}\Z')


def source_values(source_type, kind, target, instance_url=''):
    if not all(isinstance(v, str) for v in (source_type, kind, target, instance_url)):
        raise ValueError('SNS 設定は文字列で入力してください。')
    target = target.strip().removeprefix('@')
    if source_type == 'x':
        raise ValueError('X 収集は終了しました。Mastodon／Bluesky の SNS 調査を利用してください。')
    if source_type == 'mastodon' and kind == 'account' and re.fullmatch(r'[A-Za-z0-9_]{1,64}', target):
        origin = normalize_url(instance_url.strip())
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or parsed.path != '/' or parsed.query or parsed.port not in (None, 443):
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
        title = '@' + target + '@' + urlsplit(origin).hostname
        result = db.execute('''INSERT INTO feeds(url,title,folder,created_at,source_type,source_kind,target,instance_url)
          VALUES(?,?,?,?,?,?,?,?)''', (url, title, folder.strip()[:80], now(), source_type, kind, target, origin))
        return result.lastrowid


def provider_key(feed):
    return 'mastodon:' + (feed['instance_url'] or '') if feed['source_type'] == 'mastodon' else feed['source_type']


def cooldown(feed):
    from .collection import now
    row = get_db().execute('SELECT retry_at FROM provider_cooldowns WHERE provider=?', (provider_key(feed),)).fetchone()
    times = [value for value in (feed['retry_at'], row['retry_at'] if row else None) if value]
    return max(times) if times and max(times) > now() else None


def record_retry(feed, retry_at):
    if not retry_at:
        return
    db = get_db()
    with db:
        db.execute('UPDATE feeds SET retry_at=? WHERE id=?', (retry_at, feed['id']))
        db.execute('''INSERT INTO provider_cooldowns(provider,retry_at) VALUES(?,?)
          ON CONFLICT(provider) DO UPDATE SET retry_at=max(retry_at,excluded.retry_at)''', (provider_key(feed), retry_at))


def numeric_id(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise SocialError('SNS 応答の投稿・アカウント ID が不正です。')
    return value


def resolve_provider(feed):
    if feed['provider_id']:
        return numeric_id(feed['provider_id'])
    data, _ = request_json(feed['instance_url'] + '/api/v1/accounts/lookup?' + urlencode({'acct': feed['target']}))
    if not isinstance(data, dict):
        raise SocialError('Mastodon アカウントの応答形式が不正です。')
    return numeric_id(data.get('id'))


def page(feed, provider_id):
    params = {'limit': 40}
    if feed['since_id']:
        params['since_id'] = numeric_id(feed['since_id'])
    if feed['page_cursor']:
        params['max_id'] = numeric_id(feed['page_cursor'])
    rows, _ = request_json(feed['instance_url'] + f'/api/v1/accounts/{provider_id}/statuses?' + urlencode(params))
    if not isinstance(rows, list) or len(rows) > 40:
        raise SocialError('Mastodon API の投稿応答が不正です。')
    for row in rows:
        if not isinstance(row, dict):
            raise SocialError('Mastodon 投稿の応答形式が不正です。')
        numeric_id(row.get('id'))
    next_cursor = min((r['id'] for r in rows), key=int) if len(rows) == 40 else None
    if next_cursor and (next_cursor == feed['page_cursor'] or (feed['page_cursor'] and int(next_cursor) >= int(feed['page_cursor']))):
        raise SocialError('SNS のページ情報が進みません。取得対象を確認してください。')
    return rows, next_cursor


def entries(feed, rows):
    from .collection import now, sanitize
    result = []
    for row in rows:
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
            source_date_known=True
            published = datetime.fromisoformat(row.get('created_at', '').replace('Z', '+00:00'))
            if published.tzinfo is None:
                raise ValueError()
            published = published.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        except (TypeError, ValueError, AttributeError):
            source_date_known=False
            published = now()
        result.append((feed['id'], feed['source_type'] + ':' + row['id'], title, link, content, plain, published,published if source_date_known else None))
    return result


def refresh_social(feed):
    from .collection import now
    feed = dict(feed)
    if feed['source_type'] == 'x':
        raise SocialError('X 収集は終了しました。')
    if feed['source_kind'] == 'topic':
        from .social_research import refresh_topic
        return refresh_topic(feed)
    if feed['source_type'] != 'mastodon':
        raise SocialError('対応していない SNS です。')
    provider_id = resolve_provider(feed)
    db = get_db()
    with db:
        db.execute('UPDATE feeds SET provider_id=? WHERE id=?', (provider_id, feed['id']))
    initial = not feed['success_at']
    for _ in range(1 if initial else 3):
        rows, next_cursor = page(feed, provider_id)
        items = entries(feed, rows)
        newest = max([v for v in [feed['pending_newest'], feed['since_id']] if v] + [r['id'] for r in rows], key=int, default=None)
        if initial:
            next_cursor = None  # Recent baseline, not a historical archive.
        with db:
            db.executemany('''INSERT INTO articles(feed_id,guid,title,link,content,search_text,published_at,source_published_at)
              VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(feed_id,guid) DO UPDATE SET
              title=excluded.title,link=excluded.link,content=excluded.content,search_text=excluded.search_text,source_published_at=excluded.source_published_at''', items)
            db.execute('''UPDATE feeds SET since_id=?,page_cursor=?,pending_newest=?,checked_at=?,success_at=?,error=NULL,failures=0,retry_at=NULL WHERE id=?''',
                       (feed['since_id'] if next_cursor else newest, next_cursor, newest if next_cursor else None, now(), now(), feed['id']))
        from .evidence import capture_articles
        identifiers=[db.execute('SELECT id FROM articles WHERE feed_id=? AND guid=?',(feed['id'],item[1])).fetchone()[0] for item in items]
        capture_articles(identifiers,feed['id'])
        feed['page_cursor'] = next_cursor
        feed['pending_newest'] = newest if next_cursor else None
        if not next_cursor:
            break
