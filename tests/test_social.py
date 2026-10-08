import importlib.util
import json
import socket
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from feedastrolabe import collection, create_app, social, social_http
from feedastrolabe.db import get_db, init_database, connect, SCHEMA
from feedastrolabe.maintenance import backup, restore
from feedastrolabe.opml import export_opml
from feedastrolabe.preferences import preferences, due_at
from test_reader import app, client, post, subscribe
from test_phase_two import authorization


def xpost(post_id, text='Hello <script>unsafe</script>'):
    return {'id': str(post_id), 'text': text, 'created_at': '2026-10-08T00:00:00Z'}


def mastodon_post(post_id, visibility='public'):
    return {'id': str(post_id), 'visibility': visibility, 'content': '<p>Hello</p><img src="https://evil.example/a"><a href="javascript:bad">bad</a>',
            'url': 'https://example.com/@alice/' + str(post_id), 'created_at': '2026-10-08T10:00:00+09:00', 'spoiler_text': 'Spoiler <b>text</b>'}


@pytest.fixture
def token_file(app, tmp_path):
    path = tmp_path / 'x-token.txt'
    path.write_text('fixture-' + 'a' * 24)
    path.chmod(0o600)
    app.config['X_TOKEN_FILE'] = str(path)
    return path


def test_registration_scopes_validation_and_no_fetch(app, client, monkeypatch):
    monkeypatch.setattr(social, 'request_json', lambda *args: pytest.fail('Registration must not fetch'))
    _, _, read = authorization(app)
    _, _, write = authorization(app, 'write')
    body = {'source_type': 'x', 'target': '@Alice'}
    assert client.post('/api/v1/feeds', json=body, headers=read).status_code == 403
    response = client.post('/api/v1/feeds', json=body, headers=write)
    assert response.status_code == 201 and response.json['data']['target'] == 'alice'
    assert response.json['data']['source_type'] == 'x'
    assert 'page_cursor' not in response.json['data']
    assert client.post('/api/v1/feeds', json=body, headers=write).status_code == 409
    assert client.post('/api/v1/feeds', json={**body, 'token': 'never-store'}, headers=write).status_code == 400
    assert client.post('/settings/social', data=body).status_code == 400
    response = post(client, '/settings/social', {'source_type': 'mastodon', 'source_kind': 'account', 'target': 'Alice', 'instance_url': 'https://example.com'}, follow_redirects=True)
    assert 'SNS を登録しました' in response.get_data(as_text=True)
    assert 'SOCIAL SOURCES' in response.get_data(as_text=True)
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM feeds').fetchone()[0] == 2
        assert b'x.com' not in export_opml() and b'@alice' not in export_opml()


@pytest.mark.parametrize('provider,kind,target,origin', [
    ('x','list','bad',''),('x','account','a/b',''),('x','account','alice','https://evil.example'),
    ('mastodon','list','alice','https://example.com'),('mastodon','account','alice','http://example.com'),
    ('mastodon','account','alice','https://127.0.0.1'),('mastodon','account','alice','https://example.com/path'),
    ('mastodon','account','alice','https://example.com/?token=foo'),('mastodon','account','alice@remote.example','https://example.com'),
    ('other','account','alice',''),('x','account',None,'')])
def test_invalid_sources(provider,kind,target,origin):
    with pytest.raises(ValueError):
        social.source_values(provider,kind,target,origin)


