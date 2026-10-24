import calendar
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
from pathlib import Path

import bleach
import feedparser
from flask import current_app
from .db import get_db
from .fetch import fetch, safe_link, MAX_BYTES
from .xml_safety import validate_xml
from .preferences import preferences, is_due

TAGS = {'p', 'br', 'a', 'strong', 'em', 'b', 'i', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'h2', 'h3', 'h4', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td'}


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def sanitize(value):
    return bleach.clean(value, tags=TAGS, attributes={'a': ['href', 'title']}, protocols=['http', 'https'], strip=True)


def parse_feed(body):
    validate_xml(body, max_bytes=MAX_BYTES, max_elements=100000)
    parsed = feedparser.parse(body)
    if not parsed.version or not (parsed.version.startswith('rss') or parsed.version.startswith('atom')):
        raise ValueError('RSS または Atom フィードを指定してください。')
    if parsed.bozo and not parsed.entries:
        raise ValueError('フィードを解析できませんでした。')
    return parsed


class RefreshBusy(ValueError):
    pass


@contextmanager
def refresh_lock():
    path = Path(current_app.instance_path) / 'refresh.lock'
    with path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RefreshBusy('更新処理が実行中です。しばらく待ってから再度お試しください。') from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def ingest(db, feed_id, parsed, base):
    timestamp = now()
    identifiers = []
    for entry in parsed.entries[:2000]:
        title = bleach.clean(entry.get('title', '無題'), tags=[], strip=True)[:1000]
        raw = entry.get('content', [{}])[0].get('value', '') or entry.get('summary', '')
        content = sanitize(raw)
        plain = bleach.clean(content, tags=[], strip=True)
        link = safe_link(entry.get('link', ''), base)
        # Stable identity only: never hash mutable body text (content edits would mint duplicates).
        guid = entry.get('id') or link or hashlib.sha256(title.encode()).hexdigest()
        date = entry.get('published_parsed') or entry.get('updated_parsed')
        source_date_known=False
        try:
            published = datetime.fromtimestamp(calendar.timegm(date), timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if date else timestamp
            source_date_known=bool(date)
        except (OverflowError, ValueError, TypeError):
            published = timestamp
        db.execute("""INSERT INTO articles (feed_id,guid,title,link,content,search_text,published_at,source_published_at)
          VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(feed_id,guid) DO UPDATE SET
          title=excluded.title,link=excluded.link,content=excluded.content,search_text=excluded.search_text,
          source_published_at=excluded.source_published_at,
          published_at=CASE WHEN excluded.source_published_at IS NOT NULL THEN excluded.published_at ELSE articles.published_at END""",
          (feed_id, str(guid), title, link, content, plain, published, published if source_date_known else None))
        identifiers.append(db.execute('SELECT id FROM articles WHERE feed_id=? AND guid=?',(feed_id,str(guid))).fetchone()[0])
    return identifiers


def add_feed(url, folder):
    db = get_db()
    if db.execute('SELECT id FROM feeds WHERE url=?', (url,)).fetchone():
        raise ValueError('このフィードは登録済みです。')
    with refresh_lock():
        body, meta = fetch(url)
        if body is None:
            raise ValueError('初回取得に記事データがありません。')
        parsed = parse_feed(body)
        title = bleach.clean(parsed.feed.get('title', url), tags=[], strip=True)[:1000]
        with db:
            cursor = db.execute('INSERT INTO feeds (url,title,folder,etag,modified,checked_at,success_at,created_at) VALUES (?,?,?,?,?,?,?,?)',
                                (url, title, folder, meta['etag'], meta['modified'], now(), now(), now()))
            identifiers=ingest(db, cursor.lastrowid, parsed, meta['url'])
        from .evidence import capture_articles
        capture_articles(identifiers,cursor.lastrowid)
        return cursor.lastrowid


def refresh_feeds(feed_id=None, due_only=False, interval_override=None):
    db = get_db()
    succeeded = failed = 0
    with refresh_lock():
        feeds = db.execute('SELECT * FROM feeds' + (' WHERE id=?' if feed_id else ''), (feed_id,) if feed_id else ()).fetchall()
        config = preferences()
        for feed in feeds:
            if not feed['enabled']:
                continue
            if feed['source_type'] == 'x':
                continue  # Historical articles remain readable; never contact X.
            if feed['source_type'] == 'page':
                if not due_only and (feed_id or feed['enabled']):
                    from .observation import queue_page
                    queue_page(feed['id'])
                continue
            if feed['source_type'] != 'rss':
                from .social import cooldown
                if cooldown(feed):
                    continue
            if due_only and not is_due(feed, config, interval_override):
                continue
            if not due_only and not feed_id and not feed['enabled']:
                continue
            try:
                if feed['source_type'] != 'rss':
                    from .social import refresh_social
                    refresh_social(feed)
                    succeeded += 1
                    continue
                body, meta = fetch(feed['url'], feed['etag'], feed['modified'])
                parsed = parse_feed(body) if body is not None else None
                with db:
                    if parsed is not None:
                        identifiers=ingest(db, feed['id'], parsed, meta['url'])
                        db.execute('UPDATE feeds SET title=?,etag=?,modified=? WHERE id=?',
                                   (bleach.clean(parsed.feed.get('title', feed['title']), tags=[], strip=True)[:1000], meta['etag'], meta['modified'], feed['id']))
                    db.execute('UPDATE feeds SET checked_at=?,success_at=?,error=NULL,failures=0 WHERE id=?', (now(), now(), feed['id']))
                if parsed is not None:
                    from .evidence import capture_articles
                    capture_articles(identifiers,feed['id'])
                succeeded += 1
            except Exception as exc:
                if feed['source_type'] != 'rss':
                    from .social import record_retry
                    from .social_http import SocialError
                    if not isinstance(exc, SocialError):
                        exc = SocialError('SNS 取得に失敗しました。設定・接続を確認してください。')
                    record_retry(feed, exc.retry_at)
                current_app.logger.warning('Feed %s refresh failed: %s', feed['id'], exc)
                with db:
                    db.execute('UPDATE feeds SET checked_at=?,error=?,failures=failures+1 WHERE id=?', (now(), str(exc)[:500], feed['id']))
                failed += 1
    return succeeded, failed
