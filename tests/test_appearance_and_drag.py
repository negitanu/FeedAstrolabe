"""Behavioral coverage for adaptive appearance and direct folder manipulation."""
import pytest
from werkzeug.datastructures import MultiDict

from test_reader import app, client, post
from test_reader_navigation import markup
from test_folders import folder_data, sidebar_names, snapshot
from test_feed_disclosure import browser, browser_only
from test_task_navigation import live_empty
from feedastrolabe.db import get_db


@pytest.mark.parametrize('theme', ['system', 'light', 'dark'])
def test_appearance_cookie_validated_and_shared_by_templates(client, theme):
    response = post(client, '/settings/appearance', {'theme': theme})
    assert response.status_code == 303 and response.location == '/settings/appearance'
    cookie = response.headers['Set-Cookie']
    assert 'HttpOnly' in cookie and 'SameSite=Lax' in cookie and 'Max-Age=31536000' in cookie
    for path in ['/', '/settings/appearance', '/settings/openrouter', '/workspaces', '/does-not-exist']:
        tree = markup(client.get(path,follow_redirects=True).data)
        assert tree.find('html').get('data-theme') == theme
    assert "script-src 'nonce-" in client.get('/settings/appearance').headers['Content-Security-Policy']


def test_appearance_invalid_inputs_and_default(client):
    assert markup(client.get('/').data).find('html').get('data-theme') == 'system'
    client.set_cookie('feedastrolabe_theme', '" onload="alert(1)')
    assert markup(client.get('/').data).find('html').get('data-theme') == 'system'
    for values in ({}, {'theme': 'unknown'}, {'theme': 'DARK'}, {'theme': 'dark;'}):
        assert post(client, '/settings/appearance', values).status_code == 400
    assert client.post('/settings/appearance', data={'theme':'dark'}).status_code == 400
    with client.session_transaction() as session: csrf = session['csrf']
    assert client.post('/settings/appearance', data=MultiDict([('csrf',csrf),('theme','light'),('theme','dark')])).status_code == 400


def test_drag_endpoint_security_and_json(folder_data, app, client):
    client.get('/')
    with client.session_transaction() as session: csrf = session['csrf']
    before = snapshot(app)
    headers = {'Accept':'application/json'}
    assert client.post('/settings/folders', data={'folder':'Tech','move':'up'}, headers=headers).status_code == 400
    assert client.post('/settings/folders', data={'csrf':csrf,'folder':'Tech','move':'position','position':'0'}, headers=headers).status_code == 400
    assert client.post('/settings/folders', data={'csrf':csrf,'folder':'missing','move':'up'}, headers=headers).status_code == 404
    saved = client.post('/settings/folders', data={'csrf':csrf,'folder':'Tech','move':'position','position':'1'}, headers=headers)
    assert saved.status_code == 200 and saved.json['position'] == 1 and saved.json['folders'][0] == 'Tech'
    assert sidebar_names(client.get('/')) == saved.json['folders']
    assert snapshot(app) == before
    assert "script-src 'nonce-" in client.get('/').headers['Content-Security-Policy']


def order(page, selector='.feed-folder'):
    return page.locator(selector).evaluate_all('(rows) => rows.map(row => row.dataset.folder)')


def mouse_drag(page, source, target):
    source.scroll_into_view_if_needed()
    a = source.bounding_box(); b = target.bounding_box()
    page.mouse.move(a['x'] + a['width']/2, a['y'] + a['height']/2)
    page.mouse.down()
    page.mouse.move(b['x'] + b['width']/2, b['y'] + 4, steps=12)
    page.mouse.up()


