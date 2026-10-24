import hashlib
import io
import os
import sqlite3
from threading import Thread

import pytest
from itsdangerous import TimestampSigner
from werkzeug.datastructures import MultiDict
from werkzeug.serving import make_server

from feedastrolabe import collection
from feedastrolabe.db import get_db
from feedastrolabe.import_preview import MAX_PLAN_BYTES, PLAN_MAX_AGE, serializer
from feedastrolabe.opml import import_opml
from test_reader import app, client, post
from test_reader_navigation import markup, content
from test_phase_two import authorization

OPML = b'''<?xml version="1.0"?><opml version="2.0"><body>
<outline text="Existing from file" xmlUrl="https://example.com/existing"/>
<outline text="Research &amp; News">
 <outline text="&lt;script&gt;window.importExecuted=true&lt;/script&gt; First" xmlUrl="https://example.com/one"/>
 <outline text="Second" xmlUrl="https://example.com/two"/>
 <outline text="Duplicate second" xmlUrl="https://EXAMPLE.com:443/two#fragment"/>
</outline></body></opml>'''


@pytest.fixture
def import_library(app, monkeypatch):
    monkeypatch.setattr(collection, 'fetch', lambda *args: pytest.fail('Import must not fetch source URLs'))
    with app.app_context(), get_db() as db:
        db.execute("INSERT INTO feeds(url,title,folder,created_at) VALUES('https://example.com/existing','Original existing','Keep folder','2026-10-11')")


def subscriptions(app):
    with app.app_context():
        return [tuple(row) for row in get_db().execute('SELECT url,title,folder,checked_at FROM feeds ORDER BY id')]


def preview(client, data=OPML):
    response = post(client, '/settings/opml', {'opml': (io.BytesIO(data), 'fixture.opml')})
    assert response.status_code == 200
    token = markup(response.data).find(".//input[@name='plan']").get('value')
    return response, token


def test_preview_is_read_only_ordered_and_cancelable(app, client, import_library):
    before = subscriptions(app)
    response, token = preview(client)
    tree = markup(response.data)
    rows = tree.findall(".//li[@class='opml-preview-entry']")
    assert [content(row.find('.//strong')) for row in rows] == [
        'Existing from file', '<script>window.importExecuted=true</script> First', 'Second', 'Duplicate second']
    assert [content(row.find(".//span[@class='classification-badge']")) for row in rows] == [
        '登録済み', '追加予定', '追加予定', 'ファイル内で重複']
    assert '追加予定 2 件' in response.get_data(as_text=True)
    assert '<script>' not in response.get_data(as_text=True)
    assert '&lt;script&gt;' in response.get_data(as_text=True)
    assert "script-src 'nonce-" in response.headers['Content-Security-Policy']
    assert response.headers['Cache-Control'] == 'no-store'
    with client.session_transaction() as session:
        assert set(session) == {'csrf'}
        assert token not in str(dict(session))
    assert client.get('/settings/imports').status_code == 200
    assert subscriptions(app) == before


def test_confirmation_is_atomic_idempotent_and_preserves_existing(app, client, import_library):
    _, token = preview(client)
    response = post(client, '/settings/opml/confirm', {'plan': token})
    assert response.status_code == 303 and response.location == '/settings/imports'
    assert '2 件追加、2 件登録済み・重複' in client.get(response.location).get_data(as_text=True)
    rows = subscriptions(app)
    assert [row[0] for row in rows] == ['https://example.com/existing', 'https://example.com/one', 'https://example.com/two']
    assert rows[0][1:3] == ('Original existing', 'Keep folder')
    assert rows[1][2] == rows[2][2] == 'Research & News'
    assert rows[2][1] == 'Second'
    assert all(row[3] is None for row in rows)
    assert post(client, '/settings/opml/confirm', {'plan': token}).status_code == 303
    assert subscriptions(app) == rows
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM articles').fetchone()[0] == 0


