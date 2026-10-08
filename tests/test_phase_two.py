import io
from datetime import datetime, timedelta, timezone
import hashlib
import sqlite3
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from feedastrolabe import create_app, collection
from feedastrolabe.db import SCHEMA, connect, get_db, init_database
from feedastrolabe.keys import issue_key
from feedastrolabe.preferences import preferences, due_at
from feedastrolabe.maintenance import backup, restore
from feedastrolabe.opml import import_opml, export_opml
from test_reader import RSS, META, app, client, post, subscribe


def authorization(app, scope='read', days=90):
    with app.app_context():
        key_id, token = issue_key('test client', scope, days)
    return key_id, token, {'Authorization': 'Bearer ' + token}


def settings_data(**extra):
    return {'poll_interval': '120', 'polling_enabled': '1', 'page_size': '10', 'default_view': 'unread', 'api_rate_limit': '100', **extra}


def test_v1_migration_backup_restore(tmp_path):
    source = tmp_path / 'v1.sqlite3'
    with sqlite3.connect(source) as db:
        db.executescript(SCHEMA)
        db.execute("INSERT INTO feeds(id,url,title,created_at) VALUES(1,'https://example.com/feed','Old','2026-01-01')")
        db.execute("INSERT INTO articles(id,feed_id,guid,title,content,search_text,published_at,is_read,is_starred) VALUES(1,1,'one','Saved','safe','safe','2026-01-01',1,1)")
        db.execute('PRAGMA user_version=1')
    snapshot = tmp_path / 'snapshot.sqlite3'
    backup(source, snapshot)
    init_database(source)
    init_database(source)
    with connect(source) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 8
        assert tuple(db.execute('SELECT is_read,is_starred FROM articles').fetchone()) == (1, 1)
        assert db.execute('SELECT enabled FROM feeds').fetchone()[0] == 1
        assert db.execute('SELECT poll_interval FROM settings').fetchone()[0] == 900
    destination = tmp_path / 'restore' / 'feeds.sqlite3'
    restore(snapshot, destination)
    with connect(destination) as db:
        assert db.execute('SELECT title FROM articles').fetchone()[0] == 'Saved'
        assert db.execute('PRAGMA user_version').fetchone()[0] == 8
    assert snapshot.stat().st_mode & 0o777 == 0o600


def test_unknown_migration_rollback(tmp_path):
    path = tmp_path / 'future.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA user_version=99')
    with pytest.raises(RuntimeError):
        init_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 99


def test_settings_persist_validate_and_ui(app, client):
    subscribe(client)
    response = post(client, '/settings', settings_data(), follow_redirects=True)
    assert '設定を保存しました' in response.get_data(as_text=True)
    response = post(client, '/settings', settings_data(poll_interval='1'), follow_redirects=True)
    assert '60〜86400' in response.get_data(as_text=True)
    with app.app_context():
        assert preferences()['poll_interval'] == 120
        assert preferences()['page_size'] == 10
    restarted = create_app({'TESTING': True, 'DATA_DIR': app.instance_path})
    with restarted.app_context():
        assert preferences()['default_view'] == 'unread'
    assert '未読の記事' in client.get('/').get_data(as_text=True)
    assert client.post('/settings', data=settings_data()).status_code == 400


def test_due_pause_manual_and_backoff(app, client, monkeypatch):
    subscribe(client)
    subscribe(client, 'https://example.com/other')
    seen = []
    def recording(url, *args):
        seen.append(url)
        return RSS, META
    monkeypatch.setattr(collection, 'fetch', recording)
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE feeds SET checked_at='2020-01-01 00:00:00',poll_interval=60")
            db.execute('UPDATE feeds SET enabled=0 WHERE id=2')
        assert collection.refresh_feeds(due_only=True) == (1, 0)
        assert seen == ['https://example.com/feed']
        seen.clear()
        assert collection.refresh_feeds(due_only=True) == (0, 0)
        assert not seen
        with db:
            db.execute('UPDATE settings SET polling_enabled=0 WHERE id=1')
        assert collection.refresh_feeds(due_only=True) == (0, 0)
        assert collection.refresh_feeds(feed_id=2) == (1, 0)
        with db:
            db.execute("UPDATE feeds SET checked_at='2026-01-01 00:00:00',failures=3 WHERE id=1")
        feed = db.execute('SELECT * FROM feeds WHERE id=1').fetchone()
        assert due_at(feed, preferences()) == datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=480)
    monkeypatch.setattr(collection, 'fetch', lambda *a: (_ for _ in ()).throw(ValueError('offline')))
    post(client, '/refresh', {'feed': '1'})
    with app.app_context():
        assert get_db().execute('SELECT failures FROM feeds WHERE id=1').fetchone()[0] == 4
    monkeypatch.setattr(collection, 'fetch', recording)
    post(client, '/refresh', {'feed': '1'})
    with app.app_context():
        assert get_db().execute('SELECT failures FROM feeds WHERE id=1').fetchone()[0] == 0


