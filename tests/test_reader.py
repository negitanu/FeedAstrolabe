import pytest
from feedastrolabe import create_app
from feedastrolabe.db import get_db
from feedastrolabe import collection

RSS = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Example News</title><link>https://example.com/</link><description>News</description>
<item><guid>one</guid><title>First story</title><link>https://example.com/first</link><description><![CDATA[<p>Hello 100% world</p><script>alert(1)</script><a href="javascript:alert(1)">bad</a><img src="https://evil.com/x">]]></description><pubDate>Wed, 07 Oct 2026 12:00:00 GMT</pubDate></item>
<item><guid>two</guid><title>Second story</title><description>Another article</description></item></channel></rss>'''
ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom News</title><id>urn:feed</id><updated>2026-10-07T00:00:00Z</updated><entry><id>urn:atom:1</id><title>Atom story</title><updated>2026-10-07T09:00:00Z</updated><link href="https://example.com/atom"/><content type="html">&lt;p&gt;Atom body&lt;/p&gt;</content></entry></feed>'''
META = {'etag': 'v1', 'modified': 'Wed, 07 Oct 2026 00:00:00 GMT', 'url': 'https://example.com/feed'}

@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(collection, 'fetch', lambda *a: (RSS, META.copy()))
    return create_app({'TESTING': True, 'DATA_DIR': str(tmp_path)})

@pytest.fixture
def client(app):
    return app.test_client()


def post(client, url, data=None, **kwargs):
    client.get('/')
    with client.session_transaction() as session:
        csrf = session['csrf']
    return client.post(url, data={'csrf': csrf, **(data or {})}, **kwargs)


def subscribe(client, url='https://example.com/feed', folder='Technology'):
    return post(client, '/feeds', {'url': url, 'folder': folder}, follow_redirects=True)


def test_empty_health_headers(client):
    response = client.get('/')
    assert response.status_code == 200
    assert 'まだフィードがありません' in response.get_data(as_text=True)
    assert "script-src 'nonce-" in response.headers['Content-Security-Policy']
    assert "script-src 'none'" in client.get('/healthz').headers['Content-Security-Policy']
    assert client.get('/healthz').json == {'status': 'ok'}


def test_register_duplicate_and_invalid(app, client, monkeypatch):
    assert 'フィードを登録しました' in subscribe(client).get_data(as_text=True)
    assert '登録済み' in subscribe(client).get_data(as_text=True)
    monkeypatch.setattr(collection, 'fetch', lambda *a: (b'<html>not a feed</html>', META))
    assert 'RSS または Atom' in subscribe(client, 'https://example.com/invalid').get_data(as_text=True)
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM feeds').fetchone()[0] == 1
        assert get_db().execute('SELECT count(*) FROM articles').fetchone()[0] == 2


def test_atom(app, client, monkeypatch):
    monkeypatch.setattr(collection, 'fetch', lambda *a: (ATOM, META))
    subscribe(client)
    with app.app_context():
        article = get_db().execute('SELECT * FROM articles').fetchone()
        assert article['guid'] == 'urn:atom:1'
        assert article['published_at'] == '2026-10-07 09:00:00'
        assert 'Atom body' in article['content']


def test_idempotence_and_restart(app, client, monkeypatch):
    subscribe(client)
    post(client, '/articles/1/read', {'value': '1'})
    post(client, '/articles/1/star', {'value': '1'})
    monkeypatch.setattr(collection, 'fetch', lambda *a: (RSS.replace(b'First story', b'Updated title'), META))
    post(client, '/refresh')
    restarted = create_app({'TESTING': True, 'DATA_DIR': app.instance_path})
    assert restarted.secret_key == app.secret_key
    with restarted.app_context():
        rows = get_db().execute('SELECT * FROM articles ORDER BY id').fetchall()
        assert len(rows) == 2
        assert rows[0]['title'] == 'Updated title'
        assert rows[0]['is_read'] == rows[0]['is_starred'] == 1


