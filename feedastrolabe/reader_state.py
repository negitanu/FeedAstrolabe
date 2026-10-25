"""Atomic article state updates shared by the HTML reader and public API."""
from . import research as r


def bulk_state(body, where='', params=()):
    values = r.fields(body, {'ids', 'is_read', 'is_starred'})
    ids = values.get('ids')
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 100
            or any(type(x) is not int or not 1 <= x <= 2**63-1 for x in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError('記事 ID は重複なし1〜100件です。')
    columns = {k: int(values[k]) for k in ('is_read', 'is_starred')
               if k in values and type(values[k]) is bool}
    if not columns or len(columns) != len(values)-1:
        raise ValueError('既読・スターは真偽値です。')
    marks = ','.join('?' for _ in ids)
    with r.transaction() as db:
        sql = 'SELECT count(*) FROM articles a' + where + (' AND ' if where else ' WHERE ') + 'a.id IN ('+marks+')'
        if db.execute(sql, [*params, *ids]).fetchone()[0] != len(ids):
            raise r.ResearchMissing('記事が見つからないか現在の表示条件に含まれていません。変更しませんでした。')
        db.execute('UPDATE articles SET '+','.join(k+'=?' for k in columns)+' WHERE id IN ('+marks+')',
                   [*columns.values(), *ids])
    return {'ids': ids, **{k: bool(v) for k, v in columns.items()}}


def library_counts(folder=None):
    """Keep the library unread badge global in full pages and visit responses."""
    from .db import get_db
    db = get_db()
    where = ' WHERE feed_id IN (SELECT id FROM feeds WHERE folder=?)' if folder is not None else ''
    params = (folder,) if folder is not None else ()
    counts = dict(db.execute('SELECT count(*) AS total,coalesce(sum(is_starred),0) AS starred FROM articles' + where, params).fetchone())
    counts['unread'] = db.execute('SELECT count(*) FROM articles WHERE is_read=0').fetchone()[0]
    counts['history'] = db.execute('SELECT count(*) FROM article_visits v JOIN articles ON articles.id=v.article_id' + where, params).fetchone()[0]
    return counts