def test_feed_settings_validation(app, client):
    subscribe(client)
    post(client, '/settings/feeds/1', {'enabled': '1', 'poll_interval': '600'})
    post(client, '/settings/feeds/1', {'enabled': '1', 'poll_interval': 'abc'})
    with app.app_context():
        assert get_db().execute('SELECT poll_interval FROM feeds').fetchone()[0] == 600
    post(client, '/settings/feeds/1', {'poll_interval': ''})
    with app.app_context():
        row = get_db().execute('SELECT enabled,poll_interval FROM feeds').fetchone()
        assert tuple(row) == (0, None)


def test_key_once_hash_expire_revoke(app, client):
    result = post(client, '/settings/keys', {'name': 'one-time', 'scope': 'read', 'days': '1'})
    text = result.get_data(as_text=True)
    token = text.split('id="issued-token" readonly value="')[1].split('"')[0]
    assert token not in client.get('/settings').get_data(as_text=True)
    with app.app_context():
        key = dict(get_db().execute('SELECT * FROM api_keys').fetchone())
        assert key['token_hash'] == hashlib.sha256(token.encode()).hexdigest()
        assert token not in str(key)
    headers = {'Authorization': 'Bearer ' + token}
    assert client.get('/api/v1/feeds', headers=headers).status_code == 200
    post(client, '/settings/keys/1/revoke')
    assert client.get('/api/v1/feeds', headers=headers).status_code == 401
    key_id, _, expired = authorization(app)
    with app.app_context():
        with get_db() as db:
            db.execute("UPDATE api_keys SET expires_at='2020-01-01 00:00:00' WHERE id=?", (key_id,))
    assert client.get('/api/v1/feeds', headers=expired).status_code == 401
    assert post(client, '/settings/keys', {'name': 'bad', 'scope': 'admin', 'days': '90'}).status_code == 302


def test_api_auth_scope_and_updates(app, client):
    subscribe(client)
    _, _, read = authorization(app)
    _, _, write = authorization(app, 'write')
    assert client.get('/api/v1/feeds').status_code == 401
    assert client.get('/api/v1/feeds?api_key=ignored').status_code == 401
    assert client.get('/api/v1/feeds', headers={'Authorization': 'Bearer bogus'}).status_code == 401
    assert client.patch('/api/v1/articles/1', headers=read, json={'is_read': True}).status_code == 403
    result = client.patch('/api/v1/articles/1', headers=write, json={'is_read': True, 'is_starred': True})
    assert result.status_code == 200 and result.json['data']['is_read'] is True
    assert result.json['data']['is_starred'] is True
    assert client.patch('/api/v1/articles/1', headers=write, json={'is_read': 1}).status_code == 400
    assert client.patch('/api/v1/articles/1', headers=write, json={'title': 'no'}).status_code == 400
    assert client.get('/api/v1/articles/999', headers=read).status_code == 404
    assert client.get('/api/v1/missing', headers=read).is_json
    assert client.post('/feeds', json={'url': 'https://example.com/'}, headers=write).status_code == 400


def test_api_create_feeds(app, client):
    _, _, headers = authorization(app, 'write')
    response = client.post('/api/v1/feeds', headers=headers, json={'url': 'https://example.com/feed', 'folder': 'API'})
    assert response.status_code == 201
    assert response.headers['Location'] == '/api/v1/feeds/1'
    assert response.json['data']['folder'] == 'API'
    assert client.post('/api/v1/feeds', headers=headers, json={'url': 'https://example.com/feed'}).status_code == 409
    assert client.post('/api/v1/feeds', headers=headers, json={'url': 'file:///etc/passwd'}).status_code == 400
    assert client.post('/api/v1/feeds', headers=headers, json=['wrong']).status_code == 400
    assert client.get('/api/v1/feeds', headers=headers).json['data'][0]['enabled'] is True


