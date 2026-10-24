import os
import re
from threading import Thread

import pytest
from werkzeug.serving import make_server

from feedastrolabe.db import get_db
from test_reader import app, client, subscribe

KEY = 'feedastrolabe.feed-folders.v2'
browser_only = pytest.mark.skipif(os.environ.get('FEEDASTROLABE_TEST_BROWSER') != '1',
                                  reason='Enable real Chromium tests explicitly')


def test_reader_nonce_scope_and_sanitized_article(app, client):
    subscribe(client)
    first = client.get('/?article=1')
    second = client.get('/')
    nonce = re.search(r'<script nonce="([A-Za-z0-9_-]+)"', first.get_data(as_text=True)).group(1)
    assert "script-src 'nonce-" + nonce + "'" in first.headers['Content-Security-Policy']
    assert nonce not in second.get_data(as_text=True)
    assert "script-src 'self'" not in first.headers['Content-Security-Policy']
    assert '<script' not in re.search(r'<div class="prose">(.*?)</div>', first.get_data(as_text=True)).group(1)
    for path in ('/healthz', '/static/feed-disclosure.js'):
        assert "script-src 'none'" in client.get(path).headers['Content-Security-Policy']

    for path in ('/settings', '/workspaces'):
        response = client.get(path)
        assert "script-src 'nonce-" in response.headers['Content-Security-Policy']
        assert '/static/context-actions.js' in response.get_data(as_text=True)


@pytest.fixture
def live_reader(app):
    with app.app_context():
        db = get_db()
        with db:
            for kind in ('rss', 'x', 'mastodon', 'page'):
                db.execute('INSERT INTO feeds(url,title,source_type,folder,created_at) VALUES(?,?,?,?,?)',
                           ('https://example.com/'+kind, kind+' fixture', kind, kind, '2026-10-11 00:00:00'))
            db.execute('''INSERT INTO articles(feed_id,guid,title,content,search_text,published_at)
                          VALUES(1,'one','Fixture story',?,'Reader body','2026-10-11 00:00:00')''',
                       ('<p>Reader body</p><script>window.articleExecuted=true</script><b onclick="window.articleExecuted=true">text</b>',))
    server = make_server('127.0.0.1', 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:'+str(server.server_port)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


def group(page, kind):
    return page.locator('.feed-folder[data-folder="'+kind+'"]')


def settle(page):
    page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')


@pytest.mark.browser
@browser_only
def test_keyboard_navigation_preserves_disclosure_on_selection(browser, live_reader):
    from playwright.sync_api import expect
    context = browser.new_context()
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(live_reader)
    summary = group(page, 'rss').locator(':scope > summary')
    summary.focus()
    summary.press('Enter')
    expect(group(page, 'rss')).to_have_js_property('open', False)
    page.wait_for_function('(key) => JSON.parse(localStorage.getItem(key))?.states?.rss === false', arg=KEY)
    page.locator('.article-title').first.click()
    expect(group(page, 'rss')).to_have_js_property('open', False)
    assert page.evaluate('window.articleExecuted') is None
    page.evaluate("() => { const script=document.createElement('script'); script.textContent='window.untrustedExecuted=true'; document.body.append(script); }")
    assert page.evaluate('window.untrustedExecuted') is None
    page.goto(live_reader+'/?feed=1')
    expect(group(page, 'rss')).to_have_js_property('open', False)
    settle(page)
    assert page.evaluate('(key) => JSON.parse(localStorage.getItem(key)).states.rss', KEY) is False
    page.goto(live_reader+'/?view=unread')
    expect(group(page, 'rss')).to_have_js_property('open', False)
    storage = context.storage_state()
    assert errors == []
    context.close()
    with browser.new_context(storage_state=storage) as restored:
        page = restored.new_page()
        page.goto(live_reader)
        expect(group(page, 'rss')).to_have_js_property('open', False)
        expect(group(page, 'x')).to_have_js_property('open', True)


@pytest.mark.browser
@browser_only
def test_mobile_reset_preserves_filters_and_article_state(browser, live_reader, app, tmp_path):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':390, 'height':844}, is_mobile=True, has_touch=True) as context:
        page = context.new_page()
        page.goto(live_reader)
        page.locator('.mobile-navigation-toggle').tap()
        group(page, 'rss').locator(':scope > summary').tap(position={'x':8,'y':16})
        page.wait_for_function('(key) => JSON.parse(localStorage.getItem(key))?.states?.rss === false', arg=KEY)
        page.goto(live_reader+'/?feed=2&view=unread')
        expect(group(page, 'rss')).to_have_js_property('open', False)
        page.locator('.mobile-navigation-toggle').tap()
        expect(page.get_by_role('button', name='表示を初期状態に戻す')).to_have_count(0)
        expect(group(page, 'rss')).to_have_js_property('open', False)
        expect(group(page, 'mastodon')).to_have_js_property('open', True)
        assert 'feed=2&view=unread' in page.url
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        image_path = tmp_path/'disclosure-mobile.png'
        page.screenshot(path=str(image_path), full_page=True)
        print('Mobile screenshot:', image_path)
        page.goto(live_reader)
        expect(group(page, 'rss')).to_have_js_property('open', False)
    with app.app_context():
        assert get_db().execute('SELECT is_read,is_starred FROM articles').fetchone()[:] == (0, 0)


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('raw', ['invalid JSON', '{"version":3,"states":{"rss":false}}',
                               '{"version":2,"states":[]}', 'x'*65537], ids=['malformed','version','shape','oversized'])
def test_invalid_storage_native_defaults(browser, live_reader, raw):
    from playwright.sync_api import expect
    with browser.new_context() as context:
        page = context.new_page()
        page.goto(live_reader)
        page.evaluate('([key,raw]) => localStorage.setItem(key,raw)', [KEY,raw])
        page.reload()
        for kind in ('rss','x','mastodon','page'):
            expect(group(page, kind)).to_have_js_property('open', True)
        group(page, 'rss').locator(':scope > summary').click(position={'x':8,'y':16})
        expect(group(page, 'rss')).to_have_js_property('open', False)


@pytest.mark.browser
@browser_only
def test_denied_storage_and_no_script_controls(browser, live_reader):
    from playwright.sync_api import expect
    with browser.new_context() as context:
        context.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('storage denied')}})")
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(live_reader)
        group(page, 'rss').locator(':scope > summary').click(position={'x':8,'y':16})
        expect(group(page, 'rss')).to_have_js_property('open', False)
        page.reload()
        expect(group(page, 'rss')).to_have_js_property('open', True)
        assert errors == []
    with browser.new_context(java_script_enabled=False) as context:
        page = context.new_page()
        page.goto(live_reader+'/?feed=1')
        expect(group(page, 'rss')).to_have_attribute('open','')
        expect(group(page, 'x')).to_have_attribute('open','')
        expect(page.locator('[data-disclosure-reset]')).to_be_hidden()
        summary = group(page, 'rss').locator(':scope > summary')
        summary.focus()
        summary.press('Enter')
        expect(group(page, 'rss')).not_to_have_attribute('open','')