def touch_drag(page, source, target):
    source.scroll_into_view_if_needed()
    a = source.bounding_box(); b = target.bounding_box()
    x = a['x'] + a['width']/2; start = a['y'] + a['height']/2; end = b['y'] + 4
    cdp = page.context.new_cdp_session(page)
    cdp.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':x,'y':start}]})
    for step in range(1, 13):
        cdp.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':x,'y':start+(end-start)*step/12}]})
    cdp.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
    cdp.detach()


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width,touch', [(1280,False),(375,True)])
def test_drag_save_cancel_failure_and_keyboard(browser, live_empty, folder_data, app, width, touch):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':width,'height':1100}, is_mobile=touch, has_touch=touch) as context:
        page=context.new_page(); errors=[];page.on('pageerror',lambda exc:errors.append(str(exc)))
        page.goto(live_empty)
        if page.viewport_size['width']==375:page.locator('.mobile-navigation-toggle').click()
        # A real mouse/touch gesture, not DOM-dispatched fake drag events.
        original=order(page)
        handles=page.locator('[data-drag-handle]')
        (touch_drag if touch else mouse_drag)(page, handles.nth(1), page.locator('.feed-folder').first)
        expect(page.locator('[data-order-status]')).to_contain_text('移動しました')
        expected=[original[1],original[0],*original[2:]]
        assert order(page)==expected
        page.reload();assert order(page)==expected
        if width==375:page.locator('.mobile-navigation-toggle').click()
        # The handle supports keyboard ordering; controls track their new positions.
        page.locator('[data-drag-handle]').first.press('ArrowDown')
        expect(page.locator('[data-order-status]')).to_contain_text('2 番目')
        assert order(page)==original
        # Cancel an active drag, and a click with no movement, without any POST.
        posts=[];page.on('request',lambda req:posts.append(req.url) if req.method=='POST' else None)
        a=page.locator('[data-drag-handle]').nth(1).bounding_box()
        b=page.locator('.feed-folder').first.bounding_box()
        page.mouse.move(a['x']+10,a['y']+10);page.mouse.down();page.mouse.move(b['x']+10,b['y']+3,steps=8)
        page.keyboard.press('Escape');page.mouse.up()
        assert order(page)==original
        page.locator('[data-drag-handle]').first.click()
        assert not posts
        # A server failure restores order and exposes an actionable error.
        page.route('**/folders/order',lambda route:route.fulfill(status=500,body='error') if route.request.method=='POST' else route.continue_())
        page.locator('[data-drag-handle]').nth(1).press('ArrowUp')
        expect(page.get_by_role('alert')).to_contain_text('保存を確認できません')
        assert order(page)==original
        page.unroute('**/folders/order')
        # Save a different final order for cross-session verification.
        page.locator('[data-drag-handle]').nth(1).press('ArrowUp')
        expect(page.locator('[data-order-status]')).to_contain_text('1 番目')
        page.screenshot(path=f'/tmp/feedastrolabe-drag-{width}.png',full_page=True)
        assert not errors
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    # DB order visible to an independent browser session.
    with browser.new_context() as other:
        page=other.new_page();page.goto(live_empty)
        assert order(page,'.feed-folder')==expected


@pytest.mark.browser
@browser_only
def test_sidebar_drag_keeps_folder_destination_and_disclosure(browser, live_empty, folder_data):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':1280,'height':1100}) as context:
        page=context.new_page();page.goto(live_empty)
        original=order(page,'.feed-folder')
        second=page.locator('.feed-folder').nth(1)
        selected=second.get_attribute('data-folder')
        second.locator('summary').press('Enter')
        expect(second).not_to_have_attribute('open','')
        mouse_drag(page,second.locator('[data-drag-handle]'),page.locator('.feed-folder').first)
        expect(page.locator('[data-order-status]')).to_contain_text('移動しました')
        assert order(page,'.feed-folder')==[original[1],original[0],*original[2:]]
        assert page.url==live_empty+'/'
        page.reload()
        first=page.locator('.feed-folder').first
        expect(first).to_have_attribute('data-folder',selected)
        expect(first).not_to_have_attribute('open','')
        first.locator('.folder-link').click()
        expect(page.get_by_role('heading',level=1)).to_contain_text('の記事')
        expect(page.locator('.folder-link[aria-current]')).to_have_count(1)


PAGES=['/', '/folders?folder=Tech', '/settings', '/settings/appearance',
       '/settings/openrouter', '/settings/general', '/settings/connectors', '/settings/api',
       '/settings/imports','/settings/backup', '/workspaces', '/evidence', '/entities',
       '/security', '/network', '/ai-research', '/assistant', '/operations', '/operations/reports',
       '/social-research', '/navigate/collect', '/navigate/research', '/navigate/publish',
       '/sources/new/rss','/sources/new/sns','/sources/new/page','/sources/new/mastodon','/does-not-exist']


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width,scheme',[(1280,'light'),(375,'dark')])
def test_theme_system_explicit_and_all_page_surfaces(browser, live_empty, folder_data, width, scheme):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':width,'height':1000},color_scheme=scheme,java_script_enabled=False) as context:
        page=context.new_page();page.goto(live_empty+'/settings/appearance')
        expect(page.locator('html')).to_have_attribute('data-theme','system')
        expect(page.get_by_label('システムに合わせる',exact=True)).to_be_checked()
        def color():return page.locator('body').evaluate('(el) => getComputedStyle(el).backgroundColor')
        assert color()==('rgb(18, 25, 30)' if scheme=='dark' else 'rgb(247, 248, 249)')
        page.emulate_media(color_scheme='light' if scheme=='dark' else 'dark')
        assert color()==('rgb(247, 248, 249)' if scheme=='dark' else 'rgb(18, 25, 30)')
        for mode,label in [('dark','ダーク'),('light','ライト')]:
            page.goto(live_empty+'/settings/appearance')
            page.get_by_label(label,exact=True).check();page.get_by_role('button',name='保存',exact=True).click()
            expect(page.locator('html')).to_have_attribute('data-theme',mode)
            expect(page.get_by_label(label,exact=True)).to_be_checked()
            page.emulate_media(color_scheme='light' if mode=='dark' else 'dark')
            assert_theme_contrast(page)
            for path in PAGES:
                page.goto(live_empty+path)
                expect(page.locator('html')).to_have_attribute('data-theme',mode)
                assert color()==('rgb(18, 25, 30)' if mode=='dark' else 'rgb(247, 248, 249)'),path
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),path
                # All common panels and editable controls use adaptive surfaces.
                panels=page.locator('.settings-card,.article-card,.destination-card,input:not([type=hidden]):not([type=radio]):not([type=checkbox]),textarea,select')
                for panel in panels.all():
                    if not panel.is_visible():continue
                    surface=panel.evaluate('(el)=>getComputedStyle(el).backgroundColor')
                    assert surface not in (['rgb(255, 255, 255)','rgb(247, 248, 249)'] if mode=='dark' else ['rgb(18, 25, 30)','rgb(27, 37, 44)']),(path,surface)
            for path,name in [('/','reader'),('/settings','settings'),('/settings/appearance','appearance'),('/network','network')]:
                page.goto(live_empty+path)
                page.screenshot(path=f'/tmp/feedastrolabe-{name}-{mode}-{width}.png',full_page=True)
        # Browser-local choice does not impose the mode on a different browser.
    with browser.new_context(color_scheme='dark') as fresh:
        page=fresh.new_page();page.goto(live_empty)
        expect(page.locator('html')).to_have_attribute('data-theme','system')


