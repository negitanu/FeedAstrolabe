from datetime import datetime, timedelta, timezone
from flask import g
from .preferences import preferences

JST = timezone(timedelta(hours=9), 'JST')


def display_time(value, precision='seconds', missing='不明'):
    if value is None or value == '':
        return missing
    try:
        instant = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        if 'display_timezone' not in g:
            g.display_timezone = preferences()['display_timezone']
        target = JST if g.display_timezone == 'Asia/Tokyo' else timezone.utc
        pattern = '%Y-%m-%d %H:%M' if precision == 'minutes' else '%Y-%m-%d %H:%M:%S'
        return instant.astimezone(target).strftime(pattern + ' %Z')
    except (ValueError, TypeError, OverflowError):
        return missing