def test_x_lookup_baseline_state_and_unified_api(app, client, token_file, monkeypatch):
    seen = []
    def request(url, token=None):
        seen.append((url, token))
        if '/by/username/' in url:
            return {'data': {'id': '123'}}, {}
        return {'data': [xpost(20), xpost(10)], 'meta': {'next_token': 'older-page'}}, {}
    monkeypatch.setattr(social, 'request_json', request)
    with app.app_context():
        feed_id = social.add_social('x','account','alice')
        assert collection.refresh_feeds(feed_id) == (1,0)
        db=get_db()
        feed=db.execute('SELECT * FROM feeds').fetchone()
        assert feed['since_id']=='20' and feed['page_cursor'] is None
        article=db.execute('SELECT * FROM articles WHERE guid=?', ('x:20',)).fetchone()
        assert '&lt;script&gt;' in article['content'] and '<script>' not in article['content']
        article_id=article['id']
    post(client, f'/articles/{article_id}/read', {'value':'1'})
    post(client, f'/articles/{article_id}/star', {'value':'1'})
    monkeypatch.setattr(social, 'request_json', lambda *a: ({'data':[xpost(20,'edited')],'meta':{}},{}))
    with app.app_context():
        assert collection.refresh_feeds(feed_id)==(1,0)
        article=get_db().execute('SELECT * FROM articles WHERE id=?',(article_id,)).fetchone()
        assert article['title']=='edited' and article['is_read']==article['is_starred']==1
    _,_,headers=authorization(app)
    data=client.get('/api/v1/articles?source_type=x&q=edited',headers=headers).json['data']
    assert len(data)==1 and data[0]['source_type']=='x'
    assert client.get('/api/v1/articles?source_type=other',headers=headers).status_code==400
    assert all(token=='fixture-'+'a'*24 for _,token in seen)


def test_durable_pages_resume_after_failure_and_restart(app, token_file, monkeypatch):
    with app.app_context():
        feed_id=social.add_social('x','account','123')
        db=get_db()
        with db:
            db.execute("UPDATE feeds SET since_id='10',success_at='2020-01-01 00:00:00'")
    calls=[]
    fail=True
    def request(url,token=None):
        nonlocal fail
        params=parse_qs(urlsplit(url).query)
        assert params['since_id']==['10']
        cursor=params.get('pagination_token',[''])[0]
        calls.append(cursor)
        if cursor=='p2' and fail:
            fail=False
            raise social_http.SocialError('temporary')
        pages={'':([xpost(50)],'p2'),'p2':([xpost(40)],'p3'),'p3':([xpost(30)],'p4'),'p4':([xpost(20)],None)}
        rows,next_token=pages[cursor]
        return {'data':rows,'meta':{'next_token':next_token} if next_token else {}},{}
    monkeypatch.setattr(social,'request_json',request)
    with app.app_context():
        assert collection.refresh_feeds(feed_id)==(0,1)
        row=get_db().execute('SELECT * FROM feeds').fetchone()
        assert row['since_id']=='10' and row['page_cursor']=='p2' and row['pending_newest']=='50'
        assert get_db().execute('SELECT count(*) FROM articles').fetchone()[0]==1
    restarted=create_app({'TESTING':True,'DATA_DIR':app.instance_path,'X_TOKEN_FILE':str(token_file)})
    with restarted.app_context():
        assert collection.refresh_feeds(feed_id)==(1,0)
        row=get_db().execute('SELECT * FROM feeds').fetchone()
        assert row['since_id']=='50' and row['page_cursor'] is None
        assert get_db().execute('SELECT count(*) FROM articles').fetchone()[0]==4
    assert calls==['','p2','p2','p3','p4']


def test_three_page_budget_and_x_list_boundary(app, token_file, monkeypatch):
    with app.app_context():
        feed_id=social.add_social('x','list','123')
        db=get_db()
        with db:
            db.execute("UPDATE feeds SET since_id='10',success_at='2020-01-01 00:00:00'")
        seen=[]
        def request(url,token=None):
            params=parse_qs(urlsplit(url).query)
            assert 'since_id' not in params and '/lists/123/tweets' in url
            cursor=params.get('pagination_token',[''])[0]
            seen.append(cursor)
            if cursor=='p3':
                return {'data':[xpost(20),xpost(10)],'meta':{'next_token':'older'}},{}
            number=int(cursor[1:]) if cursor else 0
            return {'data':[xpost(50-number*10)],'meta':{'next_token':'p'+str(number+1)}},{}
        monkeypatch.setattr(social,'request_json',request)
        assert collection.refresh_feeds(feed_id)==(1,0)
        row=db.execute('SELECT * FROM feeds').fetchone()
        assert row['since_id']=='10' and row['page_cursor']=='p3'
        assert collection.refresh_feeds(feed_id)==(1,0)
        row=db.execute('SELECT * FROM feeds').fetchone()
        assert row['since_id']=='50' and row['page_cursor'] is None
        assert len(seen)==4 and db.execute('SELECT count(*) FROM articles').fetchone()[0]==4


