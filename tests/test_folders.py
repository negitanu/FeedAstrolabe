"""Folder click destinations and durable, arbitrary display order."""
from contextlib import closing
from urllib.parse import urlencode, urlsplit, parse_qs

import pytest

from feedastrolabe import create_app
from feedastrolabe.db import get_db, connect, init_database
from feedastrolabe.maintenance import backup, restore
from test_reader import app, client, post
from test_reader_navigation import markup
from test_feed_disclosure import browser, browser_only
from test_task_navigation import live_empty

HOSTILE = '\"><img src=x onerror=alert(1)>'


@pytest.fixture
def folder_data(app):
    rows = [('', 'Unfiled', 'rss'), ('Tech', 'Tech Alpha', 'rss'),
            ('Tech', 'Tech Beta', 'mastodon'), ('ニュース', 'News', 'rss'),
            ('未分類', 'Named unclassified', 'page'), (HOSTILE, 'Escaped', 'rss'),
            ('case', 'Lower case', 'rss'), ('Case', 'Upper case', 'rss')]
    with app.app_context():
        with get_db() as db:
            for index, (name, title, kind) in enumerate(rows, 1):
                db.execute('INSERT INTO feeds(id,url,title,folder,source_type,created_at) VALUES(?,?,?,?,?,?)',
                           (index, f'https://example.com/{index}', title, name, kind, '2026-10-24'))
            for index, fid in enumerate([2, 2, 3, 4, 1], 1):
                db.execute('''INSERT INTO articles(id,feed_id,guid,title,content,search_text,published_at,is_read,is_starred)
                              VALUES(?,?,?,?,?,?,?,?,?)''',
                           (index, fid, str(index), f'Story {index}', '<p>Fixture body</p>',
                            'Fixture body', '2026-10-24', int(index == 1), int(index == 2)))
    return sorted(set(row[0] for row in rows))


def sidebar_names(response):
    tree = markup(response.data)
    return [node.get('data-folder') for node in tree.findall(".//details[@class='feed-folder']")]


def snapshot(app):
    with app.app_context():
        return [tuple(row) for row in get_db().execute('SELECT * FROM articles ORDER BY id')]


def article_ids(response):
    tree = markup(response.data)
    return [int(parse_qs(urlsplit(a.get('href')).query)['article'][0])
            for a in tree.findall(".//a[@class='article-title']")]


def test_folder_article_membership_counts_and_links(folder_data, client):
    response = client.get('/folders?' + urlencode({'folder':'Tech'}))
    assert response.status_code == 200
    tree = markup(response.data)
    assert ''.join(tree.find('.//h1').itertext()) == 'Tech の記事'
    assert article_ids(response) == [3, 2, 1]
    assert '3 件の記事' in response.get_data(as_text=True)
    assert not tree.findall(".//li[@class='folder-feed-card']")
    assert tree.find(".//section[@aria-label='記事一覧']") is not None
    for link in tree.findall(".//a[@class='article-title']"):
        assert parse_qs(urlsplit(link.get('href')).query)['folder'] == ['Tech']
    selected = [f for f in tree.findall(".//details[@class='feed-folder']") if f.get('data-selected') == 'true']
    assert len(selected) == 1 and selected[0].get('data-folder') == 'Tech'
    assert selected[0].find("./summary/a[@aria-current='page']") is not None
    assert tree.find(".//nav[@aria-label='アプリ全体']/a[@aria-current]").get('href') == '/'
    assert sidebar_names(response) == folder_data


@pytest.mark.parametrize('name,ids', [('', [5]), ('未分類',[]), (HOSTILE,[]), ('Case',[]), ('case',[])])
def test_exact_folder_identity_and_escaping(folder_data, client, name, ids):
    response = client.get('/folders?' + urlencode({'folder':name}))
    tree = markup(response.data)
    assert response.status_code == 200
    assert article_ids(response) == ids
    assert not tree.findall('.//img')
    assert not tree.findall(".//*[@onerror]")


@pytest.mark.parametrize('path,status', [('/folders',400),('/folders?folder=missing',404),
    ('/folders?folder=Tech&folder=case',400),('/folders?folder='+('x'*81),400),('/folders?folder=%00',400)])
def test_folder_validation(folder_data, client, path, status):
    assert client.get(path).status_code == status


def test_arbitrary_order_survives_restart_membership_changes_and_restore(folder_data, app, client, tmp_path):
    articles_before = snapshot(app)
    names = list(folder_data)
    for name, move, position in [('ニュース','position','1'), ('','down',None), ('Tech','up',None), ('Case','position',str(len(names)))]:
        values = {'folder':name,'move':move}
        if position:values['position']=position
        response = post(client,'/settings/folders',values)
        assert response.status_code == 303 and response.location == '/'
        old = names.index(name)
        target = int(position)-1 if position else max(0,min(len(names)-1,old+(-1 if move=='up' else 1)))
        names.pop(old);names.insert(target,name)
        assert sidebar_names(client.get('/')) == names
    assert snapshot(app) == articles_before
    restarted = create_app({'TESTING':True,'DATA_DIR':app.instance_path})
    assert sidebar_names(restarted.test_client().get('/')) == names
    with app.app_context():
        with get_db() as db:
            db.execute("UPDATE feeds SET folder='New folder' WHERE folder='Tech'")
            db.execute("DELETE FROM feeds WHERE folder='case'")
    expected = [n for n in names if n not in ('Tech','case')] + ['New folder']
    assert sidebar_names(client.get('/')) == expected
    source = app.config['DATABASE']
    backup(source, tmp_path/'backup.sqlite3')
    restore(tmp_path/'backup.sqlite3', tmp_path/'restored'/'feeds.sqlite3')
    restored = create_app({'TESTING':True,'DATA_DIR':str(tmp_path/'restored')})
    assert sidebar_names(restored.test_client().get('/')) == expected


