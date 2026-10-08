from datetime import datetime, timedelta, timezone
from .db import get_db


def preferences():
    return dict(get_db().execute('SELECT * FROM settings WHERE id=1').fetchone())


def bounded_int(value, low, high, label):
    try:
        if isinstance(value,(bool,float)):
            raise ValueError()
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label}は整数で入力してください。') from None
    if not low <= number <= high:
        raise ValueError(f'{label}は {low}〜{high} の範囲で入力してください。')
    return number


def save_preferences(values):
    interval = bounded_int(values.get('poll_interval'), 60, 86400, 'ポーリング間隔')
    page_size = bounded_int(values.get('page_size'), 10, 100, '表示件数')
    rate = bounded_int(values.get('api_rate_limit'), 1, 1000, 'API リクエスト上限')
    view = values.get('default_view')
    if view not in ('all', 'unread', 'starred'):
        raise ValueError('初期表示が不正です。')
    db = get_db()
    with db:
        db.execute('UPDATE settings SET poll_interval=?,polling_enabled=?,page_size=?,default_view=?,api_rate_limit=? WHERE id=1',
                   (interval, int(values.get('polling_enabled') == '1'), page_size, view, rate))


def due_at(feed, config, interval_override=None):
    feed = dict(feed)
    if not feed['checked_at']:
        return None
    interval = feed['poll_interval'] or interval_override or config['poll_interval']
    delay = min(86400, interval * 2 ** min(feed['failures'], 10))
    checked = datetime.strptime(feed['checked_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    scheduled = checked + timedelta(seconds=delay)
    if feed.get('retry_at'):
        retry = datetime.strptime(feed['retry_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        scheduled = max(scheduled, retry)
    return scheduled


def is_due(feed, config, interval_override=None):
    if not config['polling_enabled'] or not feed['enabled']:
        return False
    next_time = due_at(feed, config, interval_override)
    return next_time is None or next_time <= datetime.now(timezone.utc)