def test_confirmation_rechecks_concurrent_duplicates(app, client, import_library):
    _, token = preview(client)
    with app.app_context(), get_db() as db:
        db.execute("INSERT INTO feeds(url,title,folder,created_at) VALUES('https://example.com/one','Another request','Keep new folder','2026-10-11')")
    response = post(client, '/settings/opml/confirm', {'plan': token}, follow_redirects=True)
    assert '1 件追加、3 件登録済み・重複' in response.get_data(as_text=True)
    assert subscriptions(app)[1][1:3] == ('Another request', 'Keep new folder')


@pytest.mark.parametrize('kind', ['tampered', 'empty', 'oversized', 'unicode', 'repeated'])
def test_invalid_confirmation_plan_cannot_write(app, client, import_library, kind):
    _, token = preview(client)
    if kind == 'repeated':
        with client.session_transaction() as session:
            csrf = session['csrf']
        data = MultiDict([('csrf', csrf), ('plan', token), ('plan', token)])
        response = client.post('/settings/opml/confirm', data=data)
    else:
        invalid = {'tampered': token+'tampered', 'empty': '', 'oversized': 'x'*(MAX_PLAN_BYTES+1), 'unicode': '不正なプレビュー'}[kind]
        response = post(client, '/settings/opml/confirm', {'plan': invalid})
    assert response.status_code == 400
    assert token not in response.get_data(as_text=True)
    assert len(subscriptions(app)) == 1


def test_expired_confirmation_plan_cannot_write(app, client, import_library, monkeypatch):
    now = [2000000000]
    monkeypatch.setattr(TimestampSigner, 'get_timestamp', lambda self: now[0])
    _, token = preview(client)
    now[0] += PLAN_MAX_AGE + 1
    response = post(client, '/settings/opml/confirm', {'plan': token})
    assert response.status_code == 400 and '有効期限' in response.get_data(as_text=True)
    assert len(subscriptions(app)) == 1


def test_confirmation_requires_same_session_and_csrf(app, client, import_library):
    _, token = preview(client)
    assert client.post('/settings/opml/confirm', data={'plan': token}).status_code == 400
    assert post(app.test_client(), '/settings/opml/confirm', {'plan': token}).status_code == 400
    assert client.get('/settings/opml/confirm').status_code == 405
    assert len(subscriptions(app)) == 1


@pytest.mark.parametrize('change', [
    {'version': True}, {'entries': 'bad'}, {'entries': [{'url': 'http://127.0.0.1/feed', 'title': 'bad', 'folder': ''}]},
    {'entries': [{'url': 'https://example.com/feed', 'title': 'bad', 'folder': '', 'extra': True}]},
])
def test_even_signed_plan_shape_is_revalidated(app, client, import_library, change):
    preview(client)
    with client.session_transaction() as session:
        binding = hashlib.sha256(session['csrf'].encode()).hexdigest()
    with app.app_context():
        token = serializer().dumps({'version': 1, 'session': binding, 'entries': [], **change})
    assert post(client, '/settings/opml/confirm', {'plan': token}).status_code == 400
    assert len(subscriptions(app)) == 1