@pytest.mark.parametrize('values,status', [
    ({'folder':'Tech','move':'position','position':'0'},400),
    ({'folder':'Tech','move':'position','position':'999'},400),
    ({'folder':'Tech','move':'position','position':'1.5'},400),
    ({'folder':'Tech','move':'position','position':'bad'},400),
    ({'folder':'missing','move':'up'},404),
    ({'folder':'Tech','move':'unknown'},400),
    ({'move':'up'},400),
    ({'folder':'Tech','move':'position'},400),
])
def test_invalid_order_does_not_save(folder_data, app, client, values, status):
    assert post(client,'/settings/folders',values).status_code == status
    assert sidebar_names(client.get('/')) == folder_data
    with app.app_context():assert get_db().execute('SELECT count(*) FROM folder_positions').fetchone()[0] == 0


def test_csrf_and_duplicate_parameters(folder_data,client):
    assert client.post('/settings/folders',data={'folder':'Tech','move':'up'}).status_code == 400
    from werkzeug.datastructures import MultiDict
    client.get('/')
    with client.session_transaction() as session:csrf=session['csrf']
    assert client.post('/settings/folders',data=MultiDict([('csrf',csrf),('folder','Tech'),('folder','case'),('move','up')])).status_code == 400
    assert sidebar_names(client.get('/')) == folder_data


def test_upgrade_from_v16_keeps_feeds_and_article_state(folder_data,app,client):
    before=snapshot(app)
    with app.app_context():
        with get_db() as db:
            db.execute('DROP TABLE folder_positions')
            db.execute('DROP TABLE article_visits')
            db.execute('PRAGMA user_version=16')
    init_database(app.config['DATABASE'])
    init_database(app.config['DATABASE']) # Repeated startup is safe.
    assert snapshot(app)==before
    with closing(connect(app.config['DATABASE'])) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==19
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    assert sidebar_names(client.get('/'))==folder_data


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width,javascript',[(1280,True),(375,True),(1280,False),(375,False)])
def test_folder_click_order_and_reading_workflow(browser,live_empty,folder_data,app,width,javascript,tmp_path):
    from playwright.sync_api import expect
    articles_before=snapshot(app)
    with browser.new_context(viewport={'width':width,'height':900},java_script_enabled=javascript,
                             is_mobile=width==375,has_touch=width==375) as context:
        page=context.new_page();page.goto(live_empty)
        if width==375 and javascript:page.locator('.mobile-navigation-toggle').tap()
        folder=page.locator('.feed-folder[data-folder="Tech"]')
        summary=folder.locator(':scope > summary')
        # Keyboard activates only disclosure; the link remains a separate target.
        summary.focus();summary.press('Enter')
        expect(folder).not_to_have_attribute('open','')
        assert page.url==live_empty+'/'
        if javascript:
            page.wait_for_function("() => JSON.parse(localStorage.getItem('feedastrolabe.feed-folders.v2'))?.states?.Tech === false")
        folder.locator('.folder-link').click()
        expect(page).to_have_url(live_empty+'/folders?folder=Tech&view=all')
        expect(page.get_by_role('heading',level=1)).to_have_text('Tech の記事')
        expect(page.locator('.article-card')).to_have_count(3)
        expect(page.locator('.folder-link[aria-current]')).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('.article-title').first.click()
        expect(page.locator('#article-detail')).to_contain_text('Story 3')
        assert parse_qs(urlsplit(page.url).query)['folder'] == ['Tech']
        expect(page.locator('.article-card')).to_have_count(3)
        if javascript:
            if width==375:page.locator('.mobile-navigation-toggle').tap()
            handle = page.locator('.feed-folder[data-folder="Tech"] [data-drag-handle]')
            expect(handle).to_be_visible()  # Keyboard press does not wait for deferred script initialization.
            handle.press('Home')
            expect(page.locator('[data-order-status]')).to_contain_text('1 番目')
            expect(page.locator('.feed-folder').first).to_have_attribute('data-folder','Tech')
        page.goto(live_empty+'/folders?folder=Tech')
        if width==375 and javascript:page.locator('.mobile-navigation-toggle').tap()
        if javascript:expect(page.locator('.feed-folder').first).to_have_attribute('data-folder','Tech')
        # Arrow pointer target must not open the overview link.
        summary=page.locator('.feed-folder[data-folder="Tech"]').locator(':scope > summary')
        summary.click(position={'x':8,'y':16})
        if javascript:
            expect(page.locator('.feed-folder[data-folder="Tech"]')).to_have_attribute('open','')
        else:
            expect(page.locator('.feed-folder[data-folder="Tech"]')).not_to_have_attribute('open','')
        assert page.url==live_empty+'/folders?folder=Tech'
        page.screenshot(path=str(tmp_path/f'folder-overview-{width}-{javascript}.png'),full_page=True)
    with browser.new_context(viewport={'width':1280,'height':900}) as other_session:
        page=other_session.new_page();page.goto(live_empty)
        expect(page.locator('.feed-folder').first).to_have_attribute('data-folder','Tech' if javascript else folder_data[0])
    assert snapshot(app)==articles_before
