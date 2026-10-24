import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from feedastrolabe.db import get_db
from test_reader import app, client
from test_reader_navigation import markup
from test_feed_disclosure import browser, browser_only, live_reader, settle, group

FOLDER_KEY = 'feedastrolabe.feed-folders.v2'
LAYOUT_KEY = 'feedastrolabe.article-layout.v1'
TYPE_KEY = 'feedastrolabe.feed-disclosure.v1'
LEGACY_FOLDER_KEY = 'feedastrolabe.feed-folders.v1'
HOSTILE_FOLDER = '\"><img src=x onerror=alert(1)>'


@pytest.fixture
def presentation_reader(live_reader, app):
    with app.app_context():
        db = get_db()
        with db:
            db.execute('UPDATE settings SET page_size=10 WHERE id=1')
            db.execute("UPDATE feeds SET folder='ニュース'")
            db.execute("UPDATE feeds SET title='日本語ニュースと技術のフィード' WHERE id=1")
            for number, name in enumerate(('ニュース', '技術', '', '未分類', HOSTILE_FOLDER), 5):
                db.execute('INSERT INTO feeds(id,url,title,folder,source_type,created_at) VALUES(?,?,?,?,?,?)',
                           (number, 'https://example.com/folder/'+str(number), '購読 '+str(number), name, 'rss', '2026-10-21'))
            for number in range(35):
                db.execute('''INSERT INTO articles(feed_id,guid,title,content,search_text,published_at)
                              VALUES(1,?,?,?,?,?)''',
                           ('presentation-'+str(number), f'ニュース {number:02d} '+('情報と技術の進展について '*12),
                            '<p>本文と出典を読む。</p>', '情報を整理するための記事の要約です。'*15, '2026-10-21 00:00:00'))
    return live_reader


def folder(page, name='ニュース'):
    return page.locator('.feed-folder[data-folder='+json.dumps(name, ensure_ascii=False)+']')


def wait_closed_state(page, name='ニュース'):
    identity = name
    page.wait_for_function('([key,name]) => { try { return JSON.parse(localStorage.getItem(key))?.states?.[name] === false; } catch { return false; } }',
                           arg=[FOLDER_KEY, identity])


def test_folder_structure_counts_escaping_and_script_nonces(presentation_reader, client):
    response = client.get('/')
    tree = markup(response.data)
    folders = tree.findall(".//details[@class='feed-folder']")
    assert len(folders) == 5
    news = next(node for node in folders if node.get('data-folder') == 'ニュース')
    summary = news.find('summary')
    assert '5 件' not in ''.join(summary.itertext()) and '36' in ''.join(summary.itertext())
    assert len(news.findall(".//a[@class='nav-item feed-item ']")) == 5
    assert {node.text for node in news.findall(".//span[@class='feed-kind']")} == {'RSS','X','Mastodon','ページ'}
    assert {node.get('data-folder') for node in folders} >= {'', '未分類', HOSTILE_FOLDER}
    assert not tree.findall('.//img')
    scripts = tree.findall('.//script')
    assert {script.get('src') for script in scripts} == {'/static/feed-disclosure.js', '/static/article-layout.js', '/static/folder-order.js', '/static/context-actions.js','/static/reader-stream.js','/static/sidebar-organizer.js'}
    assert len({script.get('nonce') for script in scripts}) == 1
    assert all(not script.text for script in scripts)
    selected = markup(client.get('/?feed=1').data)
    active = [node for node in selected.findall(".//details[@class='feed-folder']") if node.get('data-selected') == 'true']
    assert len(active) == 1 and active[0].get('data-folder') == 'ニュース'


@pytest.mark.browser
@browser_only
def test_folder_persistence_identity_selection_and_reset(browser, presentation_reader):
    from playwright.sync_api import expect
    with browser.new_context() as context:
        page = context.new_page()
        page.goto(presentation_reader)
        summary = folder(page).locator(':scope > summary')
        summary.focus()
        summary.press('Enter')
        wait_closed_state(page)
        expect(folder(page)).to_have_js_property('open', False)
        assert folder(page).count() == 1
        expect(folder(page, name='技術')).to_have_js_property('open', True)
        assert page.evaluate('(key) => localStorage.getItem(key)', TYPE_KEY) is None
        page.goto(presentation_reader+'/?feed=1')
        expect(folder(page)).to_have_js_property('open', False)
        settle(page)
        wait_closed_state(page)
        page.goto(presentation_reader)
        expect(folder(page)).to_have_js_property('open', False)
        folder(page, name='').locator(':scope > summary').click(position={'x':8,'y':16})
        wait_closed_state(page, name='')
        expect(folder(page, name='未分類')).to_have_js_property('open', True)
        page.reload()
        expect(folder(page, name='')).to_have_js_property('open', False)
        expect(page.get_by_role('button', name='表示を初期状態に戻す')).to_have_count(0)
        page.reload()
        expect(folder(page)).to_have_js_property('open', False)
        expect(folder(page, name='')).to_have_js_property('open', False)