def test_304_and_error_isolation(app, client, monkeypatch):
    subscribe(client)
    seen = []
    def unchanged(url, etag, modified):
        seen.append((etag, modified))
        return None, {'etag': None, 'modified': None, 'url': url}
    monkeypatch.setattr(collection, 'fetch', unchanged)
    post(client, '/refresh')
    assert seen == [('v1', META['modified'])]
    with app.app_context():
        assert get_db().execute('SELECT etag FROM feeds').fetchone()[0] == 'v1'
    monkeypatch.setattr(collection, 'fetch', lambda *a: (RSS, META))
    subscribe(client, 'https://example.com/other')
    def failure(url, *args):
        if url.endswith('/feed'):
            raise ValueError('HTTP 503')
        return RSS, META
    monkeypatch.setattr(collection, 'fetch', failure)
    result = post(client, '/refresh', follow_redirects=True)
    assert '1 件成功、1 件失敗' in result.get_data(as_text=True)
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM articles').fetchone()[0] == 4
        feeds = get_db().execute('SELECT * FROM feeds ORDER BY id').fetchall()
        assert feeds[0]['error'] == 'HTTP 503'
        assert feeds[1]['error'] is None
    result = client.get('/?feed=1')
    assert 'HTTP 503' in result.get_data(as_text=True)


def test_filters_search_and_scoped_bulk(app, client):
    subscribe(client)
    subscribe(client, 'https://example.com/other')
    post(client, '/articles/1/star', {'value': '1'})
    text = client.get('/?view=starred&q=First&feed=1').get_data(as_text=True)
    assert 'First story' in text and 'Second story' not in text
    assert 'First story' in client.get('/?q=100%25').get_data(as_text=True)
    assert 'First story' not in client.get('/?q=100_').get_data(as_text=True)
    assert client.get('/?q=%27%20OR%201%3D1--').status_code == 200
    post(client, '/articles/read-all', {'view': 'starred', 'feed': '1', 'q': 'First'})
    with app.app_context():
        assert [r[0] for r in get_db().execute('SELECT is_read FROM articles ORDER BY id')] == [1, 0, 0, 0]
    text = client.get('/?view=unread&feed=1').get_data(as_text=True)
    assert 'First story' not in text and 'Second story' in text


def test_detail_safe_and_get_read_only(app, client):
    subscribe(client)
    result = client.get('/?article=1')
    text = result.get_data(as_text=True)
    assert '<script>alert' not in text and 'javascript:' not in text
    from test_reader_navigation import markup
    assert not markup(result.data).findall('.//div[@class="prose"]//img')
    assert all(img.get('class')=='article-hero' for img in markup(result.data).findall('.//img'))
    assert text.count('<script') == 8 and 'feed-disclosure.js' in text and 'article-layout.js' in text
    assert '<p>Hello 100% world</p>' in text
    assert 'rel="noopener noreferrer"' in text
    with app.app_context():
        assert get_db().execute('SELECT is_read FROM articles WHERE id=1').fetchone()[0] == 0
    assert client.get('/?article=999').status_code == 404


def test_pagination(app, client):
    subscribe(client)
    with app.app_context():
        db = get_db()
        with db:
            for i in range(31):
                db.execute("INSERT INTO articles(feed_id,guid,title,content,search_text,published_at) VALUES(1,?,?, '', '', '2026-10-08 00:00:00')", (f'p{i}', f'PAGE STORY {i}'))
    text = client.get('/?page=1').get_data(as_text=True)
    assert text.count('class="article-card') == 30
    text = client.get('/?page=2').get_data(as_text=True)
    assert text.count('class="article-card') == 30
    from test_reader_navigation import markup
    next_url = markup(text.encode()).find('.//*[@data-article-loader]').get('data-more-url')
    response = client.get(next_url)
    assert response.status_code == 200 and response.json['html'].count('class="article-card') == 3
    assert response.json['next'] is None
    assert ' ページ' not in text
    assert client.get('/?page=-4').status_code == 200


def test_folder_delete_and_csrf(app, client):
    subscribe(client)
    assert client.post('/feeds/1/delete').status_code == 400
    assert post(client, '/feeds/1/folder', {'folder': 'Science'}).status_code == 302
    assert 'Science' in client.get('/').get_data(as_text=True)
    post(client, '/feeds/1/delete')
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM articles').fetchone()[0] == 0
    assert post(client, '/articles/999/read', {'value': '1'}).status_code == 404
    assert post(client, '/articles/1/star', {'value': '2'}).status_code == 400

@pytest.mark.parametrize('target', ['https://evil.com', '//evil.com', '/\\evil.com'])
def test_return_path(client, target):
    response = post(client, '/articles/read-all', {'next': target})
    assert response.location == '/'