def test_api_cursor_filters(app, client):
    subscribe(client)
    _, _, headers = authorization(app)
    first = client.get('/api/v1/articles?limit=1', headers=headers).json
    assert first['data'][0]['id'] == 2 and first['has_more']
    assert first['next_before_id'] == 2
    second = client.get('/api/v1/articles?limit=1&before_id=2', headers=headers).json
    assert second['data'][0]['id'] == 1 and not second['has_more']
    first = client.get('/api/v1/articles?limit=1&after_id=0', headers=headers).json
    assert first['data'][0]['id'] == 1 and first['next_after_id'] == 1
    second = client.get('/api/v1/articles?limit=1&after_id=1', headers=headers).json
    assert second['data'][0]['id'] == 2 and not second['has_more']
    assert client.get('/api/v1/articles?feed=1&is_read=false&q=First', headers=headers).json['data'][0]['id'] == 1
    assert not client.get('/api/v1/articles?is_starred=true', headers=headers).json['data']
    for query in ('limit=101', 'feed=no', 'before_id=-1', 'before_id=2&after_id=0', 'is_read=maybe'):
        assert client.get('/api/v1/articles?' + query, headers=headers).status_code == 400


def test_rate_limit_across_clients_persists(app, client):
    _, _, headers = authorization(app)
    with app.app_context():
        with get_db() as db:
            db.execute('UPDATE settings SET api_rate_limit=1')
    assert client.get('/api/v1/feeds', headers=headers).status_code == 200
    response = app.test_client().get('/api/v1/articles', headers=headers)
    assert response.status_code == 429
    assert 1 <= int(response.headers['Retry-After']) <= 60
    with app.app_context():
        with get_db() as db:
            db.execute('UPDATE api_keys SET rate_window=0')
    assert client.get('/api/v1/feeds', headers=headers).status_code == 200


def test_opml_round_trip(app, client, tmp_path, monkeypatch):
    subscribe(client)
    subscribe(client, 'https://example.com/other', 'Research & News')
    exported = client.get('/subscriptions.opml')
    assert exported.status_code == 200 and b'Research &amp; News' in exported.data
    other = create_app({'TESTING': True, 'DATA_DIR': str(tmp_path / 'other')})
    monkeypatch.setattr(collection, 'fetch', lambda *a: pytest.fail('OPML import must not fetch'))
    with other.app_context():
        assert import_opml(exported.data) == (2, 0)
        assert import_opml(exported.data) == (0, 2)
        rows = get_db().execute('SELECT * FROM feeds ORDER BY url').fetchall()
        assert {r['folder'] for r in rows} == {'Technology', 'Research & News'}
        assert all(r['checked_at'] is None for r in rows)

@pytest.mark.parametrize('xml', [
    b'<!DOCTYPE opml [<!ENTITY x SYSTEM "file:///etc/passwd">]><opml><body>&x;</body></opml>',
    b'<opml><body><outline xmlUrl="http://127.0.0.1/feed"/></body></opml>',
    b'<opml><body><outline xmlUrl="https://example.com/feed"/><outline xmlUrl="file:///etc/passwd"/></body></opml>',
    b'<opml><body>' + b'<outline xmlUrl="https://example.com/feed"/>' * 101 + b'</body></opml>',
    b'x' * (1024 * 1024 + 1), b'<wrong/>',
])
def test_unsafe_opml_atomic(app, xml):
    with app.app_context():
        with pytest.raises(ValueError):
            import_opml(xml)
        assert get_db().execute('SELECT count(*) FROM feeds').fetchone()[0] == 0


def test_opml_upload_csrf(client):
    response = post(client, '/settings/opml', {'opml': (io.BytesIO(b'<opml><body><outline xmlUrl="https://example.com/rss"/></body></opml>'), 'feeds.opml')}, follow_redirects=True)
    assert '1 件追加' in response.get_data(as_text=True)
    assert client.post('/settings/opml', data={}).status_code == 400

@pytest.fixture
def protected(tmp_path):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    app = create_app({'TESTING': True, 'DATA_DIR': str(tmp_path), 'ACCESS_MODE': 'cloudflare',
                      'ACCESS_TEAM_DOMAIN': 'https://example.cloudflareaccess.com', 'ACCESS_AUD': 'expected-aud', 'PUBLIC_HOSTS': 'reader.example.com'})
    app.extensions['access_jwks'] = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key()))
    return app, private


def assertion(private, **values):
    current = int(datetime.now(timezone.utc).timestamp())
    payload = {'iss': 'https://example.cloudflareaccess.com', 'aud': ['expected-aud'], 'iat': current - 5, 'exp': current + 300, **values}
    return jwt.encode(payload, private, algorithm='RS256', headers={'kid': 'test'})