@pytest.mark.browser
@browser_only
def test_legacy_source_preference_does_not_hide_folder(browser, presentation_reader, app):
    with app.app_context():
        db = get_db()
        with db:
            db.execute("DELETE FROM feeds WHERE source_type='x'")
    with browser.new_context() as context:
        page = context.new_page()
        page.goto(presentation_reader)
        page.evaluate('(key) => localStorage.setItem(key,JSON.stringify({version:1,states:{x:false}}))', TYPE_KEY)
        page.reload()
        assert group(page, 'x').count() == 0
        folder(page).locator(':scope > summary').click(position={'x':8,'y':16})
        wait_closed_state(page)
        assert page.evaluate('(key) => JSON.parse(localStorage.getItem(key)).states.x', TYPE_KEY) is False


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('saved,closed', [
    ({'rss':False,'x':False,'mastodon':False,'page':False},True),
    ({'rss':False},False),
    ({'rss':False,'x':False,'mastodon':True,'page':False},False),
])
def test_merged_folder_migrates_legacy_choices(browser, presentation_reader, saved, closed):
    from playwright.sync_api import expect
    legacy = {json.dumps([kind,'ニュース'],ensure_ascii=False,separators=(',',':')):value
              for kind,value in saved.items()}
    with browser.new_context() as context:
        page = context.new_page()
        page.goto(presentation_reader)
        page.evaluate('([oldKey,newKey,states]) => {localStorage.removeItem(newKey);localStorage.setItem(oldKey,JSON.stringify({version:1,states}));}',
                      [LEGACY_FOLDER_KEY,FOLDER_KEY,legacy])
        page.reload()
        expect(folder(page)).to_have_js_property('open', not closed)
        assert page.evaluate('(key) => JSON.parse(localStorage.getItem(key)).states["ニュース"]', FOLDER_KEY) is (not closed)
        page.goto(presentation_reader+'/?feed=1')
        expect(folder(page)).to_have_js_property('open', not closed)
        settle(page)
        assert page.evaluate('(key) => JSON.parse(localStorage.getItem(key)).states["ニュース"]', FOLDER_KEY) is (not closed)
        expect(page.get_by_role('button',name='表示を初期状態に戻す')).to_have_count(0)



@pytest.mark.browser
@browser_only
def test_themed_controls_keep_query_and_bulk_read_scope(browser, presentation_reader, app):
    from playwright.sync_api import expect
    with app.app_context():
        db = get_db()
        with db:
            wid = db.execute("INSERT INTO workspaces(title,created_at,updated_at) VALUES('画面検証の案件','2026-10-21','2026-10-21')").lastrowid
            tid = db.execute("INSERT INTO tags(name) VALUES('画面検証のタグ')").lastrowid
            for aid in range(2,37):
                db.execute('INSERT INTO workspace_articles VALUES(?,?)',(wid,aid))
                db.execute('INSERT INTO article_tags VALUES(?,?)',(aid,tid))
    with browser.new_context(viewport={'width':1440,'height':900}) as context:
        page = context.new_page()
        page.goto(presentation_reader+'/?feed=1&view=unread')
        fields = page.locator('.reader-search select,.reader-search input:not([type="hidden"]),.reader-search button')
        metrics = fields.evaluate_all('(fields) => fields.map(field => ({top:field.getBoundingClientRect().top,height:field.getBoundingClientRect().height,border:getComputedStyle(field).borderColor,radius:getComputedStyle(field).borderRadius}))')
        assert len(metrics) == 4
        assert len({item['top'] for item in metrics}) == 1
        assert len({item['height'] for item in metrics}) == 1
        assert metrics[0]['border'] == metrics[2]['border'] and metrics[0]['radius'] == metrics[2]['radius']
        page.get_by_label('調査案件',exact=True).select_option(str(wid))
        page.get_by_label('記事タグ',exact=True).select_option(str(tid))
        page.get_by_label('記事を検索',exact=True).fill('情報')
        page.get_by_role('button',name='検索',exact=True).click()
        assert parse_qs(urlsplit(page.url).query) == {'view':['unread'],'feed':['1'],'workspace':[str(wid)],'tag':[str(tid)],'q':['情報']}
        expect(page.locator('.article-card')).to_have_count(30)
        page.get_by_role('button',name='全て既読',exact=True).click()
        expect(page.locator('.article-card')).to_have_count(0)
        with app.app_context():
            assert get_db().execute('SELECT sum(is_read) FROM articles').fetchone()[0] == 35
            assert get_db().execute('SELECT is_read FROM articles WHERE id=1').fetchone()[0] == 0