def test_lock_and_worker(app, client):
    with app.app_context(), collection.refresh_lock():
        with pytest.raises(ValueError, match='更新処理が実行中'):
            collection.refresh_feeds()
        response = post(client, '/refresh', follow_redirects=True)
        assert '更新処理が実行中' in response.get_data(as_text=True)
    result = app.test_cli_runner().invoke(args=['worker', '--once'])
    assert result.exit_code == 0 and 'success=0' in result.output
    assert app.test_cli_runner().invoke(args=['worker', '--interval', '2', '--once']).exit_code != 0


def test_fallback_guid(app, client, monkeypatch):
    body = b'<rss version="2.0"><channel><title>Fallback</title><item><title>Stable title</title><description>Stable body</description></item></channel></rss>'
    monkeypatch.setattr(collection, 'fetch', lambda *a: (body, META))
    subscribe(client)
    post(client, '/refresh')
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM articles').fetchone()[0] == 1


def test_unicode_csrf_rejected(client):
    client.get('/')
    assert client.post('/articles/read-all', data={'csrf': '無効'}).status_code == 400


def test_fallback_guid_ignores_body_edits(app, client, monkeypatch):
    first = b'<rss version="2.0"><channel><title>Fallback</title><item><title>Stable title</title><description>Body A</description></item></channel></rss>'
    second = b'<rss version="2.0"><channel><title>Fallback</title><item><title>Stable title</title><description>Body B changed</description></item></channel></rss>'
    monkeypatch.setattr(collection, 'fetch', lambda *a: (first, META))
    subscribe(client)
    monkeypatch.setattr(collection, 'fetch', lambda *a: (second, META))
    post(client, '/refresh')
    with app.app_context():
        rows = get_db().execute('SELECT title,search_text FROM articles').fetchall()
        assert len(rows) == 1
        assert rows[0]['title'] == 'Stable title'
        assert 'Body B' in rows[0]['search_text']

def test_read_all_prefers_form_over_query(app, client):
    subscribe(client)
    subscribe(client, 'https://example.com/other')
    response = post(client, '/articles/read-all?feed=2', {'view': 'all', 'feed': '1', 'q': ''})
    assert response.status_code == 302
    with app.app_context():
        rows = get_db().execute('SELECT feed_id,is_read FROM articles ORDER BY id').fetchall()
        assert [(r['feed_id'], r['is_read']) for r in rows] == [(1, 1), (1, 1), (2, 0), (2, 0)]

def test_published_at_updates_when_source_date_changes(app, client, monkeypatch):
    first = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Dates</title>
<item><guid>dated</guid><title>Dated</title><description>Hello</description><pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item></channel></rss>'''
    second = first.replace(b'01 Jan 2024', b'01 Jan 2025')
    monkeypatch.setattr(collection, 'fetch', lambda *a: (first, META))
    subscribe(client)
    monkeypatch.setattr(collection, 'fetch', lambda *a: (second, META))
    post(client, '/refresh')
    text = client.get('/').get_data(as_text=True)
    assert '2025-01-01' in text
    with app.app_context():
        row = get_db().execute('SELECT published_at,source_published_at FROM articles').fetchone()
        assert row['published_at'] == '2025-01-01 00:00:00'
        assert row['source_published_at'] == '2025-01-01 00:00:00'

def test_detail_respects_filters_and_missing_feed(app, client):
    subscribe(client)
    post(client, '/articles/1/star', {'value': '1'})
    assert client.get('/?view=starred&article=2').status_code == 404
    assert client.get('/?feed=999').status_code == 404
    assert client.get('/?view=starred&article=1').status_code == 200

def test_read_all_rejects_invalid_view(client):
    assert post(client, '/articles/read-all', {'view': 'bogus'}).status_code == 400

def test_query_too_long_rejected(client):
    assert client.get('/?q=' + ('a' * 201)).status_code == 400

def test_reading_prefs_and_open_marks_read(app, client):
    subscribe(client)
    post(client, '/reading-prefs', {'list_density': 'compact', 'mark_read_on_open': '1', 'scan_after_read': '1'})
    text = client.get('/').get_data(as_text=True)
    assert 'density-compact' in text
    assert 'class="open-form"' not in text
    response = post(client, '/articles/1/open', {'view': 'unread'})
    assert 'article=1' in response.location
    post(client, '/articles/1/visit')
    with app.app_context():
        assert get_db().execute('SELECT is_read FROM articles WHERE id=1').fetchone()[0] == 1
    assert client.get('/?article=1').status_code == 200

def test_sidebar_preserves_search(app, client):
    subscribe(client)
    text = client.get('/?q=First&view=unread').get_data(as_text=True)
    assert 'q=First' in text
    assert 'view=unread' in text