def assert_theme_contrast(page):
    colors=page.locator('html').evaluate("""el => Object.fromEntries(
      ['ink','muted','accent','on-accent','bg','surface','light','danger','danger-bg','control-line']
        .map(name => [name,getComputedStyle(el).getPropertyValue('--'+name).trim()]))""")
    def luminance(value):
        rgb=[int(value[i:i+2],16)/255 for i in (1,3,5)]
        linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
        return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))
    for fg,bg in [('ink','bg'),('ink','surface'),('muted','surface'),('muted','bg'),
                  ('accent','light'),('on-accent','accent'),('danger','danger-bg')]:
        a,b=sorted([luminance(colors[fg]),luminance(colors[bg])])
        assert (b+.05)/(a+.05)>=4.5,(fg,bg,colors)
    a,b=sorted([luminance(colors['control-line']),luminance(colors['surface'])])
    assert (b+.05)/(a+.05)>=3


@pytest.mark.browser
@browser_only
def test_touch_cancel_and_downward_drag(browser, live_empty, folder_data):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':375,'height':1100},has_touch=True,is_mobile=True) as context:
        page=context.new_page();page.goto(live_empty)
        if page.viewport_size['width']==375:page.locator('.mobile-navigation-toggle').click()
        original=order(page)
        handle=page.locator('[data-drag-handle]').first
        a=handle.bounding_box();b=page.locator('.feed-folder').nth(1).bounding_box()
        cdp=context.new_cdp_session(page)
        def gesture(cancel):
            cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':a['x']+12,'y':a['y']+12}]})
            for step in range(1,13):
                cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':a['x']+12,'y':a['y']+12+(b['y']+b['height']-4-a['y']-12)*step/12}]})
            cdp.send('Input.dispatchTouchEvent',{'type':'touchCancel' if cancel else 'touchEnd','touchPoints':[]})
        gesture(True)
        assert order(page)==original
        gesture(False)
        expect(page.locator('[data-order-status]')).to_contain_text('2 番目')
        assert order(page)==[original[1],original[0],*original[2:]]
        cdp.detach()


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width', [375,1280])
def test_drag_autoscroll_to_last_position(browser, live_empty, folder_data, width, app):
    from playwright.sync_api import expect
    with app.app_context():
        with get_db() as db:
            for n in range(20):
                db.execute('INSERT INTO feeds(url,title,folder,created_at) VALUES(?,?,?,?)',
                           (f'https://example.com/scroll/{n}',f'Scroll {n}',f'Scroll {n:02}', '2026-10-24'))
    with browser.new_context(viewport={'width':width,'height':650}) as context:
        page=context.new_page();page.goto(live_empty)
        if page.viewport_size['width']==375:page.locator('.mobile-navigation-toggle').click()
        original=order(page)
        a=page.locator('[data-drag-handle]').first.bounding_box()
        page.mouse.move(a['x']+10,a['y']+10);page.mouse.down()
        page.mouse.move(a['x']+10,630,steps=15)
        page.wait_for_function("name => document.querySelector('.feed-navigation').lastElementChild.dataset.folder === name",arg=original[0])
        page.mouse.up()
        expect(page.locator('[data-order-status]')).to_contain_text(f'{len(original)} 番目')
        assert page.evaluate('scrollY')>0
        page.reload()
        assert order(page)==[*original[1:],original[0]]