@pytest.mark.browser
@browser_only
def test_mobile_navigation_density_and_breakpoint(browser, presentation_reader):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True) as context:
        page = context.new_page()
        page.goto(presentation_reader)
        navigation = page.locator('.sidebar-navigation')
        expect(navigation).to_have_js_property('open',False)
        assert page.locator('.article-card').first.bounding_box()['y'] < 430
        page.get_by_role('button',name='1行',exact=True).tap()
        assert all(button.bounding_box()['height'] >= 40 for button in page.locator('.article-layout-switch button').all())
        visible = page.locator('.article-card').evaluate_all('(cards) => cards.filter(card => card.getBoundingClientRect().bottom<=innerHeight).length')
        assert visible >= 5
        page.locator('.mobile-navigation-toggle').tap()
        expect(folder(page)).to_be_visible()
        folder(page).get_by_role('link').first.tap()
        expect(navigation).to_have_js_property('open',False)
        page.set_viewport_size({'width':1440,'height':900})
        expect(navigation).to_have_js_property('open',True)
        expect(page.locator('.mobile-navigation-toggle')).to_be_hidden()


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width',[320,768,1024,1920])
def test_compact_controls_do_not_overflow(browser, presentation_reader, width):
    with browser.new_context(viewport={'width':width,'height':900}) as context:
        page = context.new_page()
        page.goto(presentation_reader)
        page.locator('[data-article-layout-choice="line"]').click()
        if width>=1024:
            source=page.locator('.article-meta>span').first.bounding_box()
            title=page.locator('.article-title').first.bounding_box()
            assert source['width']<=140 and title['width']>source['width']
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        for field in page.locator('.reader-search select,.reader-search input:not([type="hidden"]),.reader-search button').all():
            assert field.is_visible()
            bounds = field.bounding_box()
            assert bounds['x'] >= 0 and bounds['x']+bounds['width'] <= width


@pytest.mark.browser
@browser_only
def test_layout_switch_navigation_and_read_star_actions(browser, presentation_reader, app):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':1440, 'height':1000}) as context:
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(presentation_reader+'/?feed=1&view=unread&q=情報')
        original = page.locator('.article-title').evaluate_all('(links) => links.map(link => link.href)')
        for name, value in [('1行','line'), ('タイル','tiles')]:
            button = page.get_by_role('button', name=name, exact=True)
            button.click()
            expect(button).to_have_attribute('aria-pressed', 'true')
            expect(page.locator('.article-list')).to_have_attribute('data-article-layout', value)
            assert page.locator('.article-title').evaluate_all('(links) => links.map(link => link.href)')[:len(original)] == original
        with app.app_context():
            assert get_db().execute('SELECT sum(is_read),sum(is_starred) FROM articles').fetchone()[:] == (0,0)
        page.locator('.article-title').first.click()
        expect(page.locator('.article-detail')).to_be_visible()
        expect(page.locator('.article-list')).to_have_attribute('data-article-layout', 'tiles')
        page.get_by_role('link', name='閉じる ×').click()
        if page.locator('[data-article-loader]').count():page.locator('[data-article-loader]').scroll_into_view_if_needed()
        expect(page.locator('.article-card')).to_have_count(35)
        assert parse_qs(urlsplit(page.url).query) == {'view':['unread'], 'feed':['1'], 'q':['情報']}
        expect(page.locator('.article-list')).to_have_attribute('data-article-layout', 'tiles')
        page.get_by_role('button', name='1行', exact=True).click()
        card = page.locator('.article-card').first
        aid = int(parse_qs(urlsplit(card.locator('.article-title').get_attribute('href')).query)['article'][0])
        card.get_by_role('button', name='☆ 保存', exact=True).click()
        page.locator('.article-card').first.get_by_role('button', name='既読にする', exact=True).click()
        expect(page.locator('.article-list')).to_have_attribute('data-article-layout', 'line')
        expect(page.locator('[data-article-id="'+str(aid)+'"]')).to_have_count(0)
        with app.app_context():
            assert get_db().execute('SELECT is_read,is_starred FROM articles WHERE id=?', (aid,)).fetchone()[:] == (1,1)
        assert errors == []
        storage = context.storage_state()
    with browser.new_context(storage_state=storage) as context:
        page = context.new_page()
        page.goto(presentation_reader)
        expect(page.locator('.article-list')).to_have_attribute('data-article-layout', 'line')


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('layout,label', [('line','1行'), ('tiles','タイル')])
@pytest.mark.parametrize('width,detail', [(1440,False),(390,False),(1280,True)])
def test_layout_geometry_and_screenshots(browser, presentation_reader, layout, label, width, detail):
    with browser.new_context(viewport={'width':width,'height':960}) as context:
        page = context.new_page()
        page.goto(presentation_reader+'/?article=36' if detail else presentation_reader)
        page.get_by_role('button', name=label, exact=True).click()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        boxes = page.locator('.article-card').evaluate_all('(cards) => cards.map(card => ({x:card.getBoundingClientRect().x,y:card.getBoundingClientRect().y,w:card.getBoundingClientRect().width,h:card.getBoundingClientRect().height}))')
        if layout == 'line':
            assert max(box['h'] for box in boxes) <= 62
            assert page.locator('.article-title').first.evaluate('(link) => getComputedStyle(link).whiteSpace') == 'nowrap'
        elif width == 1440:
            assert boxes[0]['y'] == boxes[1]['y'] and boxes[0]['x'] != boxes[1]['x']
        else:
            assert boxes[0]['y'] < boxes[1]['y']
        for button in page.locator('.article-card').first.locator('button').all():
            assert button.is_visible()
        out = Path('/private/tmp/feedastrolabe-reader-presentation')
        out.mkdir(exist_ok=True)
        page.screenshot(path=str(out/f'{layout}-{width}{"-detail" if detail else ""}.png'), full_page=True)


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('folder_raw,layout_raw', [
    ('not JSON','not JSON'),
    ('{"version":3,"states":{}}','{"version":2,"layout":"tiles"}'),
    ('{"version":2,"states":[]}','{"version":1,"layout":"unknown"}'),
    ('x'*65537,'x'*129),
], ids=['malformed', 'unknown-version', 'wrong-shape', 'oversized'])
def test_invalid_presentation_storage_falls_back(browser, presentation_reader, folder_raw, layout_raw):
    from playwright.sync_api import expect
    with browser.new_context() as context:
        page = context.new_page()
        page.goto(presentation_reader)
        page.evaluate('([fk,fv,lk,lv]) => { localStorage.setItem(fk,fv);localStorage.setItem(lk,lv); }',
                      [FOLDER_KEY,folder_raw,LAYOUT_KEY,layout_raw])
        page.reload()
        expect(folder(page)).to_have_js_property('open', True)
        expect(page.locator('.article-list')).to_have_attribute('data-article-layout', 'standard')
        page.get_by_role('button', name='タイル', exact=True).click()
        expect(page.locator('.article-list')).to_have_attribute('data-article-layout', 'tiles')
        folder(page).locator(':scope > summary').click(position={'x':8,'y':16})
        wait_closed_state(page)


