"""Locate article neighbours in the full, deterministic reader filter."""

from .db import get_db


def article_navigation(where, params, article_id):
    row = get_db().execute('''
        WITH ordered AS (
            SELECT a.id,
                   row_number() OVER reading_order AS position,
                   lag(a.id) OVER reading_order AS previous_id,
                   lead(a.id) OVER reading_order AS next_id
            FROM articles a''' + where + '''
            WINDOW reading_order AS (ORDER BY a.published_at DESC, a.id DESC)
        )
        SELECT position, previous_id, next_id FROM ordered WHERE id=?
    ''', [*params, article_id]).fetchone()
    if row is None:
        return None

    return {
        'position':row['position'],
        'previous':{'id':row['previous_id']} if row['previous_id'] else None,
        'next':{'id':row['next_id']} if row['next_id'] else None,
    }
