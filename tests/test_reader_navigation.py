import os
from html.parser import HTMLParser
from xml.etree.ElementTree import Element, SubElement
from threading import Thread
from urllib.parse import parse_qs, urlsplit

import pytest
from werkzeug.datastructures import MultiDict
from werkzeug.serving import make_server

from feedastrolabe.db import get_db
from test_reader import app, client, post


class Markup(HTMLParser):
    void = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__()
        self.root = Element('root')
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = SubElement(self.stack[-1], tag, {key: value or '' for key, value in attrs})
        if tag not in self.void:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        node = self.stack[-1]
        if len(node):
            node[-1].tail = (node[-1].tail or '') + data
        else:
            node.text = (node.text or '') + data


def markup(data):
    parser = Markup()
    parser.feed(data.decode())
    return parser.root


def content(element):
    return ''.join(element.itertext()).strip()


def selected_title(tree):
    selected = next(item for item in tree.findall('.//article') if 'selected' in item.get('class', '').split())
    return content(selected.find("a[@class='article-title']"))


@pytest.fixture
def reading_library(app):
    with app.app_context():
        db = get_db()
        with db:
            db.execute('UPDATE settings SET page_size=10 WHERE id=1')
            for title in ('Sequence feed', 'Other feed'):
                db.execute('INSERT INTO feeds(url,title,created_at) VALUES(?,?,?)',
                           ('https://example.com/'+title.replace(' ', '-'), title, '2026-10-11'))
            db.execute("INSERT INTO workspaces(title,created_at,updated_at) VALUES('Reading case','2026-10-11','2026-10-11')")
            db.execute("INSERT INTO tags(name) VALUES('Reading tag')")
            for number in range(1, 29):
                feed = 2 if number == 25 else 1
                text = 'unrelated text' if number == 26 else 'Reading match 100% &'
                date = '2026-10-12 00:00:00' if number > 24 else '2026-10-11 00:00:00'
                db.execute('''INSERT INTO articles(feed_id,guid,title,content,search_text,published_at,is_starred)
                              VALUES(?,?,?,?,?,?,1)''',
                           (feed, str(number), f'Story {number}', '<p>Reading body</p>', text, date))
                if number != 27:
                    db.execute('INSERT INTO workspace_articles VALUES(1,?)', (number,))
                if number != 28:
                    db.execute('INSERT INTO article_tags VALUES(?,1)', (number,))
    return {'feed': '1', 'q': '100% &', 'workspace': '1', 'tag': '1', 'view': 'unread'}


def detail(client, filters, article, **extra):
    response = client.get('/', query_string={**filters, 'article': article, **extra})
    assert response.status_code == 200
    return markup(response.data)


def query(url):
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query, keep_blank_values=True).items()}


def assert_target(url, filters, article, page):
    assert query(url) == {**filters, 'article': str(article)}
    assert urlsplit(url).fragment == 'article-detail'
    assert urlsplit(url).netloc == ''


def article_states(app):
    with app.app_context():
        return [tuple(row) for row in get_db().execute('SELECT id,is_read,is_starred FROM articles ORDER BY id')]


@pytest.mark.parametrize('view', ['all', 'unread', 'starred'])
def test_full_filter_navigation_aligns_page_without_mutation(app, client, reading_library, view):
    filters = {**reading_library, 'view': view}
    before = article_states(app)
    soup = detail(client, filters, 15, page=999)
    nav = soup.find(".//nav[@class='article-sequence']")
    assert content(nav.find('span')) == '10 / 24 件'
    assert_target(nav.find("a[@rel='prev']").get('href'), filters, 16, 1)
    assert_target(nav.find("a[@rel='next']").get('href'), filters, 14, 2)
    assert ' ページ' not in content(soup)
    assert selected_title(soup) == 'Story 15'
    next_soup = markup(client.get(nav.find("a[@rel='next']").get('href')).data)
    assert selected_title(next_soup) == 'Story 14'
    assert ' ページ' not in content(next_soup)
    assert article_states(app) == before


