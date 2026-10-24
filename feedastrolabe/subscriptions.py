"""Atomic UI/API management. No network access while editing subscriptions."""
from .collection import refresh_lock
from .db import get_db
from .opml import transfer_url
from .preferences import bounded_int


class SubscriptionMissing(LookupError):
    pass


class SubscriptionDuplicate(ValueError):
    pass


def find_feed(db, feed_id):
    row = db.execute('SELECT * FROM feeds WHERE id=?', (feed_id,)).fetchone()
    if row is None:
        raise SubscriptionMissing('購読が見つかりません。')
    return row


def public_url(value):
    if not isinstance(value, str):
        raise ValueError('URL は文字列で指定してください。')
    try:
        return transfer_url(value.strip())
    except ValueError:
        raise ValueError('認証情報を含まない公開 HTTP(S) URL を指定してください。') from None


def update_subscription(feed_id, values):
    if not isinstance(values, dict) or not values:
        raise ValueError('変更する設定を指定してください。')
    db = get_db()
    with refresh_lock(), db:
        db.execute('BEGIN IMMEDIATE')
        old = find_feed(db, feed_id)
        allowed = {'folder', 'enabled', 'poll_interval'}
        if old['source_type'] in ('rss', 'page'):
            allowed.add('url')
        if old['source_type'] == 'page':
            allowed.update(('selector', 'settle_ms', 'retention_days'))
        if old['source_kind'] == 'topic':
            allowed.update(('name', 'window_hours'))
        if set(values) - allowed:
            raise ValueError('この購読では変更できない設定が含まれています。')
        changes = {}
        if 'folder' in values:
            value = values['folder']
            if not isinstance(value, str) or len(value.strip()) > 80 or any(ord(c) < 32 for c in value):
                raise ValueError('フォルダーは 80 文字以下の文字列で指定してください。')
            changes['folder'] = value.strip()
        if 'enabled' in values:
            if type(values['enabled']) is not bool:
                raise ValueError('enabled は true/false で指定してください。')
            changes['enabled'] = int(values['enabled'])
            if old['source_type'] == 'x' and changes['enabled']:
                raise ValueError('X 収集は終了しました。SNS 調査を利用してください。')
        if 'poll_interval' in values:
            value = values['poll_interval']
            changes['poll_interval'] = None if value is None else bounded_int(value, 60, 86400, 'ポーリング間隔')
        if old['source_kind'] == 'topic':
            from .social_research import text_value
            if 'poll_interval' in changes:
                if changes['poll_interval'] is None:
                    raise ValueError('SNS 調査の収集間隔を指定してください。')
                changes['poll_interval'] = bounded_int(changes['poll_interval'], 900, 86400, '収集間隔（秒）')
            if 'name' in values:
                changes['title'] = text_value(values['name'], 120, '分野名')
            if 'window_hours' in values:
                window = bounded_int(values['window_hours'], 1, 168, '対象期間（時間）')
                db.execute('UPDATE social_topics SET window_hours=? WHERE feed_id=?', (window, feed_id))
                changes['checked_at'] = None
        if old['source_type'] == 'rss' and 'url' in values:
            changes['url'] = public_url(values['url'])
            if changes['url'] != old['url']:
                changes.update(etag=None, modified=None, checked_at=None, success_at=None, error=None, failures=0, retry_at=None)
        if old['source_type'] == 'page' and set(values) & {'url','selector','settle_ms','retention_days','poll_interval'}:
            from .observation import canonical, page_values
            url, selector, settle, _, retention = page_values(
                values.get('url', old['target']), values.get('selector', old['selector']),
                values.get('settle_ms', old['settle_ms']), changes.get('poll_interval', old['poll_interval']) or 900,
                values.get('retention_days', old['retention_days']))
            changes.update(url=canonical(url, selector), target=url, selector=selector, settle_ms=settle, retention_days=retention,
                           revision=old['revision'] + 1)
            if selector != old['selector']:
                changes['title'] = 'ページ観測 · ' + selector
            if url != old['target'] or selector != old['selector'] or settle != old['settle_ms']:
                changes.update(snapshot=None, checked_at=None, success_at=None, error=None, failures=0)
        if 'url' in changes and db.execute('SELECT 1 FROM feeds WHERE url=? AND id<>?', (changes['url'], feed_id)).fetchone():
            raise SubscriptionDuplicate('同じ取得対象は登録済みです。')
        if 'folder' in changes and changes['folder'] != old['folder']:
            rank = db.execute('SELECT coalesce(max(p.position),-1)+1 FROM feed_positions p JOIN feeds f ON f.id=p.feed_id WHERE f.folder=?', (changes['folder'],)).fetchone()[0]
            db.execute('INSERT INTO feed_positions VALUES(?,?) ON CONFLICT(feed_id) DO UPDATE SET position=excluded.position', (feed_id,rank))
        if changes.get('enabled') == 0:
            db.execute('DELETE FROM page_jobs WHERE feed_id=?', (feed_id,))
            db.execute("UPDATE social_ai_jobs SET status='failed',error='openrouter-automatic-paused' WHERE feed_id=? AND automatic=1 AND status='queued'", (feed_id,))
        db.execute('UPDATE feeds SET ' + ','.join(name + '=?' for name in changes) + ' WHERE id=?', [*changes.values(), feed_id])


def delete_subscription(feed_id):
    db = get_db()
    with refresh_lock(), db:
        db.execute('BEGIN IMMEDIATE')
        find_feed(db, feed_id)
        db.execute('DELETE FROM feeds WHERE id=?', (feed_id,))