def test_mastodon_public_content_pagination(app, monkeypatch):
    calls=[]
    def request(url,token=None):
        assert token is None
        calls.append(url)
        if '/lookup?' in url:
            return {'id':'123'},{}
        return [mastodon_post(20),mastodon_post(19,'private')],{}
    monkeypatch.setattr(social,'request_json',request)
    with app.app_context():
        feed_id=social.add_social('mastodon','account','alice','https://example.com')
        assert collection.refresh_feeds(feed_id)==(1,0)
        db=get_db()
        article=db.execute('SELECT * FROM articles').fetchone()
        assert db.execute('SELECT count(*) FROM articles').fetchone()[0]==1
        assert '<img' not in article['content'] and 'javascript:' not in article['content']
        assert 'Spoiler' in article['content'] and article['published_at']=='2026-10-08 01:00:00'
        assert db.execute('SELECT since_id FROM feeds').fetchone()[0]=='20'
        with db:
            db.execute("UPDATE feeds SET since_id='10',page_cursor='60',pending_newest='100'")
        monkeypatch.setattr(social,'request_json',lambda *a: ([mastodon_post(n) for n in range(60,20,-1)],{}))
        assert collection.refresh_feeds(feed_id)==(0,1)  # Same repeated page cannot silently advance.
        assert '進みません' in db.execute('SELECT error FROM feeds').fetchone()[0]


def test_rate_limit_shared_manual_pause_and_redaction(app, token_file, monkeypatch, caplog):
    calls=[]
    def request(url,token=None):
        calls.append(url)
        raise social_http.SocialError('レート上限', '2099-01-01 00:00:00')
    monkeypatch.setattr(social,'request_json',request)
    with app.app_context():
        first=social.add_social('x','account','123')
        second=social.add_social('x','list','456')
        assert collection.refresh_feeds()==(0,1)
        assert len(calls)==1
        assert collection.refresh_feeds(second)==(0,0)
        row=dict(get_db().execute('SELECT * FROM feeds WHERE id=?',(first,)).fetchone())
        assert due_at(row,preferences()).strftime('%Y-%m-%d %H:%M:%S')=='2099-01-01 00:00:00'
        with get_db():
            get_db().execute('DELETE FROM provider_cooldowns')
            get_db().execute('UPDATE feeds SET retry_at=NULL')
        monkeypatch.setattr(social,'request_json',lambda *a: (_ for _ in ()).throw(RuntimeError('secret-'+token_file.read_text())))
        assert collection.refresh_feeds(first)==(0,1)
        error=get_db().execute('SELECT error FROM feeds WHERE id=?',(first,)).fetchone()[0]
        assert 'secret-' not in error and token_file.read_text() not in caplog.text


def test_token_file_missing_permissions_symlink_and_rotation(app, token_file, tmp_path):
    with app.app_context():
        assert social.x_token()==token_file.read_text()
        token_file.chmod(0o644)
        with pytest.raises(social_http.SocialError): social.x_token()
        token_file.chmod(0o600)
        link=tmp_path/'link';link.symlink_to(token_file)
        app.config['X_TOKEN_FILE']=str(link)
        with pytest.raises(social_http.SocialError): social.x_token()
        app.config['X_TOKEN_FILE']=str(token_file)
        token_file.write_text('rotated-'+'b'*24)
        assert social.x_token()==token_file.read_text()
        token_file.unlink()
        with pytest.raises(social_http.SocialError): social.x_token()


class Response:
    def __init__(self,status=200,headers=None,body=b'{"data":[]}'):
        self.status,self.headers,self.body=status,headers or {},body
    def getheaders(self):return list(self.headers.items())
    def read1(self,size):
        value,self.body=self.body[:size],self.body[size:]
        return value


def mock_http(monkeypatch,response):
    calls=[]
    class Connection:
        sock=None
        def __init__(self,*args):calls.append({'args':args})
        def request(self,method,path,headers):calls[-1].update(path=path,headers=headers)
        def getresponse(self):return response
        def close(self):calls[-1]['closed']=True
    monkeypatch.setattr(social_http,'PinnedHTTP',Connection)
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('1.1.1.1',443))])
    return calls