def test_access_valid_and_api_double_auth(protected):
    app, private = protected
    client = app.test_client()
    token = assertion(private)
    headers = {'Cf-Access-Jwt-Assertion': token, 'Host': 'reader.example.com'}
    response = client.get('/settings', headers=headers)
    assert response.status_code == 200
    assert 'Secure' in response.headers['Set-Cookie']
    assert client.get('/api/v1/feeds', headers=headers).status_code == 401
    _, _, api_headers = authorization(app)
    assert client.get('/api/v1/feeds', headers=api_headers).status_code == 403
    assert client.get('/api/v1/feeds', headers={**headers, **api_headers}).status_code == 200
    assert client.get('/healthz').status_code == 200
    assert client.get('/settings', headers={**headers, 'Host': 'untrusted.example'}).status_code == 400

@pytest.mark.parametrize('values', [{'exp': 1}, {'aud': ['wrong']}, {'iss': 'https://evil.com'}, {'iat': 4102444800}])
def test_access_invalid_claims(protected, values):
    app, private = protected
    response = app.test_client().get('/', headers={'Cf-Access-Jwt-Assertion': assertion(private, **values)})
    assert response.status_code == 403


def test_access_forged_missing_and_jwks_outage(protected):
    app, private = protected
    client = app.test_client()
    assert client.get('/').status_code == 403
    wrong = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert client.get('/', headers={'Cf-Access-Jwt-Assertion': assertion(wrong)}).status_code == 403
    hs = jwt.encode({'exp': 4102444800}, 'x' * 32, algorithm='HS256')
    assert client.get('/', headers={'Cf-Access-Jwt-Assertion': hs}).status_code == 403
    app.extensions['access_jwks'] = SimpleNamespace(get_signing_key_from_jwt=lambda token: (_ for _ in ()).throw(RuntimeError('offline')))
    assert client.get('/', headers={'Cf-Access-Jwt-Assertion': assertion(private)}).status_code == 403


def test_access_missing_config_refuses_startup(tmp_path):
    with pytest.raises(ValueError, match='requires'):
        create_app({'TESTING': True, 'DATA_DIR': str(tmp_path), 'ACCESS_MODE': 'cloudflare'})



def test_rate_limit_atomic_parallel(app):
    from concurrent.futures import ThreadPoolExecutor
    _, _, headers = authorization(app)
    with app.app_context():
        with get_db() as db:
            db.execute('UPDATE settings SET api_rate_limit=2')
    def request():
        return app.test_client().get('/api/v1/feeds', headers=headers).status_code
    with ThreadPoolExecutor(max_workers=4) as executor:
        codes = list(executor.map(lambda _: request(), range(4)))
    assert sorted(codes) == [200, 200, 429, 429]


def test_openapi_served_and_settings_link(client):
    spec = client.get('/static/openapi.json')
    assert spec.status_code == 200
    assert '/articles/{article_id}' in spec.json['paths']
    assert spec.json['components']['securitySchemes']['BearerKey']['scheme'] == 'bearer'
    assert 'OpenAPI 定義を見る' in client.get('/settings').get_data(as_text=True)



def test_stdin_restore(tmp_path, monkeypatch):
    import sys
    from feedastrolabe import maintenance
    source = tmp_path / 'source.sqlite3'
    init_database(source)
    with connect(source) as db:
        db.execute("UPDATE settings SET page_size=60 WHERE id=1")
    snapshot = tmp_path / 'snapshot.sqlite3'
    backup(source, snapshot)
    data = tmp_path / 'restored'
    monkeypatch.setenv('FEEDASTROLABE_DATA_DIR', str(data))
    monkeypatch.setattr(sys, 'argv', ['maintenance', 'restore', '-'])
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(snapshot.read_bytes())))
    maintenance.main()
    with connect(data / 'feeds.sqlite3') as db:
        assert db.execute('SELECT page_size FROM settings').fetchone()[0] == 60
    assert not list(data.glob('.restore-*'))



@pytest.mark.parametrize('host', ['.example.com', '*.example.com', 'reader..example.com'])
def test_access_rejects_non_explicit_hosts(tmp_path, host):
    with pytest.raises(ValueError, match='explicit'):
        create_app({'TESTING': True, 'DATA_DIR': str(tmp_path), 'ACCESS_MODE': 'cloudflare',
                    'ACCESS_TEAM_DOMAIN': 'https://example.cloudflareaccess.com', 'ACCESS_AUD': 'aud', 'PUBLIC_HOSTS': host})