def test_sequence_boundaries_and_outside_filter(client, reading_library):
    assert detail(client, reading_library, 24).find(".//a[@rel='prev']") is None
    assert detail(client, reading_library, 1).find(".//a[@rel='next']") is None
    for article in (25, 26, 27, 28):
        soup = detail(client, reading_library, article)
        assert content(soup.find(".//section[@id='article-detail']/h2")) == f'Story {article}'
        assert 'この記事は現在の表示条件に含まれていません' in content(soup)
        assert soup.find(".//nav[@class='article-sequence']") is None
        assert soup.find(".//form[@class='read-next']") is None


def test_date_order_precedes_id_order(app, client, reading_library):
    with app.app_context(), get_db() as db:
        db.execute("UPDATE articles SET published_at='2026-10-13' WHERE id=1")
    soup = detail(client, reading_library, 1)
    assert soup.find(".//a[@rel='prev']") is None
    assert_target(soup.find(".//a[@rel='next']").get('href'), reading_library, 24, 1)


def test_workspace_feed_and_direct_membership_do_not_duplicate(app, client, reading_library):
    with app.app_context(), get_db() as db:
        db.execute('INSERT INTO workspace_feeds VALUES(1,1)')
    soup = detail(client, reading_library, 24)
    assert content(soup.find(".//nav[@class='article-sequence']/span")) == '2 / 25 件'
    assert_target(soup.find(".//a[@rel='next']").get('href'), reading_library, 23, 1)


@pytest.mark.parametrize('view,current', [('unread', 24), ('starred', 23)])
def test_sequence_skips_articles_excluded_by_read_or_star(app, client, reading_library, view, current):
    with app.app_context(), get_db() as db:
        db.execute('UPDATE articles SET is_read=1 WHERE id=23')
        db.execute('UPDATE articles SET is_starred=0 WHERE id=24')
    filters = {**reading_library, 'view': view}
    soup = detail(client, filters, current)
    assert_target(soup.find(".//a[@rel='next']").get('href'), filters, 22, 1)
    response = post(client, f'/articles/{current}/read-next', filters)
    assert response.status_code == 303
    assert_target(response.location, filters, 22, 1)


def test_read_next_recalculates_shrinking_unread_page(app, client, reading_library):
    before = article_states(app)
    for current, successor in ((15, 14), (14, 13)):
        response = post(client, f'/articles/{current}/read-next', {**reading_library, 'next': '//evil.com', 'next_article': '28'})
        assert response.status_code == 303
        assert_target(response.location, reading_library, successor, 1)
        soup = markup(client.get(response.location).data)
        assert selected_title(soup) == f'Story {successor}'
    after = article_states(app)
    assert [row[0] for row in after if row[1]] == [14, 15]
    assert [row[2] for row in after] == [row[2] for row in before]


@pytest.mark.parametrize('view', ['all', 'starred'])
def test_read_next_retains_rank_when_read_still_matches(app, client, reading_library, view):
    filters = {**reading_library, 'view': view}
    response = post(client, '/articles/15/read-next', filters)
    assert response.status_code == 303
    assert_target(response.location, filters, 14, 2)
    assert [row[0] for row in article_states(app) if row[1]] == [15]


def test_last_article_returns_filtered_list_with_notice(app, client, reading_library):
    response = post(client, '/articles/1/read-next', reading_library)
    assert response.status_code == 303
    assert query(response.location) == reading_library
    soup = markup(client.get(response.location).data)
    assert soup.find(".//section[@id='article-detail']") is None
    assert '表示条件に一致する次の記事はありません' in content(soup)
    assert [row[0] for row in article_states(app) if row[1]] == [1]


def test_only_matching_article_returns_empty_filtered_list(app, client, reading_library):
    with app.app_context(), get_db() as db:
        db.execute('DELETE FROM article_tags WHERE article_id != 1')
    soup = detail(client, reading_library, 1)
    assert content(soup.find(".//form[@class='read-next']/button")) == '既読にして一覧へ'
    response = post(client, '/articles/1/read-next', reading_library)
    assert query(response.location) == reading_library
    after = markup(client.get(response.location).data)
    assert '記事がありません' in content(after)
    assert ' ページ' not in content(after)
    assert [row[0] for row in article_states(app) if row[1]] == [1]


