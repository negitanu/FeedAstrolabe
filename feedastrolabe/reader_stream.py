"""Filter-bound keyset continuation for the HTML reader (not API pagination)."""
from flask import abort, current_app
from itsdangerous import URLSafeSerializer, BadData
from .db import get_db
from .reader_order import ordering, order_sql, VISITED

BATCH_SIZE = 30


def serializer():
    return URLSafeSerializer(current_app.secret_key, salt='reader-continuation-v1')


def batch(where, params, scope, cursor=None, all_results=False):
    values = list(params)
    bound_scope = {'filters': scope, 'params': values.copy()}
    column, direction = ordering(scope)
    if cursor is not None:
        try:
            if not isinstance(cursor,str) or len(cursor)>16384:
                raise ValueError()
            data = serializer().loads(cursor)
            if (not isinstance(data,dict) or data.get('v')!=1 or data.get('scope')!=bound_scope or
                    type(data.get('id')) is not int or not 1<=data['id']<=2**63-1 or
                    not isinstance(data.get('date'),str) or len(data['date'])>80):
                raise ValueError()
        except (BadData,ValueError,TypeError):
            abort(400, description='記事の読み込み条件が無効です。一覧を開き直してください。')
        where += (' AND ' if where else ' WHERE ') + f'({column},a.id){">" if direction=="ASC" else "<"}(?,?)'
        values += [data['date'],data['id']]
    sql = f'SELECT a.*,f.title AS feed_title,{column} AS order_date,{VISITED} AS visited_at FROM articles a JOIN feeds f ON f.id=a.feed_id' + where + ' ORDER BY '+order_sql(scope)
    if not all_results:
        sql += ' LIMIT ?'; values.append(BATCH_SIZE+1)
    rows = get_db().execute(sql,values).fetchall()
    more = not all_results and len(rows)>BATCH_SIZE
    rows = rows[:BATCH_SIZE] if more else rows
    token = serializer().dumps({'v':1,'scope':bound_scope,'date':rows[-1]['order_date'],'id':rows[-1]['id']}) if more else None
    return rows, token
