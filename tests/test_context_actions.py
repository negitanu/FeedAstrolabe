"""Contextual editing contracts, exercised with real pointer and keyboard input."""
from urllib.parse import urlencode, urlsplit, parse_qs
import pytest
from werkzeug.datastructures import MultiDict
from feedastrolabe.db import get_db
from feedastrolabe import research, triage, entities, security_intelligence, network_intelligence, ai_research
from feedastrolabe.social_research import add_topic
from test_reader import app, client, post
from test_folders import folder_data, snapshot, sidebar_names, HOSTILE
from test_feed_disclosure import browser, browser_only
from test_task_navigation import live_empty
from test_reader_navigation import markup


def test_removed_order_screen_and_atomic_rename(folder_data, app, client):
    assert client.get('/settings/folders').location == '/'
    for path in ['/', '/settings', '/settings/appearance']:
        assert '/settings/folders' not in client.get(path).get_data(as_text=True)
    before = snapshot(app)
    post(client, '/folders/order', {'folder':'Tech','move':'position','position':'1'})
    names = sidebar_names(client.get('/'))
    response = post(client, '/folders/rename', {'folder':'Tech','name':'技術と研究'})
    assert response.status_code == 200 and response.json == {'name':'技術と研究'}
    assert sidebar_names(client.get('/')) == ['技術と研究', *names[1:]]
    assert snapshot(app) == before
    with app.app_context():
        assert get_db().execute("SELECT count(*) FROM feeds WHERE folder='技術と研究'").fetchone()[0] == 2
    assert client.get('/folders?folder=Tech').status_code == 404
    assert client.get('/folders?' + urlencode({'folder':'技術と研究'})).status_code == 200
    assert post(client, '/folders/rename', {'folder':'','name':'Unfiled renamed'}).status_code == 200
    assert snapshot(app) == before


@pytest.mark.parametrize('old,new,status', [('Tech','Case',400),('missing','New',404),
    ('Tech','',400),('Tech',' ',400),('Tech','x'*81,400),('Tech','a\x00b',400),
    ('Tech',HOSTILE,400)])
def test_rename_rejects_invalid_without_mutation(folder_data, app, client, old, new, status):
    before = snapshot(app)
    assert post(client, '/folders/rename', {'folder':old,'name':new}).status_code == status
    assert sidebar_names(client.get('/')) == folder_data
    assert snapshot(app) == before


def test_rename_exact_identity_csrf_and_escaping(folder_data, app, client):
    assert client.post('/folders/rename',data={'folder':'Tech','name':'New'}).status_code == 400
    client.get('/')
    with client.session_transaction() as session: csrf = session['csrf']
    assert client.post('/folders/rename',data=MultiDict([('csrf',csrf),('folder','Tech'),('folder','case'),('name','new')])).status_code == 400
    name = ' <svg onload=alert(1)> '
    assert post(client, '/folders/rename', {'folder':'Tech','name':name}).status_code == 200
    assert name in sidebar_names(client.get('/'))
    tree = markup(client.get('/folders?' + urlencode({'folder':name})).data)
    assert tree.find('.//*[@onload]') is None
    assert post(client, '/folders/rename', {'folder':'case','name':'case'}).status_code == 200


@pytest.fixture
def objects(app, folder_data):
    with app.app_context():
        wid = research.create_workspace({'title':'調査対象'})
        rule = triage.save(wid, {'name':'重要な検索','query':{'any':[{'field':'text','op':'contains','value':'AI'}]}})
        domain = entities.create({'kind':'domain','value':'example.com'})
        network = network_intelligence.save_watch(wid, {'entity_id':domain,'provider':'dns','outbound_public':False})
        ai = ai_research.save_watch(wid, {'provider':'arxiv','target':'id:1706.03762','outbound_public':False})
        cve = entities.create({'kind':'cve','value':'CVE-2026-1234'})
        security = security_intelligence.save_watch(wid, {'entity_id':cve,'outbound_public':False})
        topic = add_topic('bluesky', 'AI', name='SNS テスト')
    return [('feeds',2),('feeds',topic),('workspaces',wid),('watchlists',rule),('security',security),('network',network),('ai',ai)]