def test_stale_missing_and_csrf_fail_before_mutation(app, client, reading_library):
    assert client.get('/articles/24/read-next').status_code == 405
    assert client.post('/articles/24/read-next', data=reading_library).status_code == 400
    assert post(client, '/articles/999/read-next', reading_library).status_code == 404
    assert post(client, '/articles/25/read-next', reading_library).status_code == 409
    with app.app_context(), get_db() as db:
        db.execute('UPDATE articles SET is_read=1 WHERE id=24')
    before = article_states(app)
    assert post(client, '/articles/24/read-next', reading_library).status_code == 409
    assert article_states(app) == before


@pytest.mark.parametrize('field,value', [('view', 'invalid'), ('feed', '0'), ('q', 'x'*201),
                                        ('workspace', '0'), ('tag', str(2**63))])
def test_invalid_advance_filter_cannot_mutate(app, client, reading_library, field, value):
    before = article_states(app)
    assert post(client, '/articles/24/read-next', {**reading_library, field: value}).status_code == 400
    assert article_states(app) == before


def test_repeated_advance_filter_cannot_mutate(app, client, reading_library):
    client.get('/')
    with client.session_transaction() as session:
        csrf = session['csrf']
    data = MultiDict([('csrf', csrf), *reading_library.items(), ('feed', '2')])
    assert client.post('/articles/24/read-next', data=data).status_code == 400
    assert all(row[1] == 0 for row in article_states(app))


def test_advance_rolls_back_if_target_calculation_fails(app, client, reading_library, monkeypatch):
    import feedastrolabe
    def failing_target(*args,**kwargs):
        raise RuntimeError('target calculation failed')

    monkeypatch.setattr(feedastrolabe, 'url_for', failing_target)
    with pytest.raises(RuntimeError, match='target calculation failed'):
        post(client, '/articles/24/read-next', reading_library)
    assert all(row[1] == 0 for row in article_states(app))


@pytest.fixture
def live_sequence(app, reading_library):
    server = make_server('127.0.0.1', 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:'+str(server.server_port), reading_library
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.browser
@pytest.mark.skipif(os.environ.get('FEEDASTROLABE_TEST_BROWSER') != '1', reason='Enable real Chromium tests explicitly')
@pytest.mark.parametrize('script_enabled', [True, False])
def test_mobile_sequential_reading_with_native_controls(live_sequence, app, tmp_path, script_enabled):
    from playwright.sync_api import expect, sync_playwright
    from urllib.parse import urlencode
    base, filters = live_sequence
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        try:
            with browser.new_context(viewport={'width':390, 'height':844}, is_mobile=True,
                                     has_touch=True, java_script_enabled=script_enabled) as context:
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base+'/?'+urlencode({**filters, 'article':'15'})+'#article-detail')
                detail = page.get_by_role('region', name='記事本文')
                expect(detail.get_by_role('heading', name='Story 15', exact=True)).to_be_visible()
                expect(detail.get_by_role('heading', name='Story 15', exact=True)).to_be_in_viewport()
                nav = page.get_by_role('navigation', name='記事の移動', exact=True)
                nav.get_by_role('link', name='次の記事 →').tap()
                expect(detail.get_by_role('heading', name='Story 14', exact=True)).to_be_visible()
                assert query(page.url) == {**filters, 'article':'14'}
                nav.get_by_role('link', name='← 前の記事').focus()
                nav.get_by_role('link', name='← 前の記事').press('Enter')
                expect(detail.get_by_role('heading', name='Story 15', exact=True)).to_be_visible()
                detail.get_by_role('button', name='既読にして次へ →', exact=True).first.tap()
                expect(detail.get_by_role('heading', name='Story 14', exact=True)).to_be_visible()
                assert query(page.url) == {**filters, 'article':'14'}
                expect(detail.get_by_role('heading', name='Story 14', exact=True)).to_be_in_viewport()
                if script_enabled:
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert errors == []
                image_path = tmp_path/f'sequence-mobile-{script_enabled}.png'
                page.screenshot(path=str(image_path), full_page=True)
                page.screenshot(path=str(tmp_path/f'sequence-viewport-{script_enabled}.png'))
                print('Mobile screenshot:', image_path)
                detail.get_by_role('link', name='閉じる ×').tap()
                expect(detail).to_have_count(0)
                assert query(page.url) == {**filters}
        finally:
            browser.close()
    assert [row[0] for row in article_states(app) if row[1]] == [15]
    assert all(row[2] == 1 for row in article_states(app))
