from urllib.parse import parse_qs, urlsplit

import pytest
from feedastrolabe.db import get_db
from test_reader import app, client, post
from test_folders import folder_data, article_ids
from test_reader_navigation import markup, content
from test_feed_disclosure import browser, browser_only
from test_task_navigation import live_empty


def unread_link(response):
    tree=markup(response.data)
    return tree.find('.//nav[@aria-label="記事の表示条件"]/a[@href="/?view=unread"]')


@pytest.mark.parametrize('url',[
    '/folders?folder=Tech', '/folders?folder=Tech&view=unread',
    '/?feed=2&q=Story', '/folders?folder=Tech&q=missing', '/folders?folder=',
])
def test_global_unread_link_clears_scope(folder_data,client,url):
    link=unread_link(client.get(url))
    assert link is not None
    assert content(link.find('span[@class="count"]'))=='4'
    assert 'active' not in link.get('class').split()
    response=client.get(link.get('href'))
    assert article_ids(response)==[5,4,3,2]
    assert 'active' in unread_link(response).get('class').split()


def test_global_unread_counts_after_visit_and_bulk(folder_data,app,client):
    response=post(client,'/articles/3/visit',{'folder':'Tech'},headers={'X-Reader-State':'1'})
    assert response.json['counts']['unread']==3
    assert response.json['counts']['total']==3
    assert response.json['total']==3
    assert content(unread_link(client.get('/folders?folder=Tech')).find('span[@class="count"]'))=='3'
    post(client,'/articles/read-all',{'folder':'Tech'})
    assert article_ids(client.get('/?view=unread'))==[5,4]
    post(client,'/articles/read-all',{'view':'unread'})
    assert article_ids(client.get('/?view=unread'))==[]
    with app.app_context():
        assert get_db().execute('SELECT sum(is_read) FROM articles').fetchone()[0]==5


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width,theme,javascript',[
    (1280,'light',True),(1280,'dark',True),(1280,'system',True),
    (390,'light',True),(390,'dark',True),(390,'system',True),
    (1280,'light',False),(390,'dark',False),
])
def test_unread_from_folder_is_global(browser,live_empty,folder_data,app,width,theme,javascript):
    from playwright.sync_api import expect
    from feedastrolabe.presentation import THEME_COOKIE
    with browser.new_context(viewport={'width':width,'height':900},java_script_enabled=javascript,
                             is_mobile=width==390,has_touch=width==390,
                             color_scheme='dark' if theme=='system' else theme) as context:
        context.add_cookies([{'name':THEME_COOKIE,'value':theme,'url':live_empty}])
        page=context.new_page();page.route('**/articles/*/hero',lambda route:route.abort())
        page.goto(live_empty+'/folders?folder=Tech')
        nav=page.get_by_role('navigation',name='記事の表示条件',include_hidden=True)
        link=nav.locator('a[href="/?view=unread"]')
        expect(link.locator('.count')).to_have_text('4')
        page.locator('.article-title').first.click()
        if javascript:
            expect(page.locator('#article-detail').get_by_role('button',name='未読に戻す',exact=True)).to_be_visible()
            expect(link.locator('.count')).to_have_text('3')
        page.locator('#article-detail .detail-top a').click()
        expect(page.locator('#article-detail')).to_have_count(0)
        page.get_by_role('button',name='全て既読',exact=True).click()
        expect(page.locator('.article-card').first.locator('form[action$="/read"] [name=value]')).to_have_value('0')
        if width==390:
            toggle=page.locator('.mobile-navigation-toggle')
            if not link.is_visible():toggle.click()
        expect(link.locator('.count')).to_have_text('2')
        link.click()
        assert parse_qs(urlsplit(page.url).query)=={'view':['unread']}
        expect(page.get_by_role('heading',level=1)).to_have_text('未読の記事')
        expect(page.locator('.article-card')).to_have_count(2)
        expect(page.locator('.article-card').nth(0)).to_contain_text('Story 5')
        expect(page.locator('.article-card').nth(1)).to_contain_text('Story 4')
        assert 'active' in link.get_attribute('class').split()
        if javascript:
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