@pytest.mark.browser
@browser_only
def test_folder_storage_validates_types_and_prunes_stale_keys(browser, presentation_reader):
    from playwright.sync_api import expect
    identity = lambda name: name
    with browser.new_context() as context:
        page = context.new_page()
        page.goto(presentation_reader)
        states = {identity('ニュース'):'false', identity('技術'):False, identity('deleted folder'):False}
        page.evaluate('([key,states]) => localStorage.setItem(key,JSON.stringify({version:2,states}))', [FOLDER_KEY,states])
        page.reload()
        expect(folder(page)).to_have_js_property('open', True)
        expect(folder(page, name='技術')).to_have_js_property('open', False)
        folder(page).locator(':scope > summary').click(position={'x':8,'y':16})
        wait_closed_state(page)
        saved = page.evaluate('(key) => JSON.parse(localStorage.getItem(key)).states', FOLDER_KEY)
        assert saved == {identity('ニュース'):False, identity('技術'):False}


@pytest.mark.browser
@browser_only
def test_denied_storage_and_no_javascript_presentation(browser, presentation_reader):
    from playwright.sync_api import expect
    with browser.new_context() as context:
        context.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('storage denied')}})")
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(presentation_reader)
        page.get_by_role('button', name='1行', exact=True).click()
        expect(page.locator('.article-list')).to_have_attribute('data-article-layout', 'line')
        folder(page).locator(':scope > summary').click(position={'x':8,'y':16})
        expect(folder(page)).to_have_js_property('open', False)
        page.reload()
        expect(page.locator('.article-list')).to_have_attribute('data-article-layout', 'standard')
        expect(folder(page)).to_have_js_property('open', True)
        assert errors == []
    with browser.new_context(java_script_enabled=False) as context:
        page = context.new_page()
        page.goto(presentation_reader)
        expect(page.locator('.article-layout-switch')).to_be_hidden()
        expect(page.locator('.article-list')).to_have_attribute('data-article-layout', 'standard')
        summary = folder(page).locator(':scope > summary')
        summary.focus()
        summary.press('Enter')
        expect(folder(page)).not_to_have_attribute('open','')