def test_all_object_fragments_reuse_authoritative_forms(objects, client):
    for kind, identifier in objects:
        response = client.get(f'/settings/items/{kind}/{identifier}', headers={'X-Context-Editor':'1'})
        assert response.status_code == 200, (kind,identifier)
        tree = markup(response.data)
        assert tree.find('.//*[@data-editor-content]') is not None
        assert not tree.findall('.//script') and not tree.findall('.//nav')
        for form in tree.findall('.//form'):
            assert form.find('.//input[@name="csrf"]') is not None
        assert client.get(f'/settings/items/{kind}/{identifier}').status_code == 200


def library(page, url, width):
    page.goto(url)
    if width == 375: page.locator('.mobile-navigation-toggle').click()


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width,scheme',[(1280,'light'),(375,'dark')])
def test_folder_context_rename_preserves_reading_and_disclosure(browser, live_empty, folder_data, app, width, scheme):
    from playwright.sync_api import expect
    before = snapshot(app)
    with browser.new_context(viewport={'width':width,'height':1000},has_touch=width==375,color_scheme=scheme) as context:
        page = context.new_page(); errors=[];page.on('pageerror',lambda exc:errors.append(str(exc)))
        library(page,live_empty+'/folders?folder=Tech&view=all',width)
        group = page.locator('.feed-folder[data-folder="Tech"]')
        group.locator('summary').press('Enter')
        expect(group).not_to_have_attribute('open','')
        page.wait_for_function("() => JSON.parse(localStorage.getItem('feedastrolabe.feed-folders.v2'))?.states.Tech === false")
        original = page.url
        if width==375:group.locator('[data-context-trigger]').first.tap()
        else:group.locator('.folder-link').click(button='right')
        expect(page.get_by_role('menu')).to_be_visible()
        expect(group).not_to_have_attribute('open','')
        page.get_by_role('menuitem',name='名前を変更…').click()
        dialog = page.get_by_role('dialog')
        expect(dialog).to_be_visible();assert page.url == original
        dialog.get_by_label('フォルダー名',exact=True).fill('Case')
        dialog.get_by_role('button',name='保存',exact=True).click()
        expect(dialog.get_by_role('alert')).to_contain_text('同じ名前')
        expect(dialog.get_by_label('フォルダー名',exact=True)).to_have_value('Case')
        dialog.get_by_label('フォルダー名',exact=True).fill('Security News')
        dialog.get_by_role('button',name='保存',exact=True).click()
        expect(page.get_by_role('heading',level=1)).to_have_text('Security News の記事')
        assert parse_qs(urlsplit(page.url).query)['folder'] == ['Security News']
        expect(page.locator('.article-card')).to_have_count(3)
        group = page.locator('.feed-folder[data-folder="Security News"]')
        expect(group).not_to_have_attribute('open','')
        if width==375:page.locator('.mobile-navigation-toggle').click()
        group.locator('.folder-link').focus(); page.keyboard.press('Shift+F10')
        expect(page.get_by_role('menu')).to_be_visible()
        page.keyboard.press('End');expect(page.get_by_role('menuitem',name='名前を変更…')).to_be_focused()
        page.keyboard.press('Escape');expect(group.locator('.folder-link')).to_be_focused()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=f'/tmp/context-folder-{width}.png',full_page=True)
        assert not errors
    assert snapshot(app)==before


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width', [375,1280])
def test_feed_settings_save_errors_move_and_delete_in_place(browser, live_empty, folder_data, app, width):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':width,'height':1000},has_touch=width==375,color_scheme='dark' if width==375 else 'light') as context:
        page=context.new_page();library(page,live_empty+'/folders?folder=Tech',width)
        original=page.url;row=page.locator('[data-context-editor="/settings/items/feeds/2"]')
        row.locator('[data-context-trigger]').click();page.get_by_role('menuitem',name='設定…',exact=True).click()
        dialog=page.get_by_role('dialog');expect(dialog.get_by_label('間隔（秒）')).to_be_visible()
        assert page.url==original
        # A server validation error must preserve input, even though normal endpoints redirect.
        dialog.locator('[name=url]').fill('http://127.0.0.1/feed')
        dialog.get_by_role('button',name='URL を保存').click()
        expect(dialog.get_by_role('alert')).to_be_visible()
        expect(dialog.locator('[name=url]')).to_have_value('http://127.0.0.1/feed')
        dialog.locator('[name=url]').fill('https://example.com/2')
        dialog.get_by_role('button',name='URL を保存').click()
        expect(dialog.locator('[data-editor-feedback]')).to_have_text('保存しました。')
        dialog.get_by_label('間隔（秒）').fill('180')
        # Failed fetch keeps the unsaved value.
        page.route('**/settings/feeds/2',lambda route:route.abort())
        dialog.get_by_role('button',name='保存',exact=True).click()
        expect(dialog.get_by_role('alert')).to_contain_text('保存を確認できません')
        expect(dialog.get_by_label('間隔（秒）')).to_have_value('180')
        page.unroute('**/settings/feeds/2')
        dialog.get_by_role('button',name='保存',exact=True).click()
        expect(dialog.locator('[data-editor-feedback]')).to_have_text('保存しました。')
        assert page.url==original
        page.screenshot(path=f'/tmp/context-editor-{width}.png',full_page=True)
        assert dialog.evaluate('(el)=>el.scrollWidth <= el.clientWidth')
        with page.expect_navigation():
            dialog.get_by_role('button',name='閉じる',exact=True).click()
        expect(dialog).not_to_be_visible();expect(page).to_have_url(original)
        if width==375:page.locator('.mobile-navigation-toggle').click()
        row.locator('[data-context-trigger]').click();page.get_by_role('menuitem',name='フォルダーを変更…').click()
        expect(dialog.locator('[name=folder]')).to_be_focused()
        dialog.locator('[name=folder]').fill('ニュース');dialog.get_by_role('button',name='フォルダーを保存').click()
        expect(dialog.locator('[data-editor-feedback]')).to_have_text('保存しました。')
        with page.expect_navigation():
            dialog.get_by_role('button',name='閉じる',exact=True).click()
        expect(page.locator('.article-card')).to_have_count(1)
        if width==375:page.locator('.mobile-navigation-toggle').click()
        row.locator('[data-context-trigger]').click();page.get_by_role('menuitem',name='削除…',exact=True).click()
        expect(dialog.get_by_role('button',name='フィードと記事を削除する')).to_be_focused()
        dialog.get_by_role('button',name='フィードと記事を削除する').click()
        expect(dialog).not_to_be_visible()
        expect(page.locator('[data-context-editor="/settings/items/feeds/2"]')).to_have_count(0)
    with app.app_context():assert get_db().execute('SELECT 1 FROM feeds WHERE id=2').fetchone() is None


