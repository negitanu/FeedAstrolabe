import pytest
from feedastrolabe.db import get_db
from test_reader import app, client
from test_reader_navigation import reading_library, live_sequence, markup
from test_feed_disclosure import browser, browser_only


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width',[375,1280])
@pytest.mark.parametrize('theme',['light','dark','system'])
def test_outside_click_motion_and_selected_style(browser,live_sequence,width,theme,tmp_path):
    from playwright.sync_api import expect
    from feedastrolabe.presentation import THEME_COOKIE
    base,_=live_sequence
    with browser.new_context(viewport={'width':width,'height':900},color_scheme='dark' if theme=='system' else theme) as context:
        context.add_cookies([{'name':THEME_COOKIE,'value':theme,'url':base}])
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('**/articles/*/hero',lambda route:route.abort())
        page.goto(base+'/?sort=oldest&all=1')
        cards=page.locator('.article-card');count=cards.count();first=cards.first
        first.locator('[data-select-article]').check()
        chosen=first.get_attribute('data-article-id')
        first.locator('.article-title').click()
        panel=page.locator('#article-detail');expect(panel).to_be_visible()
        page.wait_for_function('()=>document.querySelector("#article-detail").getAnimations().length===0')
        page.screenshot(path=f'/private/tmp/panel-open-{width}-{theme}.png')
        panel.locator('h2').click();expect(panel).to_be_visible()
        # Outside checkbox remains usable and closes the panel with an actual exit animation.
        page.evaluate('''()=>{const panel=document.querySelector('#article-detail');document.querySelectorAll('[data-select-article]')[1].click();window.exitAnimation=panel.inert && panel.getAnimations().some(a=>a.effect.getTiming().duration===180);}''')
        assert page.evaluate('window.exitAnimation')
        expect(panel).to_have_count(0)
        expect(page.locator('[data-selection-count]')).to_have_text('2 件を選択')
        assert 'article=' not in page.url and 'sort=oldest' in page.url
        assert cards.count()==count and first.locator('[data-select-article]').is_checked()
        # Browser back reopens; choosing another article must not be cancelled by outside handling.
        page.go_back();expect(panel).to_be_visible()
        page.evaluate('document.querySelectorAll("a.article-title")[2].click()')
        expect(panel.locator('h2')).to_contain_text('Story 3')
        page.locator('.workspace .topbar').click(position={'x':5,'y':5});expect(panel).to_have_count(0)
        # Initial detail load and reduced-motion closing.
        page.emulate_media(reduced_motion='reduce')
        page.goto(base+'/?article='+chosen)
        expect(panel).to_be_visible()
        assert panel.evaluate('el=>el.getAnimations().length')==0
        page.locator('.workspace .topbar').click(position={'x':5,'y':5});expect(panel).to_have_count(0)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=f'/private/tmp/panel-{width}-{theme}.png')
        assert errors==[]


@pytest.mark.browser
@browser_only
def test_close_ignores_stale_detail_and_save_response(browser,live_sequence,app):
    from playwright.sync_api import expect
    base,_=live_sequence
    with browser.new_context(viewport={'width':1280,'height':900}) as context:
        page=context.new_page();page.route('**/articles/*/hero',lambda route:route.abort())
        page.goto(base+'/?article=15&all=1')
        panel=page.locator('#article-detail');expect(panel).to_be_visible()
        # Hold an already-produced save response, then close while saving.
        held=[]
        def hold(route):held.append((route,route.fetch()))
        page.route('**/articles/15/star',hold)
        panel.locator('form[action="/articles/15/star"] button').click()
        page.wait_for_timeout(100)
        page.locator('.workspace .topbar').click(position={'x':5,'y':5});expect(panel).to_have_count(0)
        assert held
        route,response=held.pop();route.fulfill(response=response)
        expect(page.locator('[data-article-id="15"] form[action$="/star"] [name=value]')).to_have_value('1')
        expect(panel).to_have_count(0)
        assert 'article=' not in page.url
        # A delayed detail fetch from an already-open panel must not reopen after closing.
        page.goto(base+'/?article=15&all=1');expect(panel).to_be_visible()
        held=[]
        page.route('**/*',lambda route: hold(route) if route.request.headers.get('x-reader-detail')=='1' else route.continue_())
        page.evaluate('document.querySelector("[data-article-id=\'16\'] a.article-title").click()')
        page.wait_for_timeout(100)
        page.locator('.workspace .topbar').click(position={'x':5,'y':5});expect(panel).to_have_count(0)
        assert held
        route,response=held.pop();route.fulfill(response=response)
        page.wait_for_timeout(250)
        expect(panel).to_have_count(0)
        assert 'article=' not in page.url
        # Saving an older article must preserve a newer detail selected before the response arrives.
        page.unroute('**/*')
        page.route('**/articles/*/hero',lambda route:route.abort())
        page.goto(base+'/?article=15&all=1');expect(panel).to_be_visible()
        held=[];page.route('**/articles/15/star',hold)
        panel.locator('form[action="/articles/15/star"] button').click()
        page.wait_for_timeout(100)
        page.evaluate('document.querySelector("[data-article-id=\'16\'] a.article-title").click()')
        expect(panel.locator('h2')).to_contain_text('Story 16')
        assert held
        route,response=held.pop();route.fulfill(response=response)
        expect(page.locator('[data-article-id="15"] form[action$="/star"] [name=value]')).to_have_value('0')
        expect(panel.locator('h2')).to_contain_text('Story 16')
        assert 'article=16' in page.url