def test_confirmation_rolls_back_partial_insert(app, client, import_library):
    _, token = preview(client)
    with app.app_context(), get_db() as db:
        db.execute("""CREATE TRIGGER fail_second_import BEFORE INSERT ON feeds
                      WHEN NEW.url='https://example.com/two'
                      BEGIN SELECT RAISE(ABORT,'fixture insert failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match='fixture insert failure'):
        post(client, '/settings/opml/confirm', {'plan': token})
    assert len(subscriptions(app)) == 1


def test_busy_confirmation_has_no_writes_and_can_retry(app, client, import_library):
    _, token = preview(client)
    with app.app_context(), collection.refresh_lock():
        assert post(client, '/settings/opml/confirm', {'plan': token}).status_code == 409
        assert len(subscriptions(app)) == 1
    assert post(client, '/settings/opml/confirm', {'plan': token}).status_code == 303
    assert len(subscriptions(app)) == 3


def test_empty_and_duplicate_only_preview_disables_confirmation(app, client, import_library):
    for data in (b'<opml><body/></opml>', b'<opml><body><outline xmlUrl="https://example.com/existing"/></body></opml>'):
        response, _ = preview(client, data)
        tree = markup(response.data)
        assert 'disabled' in tree.find(".//form[@action='/settings/opml/confirm']/button").attrib
        assert '追加予定 0 件' in response.get_data(as_text=True)
    assert len(subscriptions(app)) == 1


def test_invalid_preview_is_atomic_and_does_not_echo_url(app, client, import_library):
    data = b'<opml><body><outline xmlUrl="https://example.com/one"/><outline xmlUrl="https://example.com:private-marker/rss"/></body></opml>'
    response = post(client, '/settings/opml', {'opml': (io.BytesIO(data), 'fixture.opml')}, follow_redirects=True)
    assert '公開 HTTP(S) URL' in response.get_data(as_text=True)
    assert 'private-marker' not in response.get_data(as_text=True)
    assert len(subscriptions(app)) == 1


def test_api_retains_explicit_one_step_import(app, client, import_library):
    read = authorization(app, 'read')[2]
    write = authorization(app, 'write')[2]
    assert client.post('/api/v1/opml', headers=read, data=OPML, content_type='application/xml').status_code == 403
    response = client.post('/api/v1/opml', headers=write, data=OPML, content_type='application/xml')
    assert response.status_code == 200
    assert response.json['data']['added'] == response.json['data']['skipped'] == 2
    assert response.json['data']['contract'] == 'atomic insertion-only; duplicate URLs skipped; no inline fetch'
    assert len(subscriptions(app)) == 3


@pytest.fixture
def live_import(app, import_library):
    server = make_server('127.0.0.1', 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:'+str(server.server_port)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.browser
@pytest.mark.skipif(os.environ.get('FEEDASTROLABE_TEST_BROWSER') != '1', reason='Enable real Chromium tests explicitly')
@pytest.mark.parametrize('script_enabled', [True, False])
def test_native_mobile_import_preview_cancel_and_confirm(live_import, app, tmp_path, script_enabled):
    from playwright.sync_api import expect, sync_playwright
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            with browser.new_context(viewport={'width':390, 'height':844}, is_mobile=True,
                                     has_touch=True, java_script_enabled=script_enabled) as context:
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(live_import+'/settings/imports')

                def upload():
                    page.locator('#opml').set_input_files({'name':'fixture.opml', 'mimeType':'text/xml', 'buffer':OPML})
                    page.get_by_role('button', name='インポート内容を確認').tap()
                    expect(page.get_by_role('heading', name='購読のインポートを確認')).to_be_visible()
                    expect(page.get_by_role('heading', name='追加予定 2 件')).to_be_visible()

                upload()
                assert len(subscriptions(app)) == 1
                assert page.locator('script').count() == 1
                expect(page.locator('script')).to_have_attribute('src', '/static/context-actions.js')
                if script_enabled:
                    assert page.evaluate('window.importExecuted') is None
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.get_by_role('link', name='取り消す', exact=True).tap()
                expect(page.get_by_role('heading', name='購読の移行（OPML）', level=1)).to_be_visible()
                assert len(subscriptions(app)) == 1
                upload()
                image_path = tmp_path/f'import-preview-mobile-{script_enabled}.png'
                page.screenshot(path=str(image_path), full_page=True)
                print('Mobile screenshot:', image_path)
                page.get_by_role('button', name='2 件の購読を登録').focus()
                page.get_by_role('button', name='2 件の購読を登録').press('Enter')
                expect(page.get_by_role('status')).to_contain_text('2 件追加、2 件登録済み・重複')
                assert len(subscriptions(app)) == 3
                assert errors == []
        finally:
            browser.close()