@pytest.mark.browser
@browser_only
def test_registered_objects_share_dialog_and_context_menus(browser, live_empty, objects):
    from playwright.sync_api import expect
    with browser.new_context() as context:
        page=context.new_page();page.goto(live_empty+'/settings')
        for kind,identifier in objects:
            if kind=='feeds':
                page.goto(live_empty+'/')
                link=page.locator(f'.feed-row[data-feed-id="{identifier}"] > a')
            else:
                page.goto(live_empty+'/settings')
                link=page.locator(f'a[href="/settings/items/{kind}/{identifier}"]')
            original=page.url
            link.click(button='right');page.get_by_role('menuitem',name='設定…',exact=True).click()
            dialog=page.get_by_role('dialog')
            expect(dialog.locator('[data-editor-content]')).to_be_visible()
            assert page.url==original
            page.keyboard.press('Escape');expect(dialog).not_to_be_visible()
        kind,wid=next(item for item in objects if item[0]=='workspaces')
        page.goto(live_empty+'/workspaces')
        page.locator(f'a[href="/workspaces/{wid}"]').click(button='right')
        page.get_by_role('menuitem',name='設定…',exact=True).click()
        ids = dialog.locator('[id]').evaluate_all('(nodes) => nodes.map(node => node.id)')
        for identifier in ids:
            assert page.locator('[id="'+identifier+'"]').count() == 1
        dialog.get_by_label('案件名',exact=True).fill('案件の名前を修正')
        dialog.get_by_role('button',name='案件を保存').click()
        expect(dialog.locator('[data-editor-feedback]')).to_have_text('保存しました。')
        with page.expect_navigation():
            dialog.get_by_role('button',name='閉じる',exact=True).click()
        expect(page.locator(f'a[href="/workspaces/{wid}"]')).to_contain_text('案件の名前を修正')
