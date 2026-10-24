"""Allowlisted ordering shared by reader keysets and neighbours."""
from flask import abort

VISITED = "(SELECT v.visited_at FROM article_visits v WHERE v.article_id=a.id)"


def ordering(scope=None):
    scope = scope or {}
    order = scope.get('sort') or ('recent' if scope.get('view') == 'history' else 'newest')
    if order not in ('newest', 'oldest', 'recent') or (order == 'recent' and scope.get('view') != 'history'):
        abort(400, description='並び順が不正です。')
    return (VISITED if order == 'recent' else 'a.published_at'), ('ASC' if order == 'oldest' else 'DESC')


def order_sql(scope=None):
    column, direction = ordering(scope)
    return f'{column} {direction}, a.id {direction}'
