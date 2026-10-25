"""Locate article neighbours in the full, deterministic reader filter."""

from .db import get_db
from .reader_order import order_sql


def article_navigation(where, params, article_id, scope=None):
    order = order_sql(scope)
    row = get_db().execute('''
        WITH ordered AS (
            SELECT a.id,
                   row_number() OVER reading_order AS position,
                   count(*) OVER () AS total,
                   lag(a.id) OVER reading_order AS previous_id,
                   lead(a.id) OVER reading_order AS next_id
            FROM articles a''' + where + '''
            WINDOW reading_order AS (ORDER BY ''' + order + ''')
        )
        SELECT position, total, previous_id, next_id FROM ordered WHERE id=?
    ''', [*params, article_id]).fetchone()
    if row is None:
        return None

    return {
        'position':row['position'],
        'total':row['total'],
        'previous':{'id':row['previous_id']} if row['previous_id'] else None,
        'next':{'id':row['next_id']} if row['next_id'] else None,
    }
