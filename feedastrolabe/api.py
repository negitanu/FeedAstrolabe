from flask import Blueprint, abort, request, url_for
from .db import get_db
from .keys import authenticate_api
from .collection import add_feed
from .fetch import normalize_url
from .preferences import bounded_int
from .social import add_social

api = Blueprint('api', __name__, url_prefix='/api/v1')
api.before_request(authenticate_api)


def feed_record(row):
    result = dict(row)
    result['enabled'] = bool(result['enabled'])
    for field in ('page_cursor', 'pending_newest', 'since_id'):
        result.pop(field, None)
    return result


def article_record(row):
    result = dict(row)
    result['is_read'] = bool(result['is_read'])
    result['is_starred'] = bool(result['is_starred'])
    result.pop('search_text', None)
    return result


def integer_arg(name, default, minimum=1, maximum=2**63-1):
    try:
        return bounded_int(request.args.get(name, default), minimum, maximum, name)
    except ValueError as exc:
        abort(400, description=str(exc))


@api.get('/feeds')
def list_feeds():
    return {'data': [feed_record(r) for r in get_db().execute('SELECT * FROM feeds ORDER BY id')]}


@api.get('/feeds/<int:feed_id>')
def get_feed(feed_id):
    row = get_db().execute('SELECT * FROM feeds WHERE id=?', (feed_id,)).fetchone()
    if row is None:
        abort(404, description='Feed not found')
    return {'data': feed_record(row)}


@api.post('/feeds')
def create_feed():
    body = request.get_json()
    if not isinstance(body, dict):
        abort(400, description='Supply a JSON object')
    source_type = body.get('source_type', 'rss')
    allowed = {'source_type', 'url', 'folder'} if source_type == 'rss' else {'source_type', 'source_kind', 'target', 'instance_url', 'folder'}
    if set(body) - allowed:
        abort(400, description='Unsupported fields; credentials must use server secret files')
    if source_type != 'rss':
        if source_type not in ('x', 'mastodon'):
            abort(400, description='Unsupported source_type')
        try:
            feed_id = add_social(source_type, body.get('source_kind', 'account'), body.get('target', ''), body.get('instance_url', ''), body.get('folder', ''))
        except ValueError as exc:
            if '登録済み' in str(exc):
                abort(409, description='Feed already exists')
            abort(400, description=str(exc))
        return get_feed(feed_id), 201, {'Location': url_for('api.get_feed', feed_id=feed_id)}
    if not isinstance(body.get('url'), str) or not isinstance(body.get('folder', ''), str):
        abort(400, description='url and folder must be strings')
    try:
        url = normalize_url(body['url'].strip())
    except ValueError as exc:
        abort(400, description=str(exc))
    if get_db().execute('SELECT id FROM feeds WHERE url=?', (url,)).fetchone():
        abort(409, description='Feed already exists')
    try:
        feed_id = add_feed(url, body.get('folder', '').strip()[:80])
    except ValueError as exc:
        abort(400, description=str(exc))
    except Exception:
        abort(502, description='Feed could not be retrieved')
    return get_feed(feed_id), 201, {'Location': url_for('api.get_feed', feed_id=feed_id)}


@api.get('/articles')
def list_articles():
    clauses, params = [], []
    if 'source_type' in request.args:
        if request.args['source_type'] not in ('rss', 'x', 'mastodon'):
            abort(400, description='Unsupported source_type')
        clauses.append('f.source_type=?')
        params.append(request.args['source_type'])
    limit = integer_arg('limit', 30, maximum=100)
    feed_id = integer_arg('feed', None) if 'feed' in request.args else None
    before = integer_arg('before_id', None) if 'before_id' in request.args else None
    after = integer_arg('after_id', None, minimum=0) if 'after_id' in request.args else None
    if before is not None and after is not None:
        abort(400, description='Use either before_id or after_id')
    if feed_id:
        clauses.append('a.feed_id=?')
        params.append(feed_id)
    for name in ('is_read', 'is_starred'):
        if name in request.args:
            if request.args[name] not in ('true', 'false'):
                abort(400, description=name + ' must be true or false')
            clauses.append(f'a.{name}=?')
            params.append(int(request.args[name] == 'true'))
    query = request.args.get('q', '').strip()
    if len(query) > 200:
        abort(400, description='q must be at most 200 characters')
    if query:
        clauses.append("(a.title LIKE ? ESCAPE '!' OR a.search_text LIKE ? ESCAPE '!')")
        escaped = query.replace('!', '!!').replace('%', '!%').replace('_', '!_')
        params.extend(['%' + escaped + '%'] * 2)
    if before is not None:
        clauses.append('a.id<?')
        params.append(before)
    if after is not None:
        clauses.append('a.id>?')
        params.append(after)
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    direction = 'ASC' if after is not None else 'DESC'
    rows = get_db().execute('SELECT a.*,f.title AS feed_title,f.source_type AS source_type FROM articles a JOIN feeds f ON f.id=a.feed_id' + where + f' ORDER BY a.id {direction} LIMIT ?', params + [limit + 1]).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {'data': [article_record(r) for r in rows], 'has_more': has_more,
            'next_before_id': rows[-1]['id'] if rows and after is None and has_more else None,
            'next_after_id': rows[-1]['id'] if rows and after is not None else after}


@api.get('/articles/<int:article_id>')
def get_article(article_id):
    row = get_db().execute('SELECT a.*,f.title AS feed_title,f.source_type AS source_type FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE a.id=?', (article_id,)).fetchone()
    if row is None:
        abort(404, description='Article not found')
    return {'data': article_record(row)}


@api.patch('/articles/<int:article_id>')
def update_article(article_id):
    body = request.get_json()
    allowed = {'is_read', 'is_starred'}
    if not isinstance(body, dict) or not body or set(body) - allowed or any(type(v) is not bool for v in body.values()):
        abort(400, description='Supply is_read and/or is_starred as JSON booleans')
    db = get_db()
    with db:
        result = db.execute('UPDATE articles SET ' + ','.join(k + '=?' for k in body) + ' WHERE id=?', [int(v) for v in body.values()] + [article_id])
        if not result.rowcount:
            abort(404, description='Article not found')
    return get_article(article_id)