@pytest.mark.parametrize('status,headers,body',[(302,{'Location':'https://evil.example'},b''),(401,{},b'secret'),(403,{},b'secret'),(500,{},b'secret'),(200,{'Content-Encoding':'gzip'},b''),(200,{},b'invalid secret'),(200,{'Content-Length':str(social_http.MAX_BYTES+1)},b'')])
def test_http_rejects_without_raw_body_or_redirect(monkeypatch,status,headers,body):
    calls=mock_http(monkeypatch,Response(status,headers,body))
    with pytest.raises(social_http.SocialError) as error:
        social_http.request_json('https://api.x.com/2/test','fixture-token')
    assert 'secret' not in str(error.value) and len(calls)==1 and calls[0]['closed']


def test_http_confinement_private_dns_and_429(monkeypatch):
    calls=mock_http(monkeypatch,Response())
    with pytest.raises(social_http.SocialError):social_http.request_json('https://evil.example/', 'fixture-token')
    assert not calls
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(social_http.SocialError):social_http.request_json('https://example.com/')
    assert not calls
    calls=mock_http(monkeypatch,Response(429,{'Retry-After':'3600'},b'secret'))
    with pytest.raises(social_http.SocialError) as error:social_http.request_json('https://api.x.com/2/test','fixture-token')
    assert error.value.retry_at and 'secret' not in str(error.value)
    assert calls[0]['headers']['Authorization']=='Bearer fixture-token'


def test_v2_migration_and_v3_restore(app,tmp_path):
    # Build the exact committed v2 schema without relying on current migrations.
    source=tmp_path/'v2.sqlite3'
    with sqlite3.connect(source) as db:
        db.executescript(SCHEMA)
        db.executescript("""
          ALTER TABLE feeds ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1));
          ALTER TABLE feeds ADD COLUMN poll_interval INTEGER CHECK(poll_interval BETWEEN 60 AND 86400);
          ALTER TABLE feeds ADD COLUMN failures INTEGER NOT NULL DEFAULT 0;
          CREATE TABLE settings (id INTEGER PRIMARY KEY CHECK(id=1), poll_interval INTEGER NOT NULL DEFAULT 900,
            polling_enabled INTEGER NOT NULL DEFAULT 1, page_size INTEGER NOT NULL DEFAULT 30,
            default_view TEXT NOT NULL DEFAULT 'all', api_rate_limit INTEGER NOT NULL DEFAULT 120);
          INSERT INTO settings(id) VALUES(1);
          CREATE TABLE api_keys (id INTEGER PRIMARY KEY, name TEXT NOT NULL, prefix TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE, scope TEXT NOT NULL CHECK(scope IN ('read','write')),
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT, last_used_at TEXT,
            rate_window INTEGER NOT NULL DEFAULT 0, rate_count INTEGER NOT NULL DEFAULT 0);
          PRAGMA user_version=2;
        """)
    with connect(source) as db:
        db.execute("INSERT INTO feeds(url,title,created_at) VALUES('https://example.com/rss','old','2026-01-01')")
        db.execute("INSERT INTO articles(feed_id,guid,title,content,search_text,published_at,is_read,is_starred) VALUES(1,'one','Saved','safe','safe','2026-01-01',1,1)")
    init_database(source);init_database(source)
    with connect(source) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==7
        assert db.execute('SELECT source_type FROM feeds').fetchone()[0]=='rss'
        assert tuple(db.execute('SELECT is_read,is_starred FROM articles').fetchone())==(1,1)
    snapshot=tmp_path/'snapshot.sqlite3';backup(source,snapshot)
    restored=tmp_path/'restored'/'feeds.sqlite3';restore(snapshot,restored)
    with connect(restored) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==7
        assert db.execute('SELECT title FROM articles').fetchone()[0]=='Saved'


def test_secret_scanner_synthetic_detection():
    path=Path(__file__).resolve().parents[1]/'scripts/check_secrets.py'
    spec=importlib.util.spec_from_file_location('secret_check',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    cases=[(b'AK' + b'IA' + b'A'*16,'aws-access-key'),(b'gh' + b'p_' + b'A'*36,'github-token'),(b'-----BEGIN ' + b'PRIVATE KEY-----','private-key'),(b'api_key = "' + b'A'*40 + b'"','literal-credential')]
    for data,rule in cases:assert rule in module.findings(data)
    assert not module.findings(b'Authorization: Bearer <API key>')
