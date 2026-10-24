"""Bounded literal reader conditions; calendar dates use the library timezone."""
from datetime import date, datetime, time, timedelta, timezone

from flask import abort
from .db import get_db
from .display_time import JST
from .identifiers import single_value, MAX_ID
from .preferences import preferences


def conditions(source, query):
    selected = {name: single_value(source, name, '').strip() or None for name in
                ('search_in', 'any_terms', 'exclude', 'date_from', 'date_to')}
    field = selected['search_in'] or 'both'
    if field not in ('both', 'title', 'body'):
        abort(400, description='検索対象が不正です。')
    columns = {'both': ('a.title', 'a.search_text'), 'title': ('a.title',), 'body': ('a.search_text',)}[field]
    clauses, params = [], []

    def match(phrase):
        escaped = phrase.replace('!', '!!').replace('%', '!%').replace('_', '!_')
        params.extend(['%' + escaped + '%'] * len(columns))
        return '(' + ' OR '.join(f"{c} LIKE ? ESCAPE '!'" for c in columns) + ')'

    if query:
        clauses.append(match(query))
    for name in ('any_terms', 'exclude'):
        raw = selected[name] or ''
        terms = [value.strip() for value in raw.splitlines() if value.strip()]
        if len(raw) > 2000 or len(terms) > 10 or any(len(value) > 200 for value in terms):
            abort(400, description='追加・除外キーワードは各10行・1行200文字以内で指定してください。')
        if terms:
            matches = [match(value) for value in terms]
            clauses.append('(' + ' OR '.join(matches) + ')' if name == 'any_terms'
                           else 'NOT (' + ' OR '.join(matches) + ')')
    days = {}
    try:
        for name in ('date_from', 'date_to'):
            value = selected[name]
            if value:
                day = date.fromisoformat(value)
                if day.isoformat() != value:
                    raise ValueError()
                days[name] = day
        if days.get('date_from', date.min) > days.get('date_to', date.max):
            raise ValueError()
        tz = JST if preferences()['display_timezone'] == 'Asia/Tokyo' else timezone.utc
        for name, day in days.items():
            boundary = day + timedelta(days=1) if name == 'date_to' else day
            stamp = datetime.combine(boundary, time(), tz).astimezone(timezone.utc)
            clauses.append('a.source_published_at ' + ('>=' if name == 'date_from' else '<') + ' ?')
            params.append(stamp.strftime('%Y-%m-%d %H:%M:%S'))
    except (ValueError, OverflowError):
        abort(400, description='公開日の範囲を YYYY-MM-DD で正しく指定してください。')
    raw_ids = source.getlist('sources')
    if len(raw_ids) > 100:
        abort(400, description='情報源は100件以内で指定してください。')
    identifiers = []
    for value in raw_ids:
        if not value.isascii() or not value.isdecimal() or len(value) > 19 or not 1 <= int(value) <= MAX_ID:
            abort(400, description='情報源 ID が不正です。')
        identifiers.append(int(value))
    if len(set(identifiers)) != len(identifiers):
        abort(400, description='情報源 ID が重複しています。')
    identifiers.sort()
    if identifiers:
        marks = ','.join('?' for _ in identifiers)
        if get_db().execute('SELECT count(*) FROM feeds WHERE id IN (' + marks + ')', identifiers).fetchone()[0] != len(identifiers):
            abort(404, description='情報源が見つかりません。')
        clauses.append('a.feed_id IN (' + marks + ')')
        params.extend(identifiers)
    selected['sources'] = identifiers or None
    return clauses, params, selected
