"""Folder-level reading must retain its exact scope for every article action."""
from urllib.parse import parse_qs, urlsplit, urlencode
import pytest
from werkzeug.datastructures import MultiDict
from feedastrolabe.db import get_db
from test_reader import app, client, post
from test_folders import folder_data, article_ids, snapshot
from test_reader_navigation import markup
from test_feed_disclosure import browser, browser_only
from test_task_navigation import live_empty


@pytest.mark.parametrize('query,ids', [({'view':'unread'},[3,2]),({'view':'starred'},[2]),
    ({'q':'Story 1'},[1]),({'q':'100%'},[]),({'feed':'2'},[2,1]),({'feed':'4'},[])])
def test_folder_filters_intersect(folder_data,client,query,ids):
    assert article_ids(client.get('/folders?'+urlencode({'folder':'Tech',**query})))==ids
    assert article_ids(client.get('/?'+urlencode({'folder':'Tech',**query})))==ids


def test_folder_pagination_and_workspace_tag_scope(folder_data,app,client):
    with app.app_context():
        with get_db() as db:
            db.execute('UPDATE settings SET page_size=10 WHERE id=1')
            for number in range(6,20):
                db.execute('INSERT INTO articles(id,feed_id,guid,title,content,search_text,published_at) VALUES(?,?,?,?,?,?,?)',
                           (number,2 if number%2 else 3,str(number),f'Page story {number}','body','body','2026-10-24'))
            db.execute("INSERT INTO workspaces(id,title,created_at,updated_at) VALUES(1,'Scope','2026-10-24','2026-10-24')")
            db.execute('INSERT INTO workspace_articles(workspace_id,article_id) VALUES(1,1)')
            db.execute("INSERT INTO tags(id,name) VALUES(1,'Scope')")
            db.execute('INSERT INTO article_tags(article_id,tag_id) VALUES(1,1)')
    first=client.get('/folders?folder=Tech')
    assert len(article_ids(first))==17
    assert markup(first.data).find(".//div[@class='pagination']") is None
    assert article_ids(first)==list(range(19,5,-1))+[3,2,1]
    assert article_ids(client.get('/folders?folder=Tech&workspace=1&tag=1'))==[1]
    assert article_ids(client.get('/folders?folder='+urlencode({'x':'ニュース'})[2:]+'&workspace=1&tag=1'))==[]


def test_folder_detail_and_read_next_stay_inside_folder(folder_data,app,client):
    # Story 4 and 5 belong elsewhere and must never become neighbours.
    page=client.get('/folders?folder=Tech&article=3')
    tree=markup(page.data)
    assert tree.find(".//section[@id='article-detail']") is not None
    assert {parse_qs(urlsplit(a.get('href')).query)['article'][0] for a in tree.findall(".//a[@rel='next']")}=={'2'}
    result=post(client,'/articles/3/read-next',{'folder':'Tech','view':'unread'})
    assert result.status_code==303 and urlsplit(result.location).path=='/folders'
    assert parse_qs(urlsplit(result.location).query)['folder']==['Tech']
    assert parse_qs(urlsplit(result.location).query)['article']==['2']
    result=post(client,'/articles/2/read-next',{'folder':'Tech','view':'unread'})
    assert 'article' not in parse_qs(urlsplit(result.location).query)
    assert article_ids(client.get(result.location))==[]
    assert client.get('/folders?folder=Tech&article=4').status_code==404
    assert post(client,'/articles/4/read-next',{'folder':'Tech'}).status_code==409
    with app.app_context():
        assert [r[0] for r in get_db().execute('SELECT id FROM articles WHERE is_read=0 ORDER BY id')]==[4,5]


@pytest.mark.parametrize('folder,query,changed', [('Tech',{},[2,3]),('Tech',{'q':'Story 2'},[2]),
    ('Tech',{'view':'starred'},[2]),('',{},[5])])
def test_folder_bulk_read_scoped(folder_data,app,client,folder,query,changed):
    response=post(client,'/articles/read-all',{'folder':folder,'next':'/folders?'+urlencode({'folder':folder}),**query})
    assert response.status_code==302
    with app.app_context():
        assert [r[0] for r in get_db().execute('SELECT id FROM articles WHERE is_read=1 ORDER BY id')]==sorted([1,*changed])


def test_folder_invalid_mutations_do_not_change_articles(folder_data,app,client):
    before=snapshot(app)
    for folder in ['missing','x'*81,'\x00']:
        assert post(client,'/articles/read-all',{'folder':folder}).status_code in (400,404)
    client.get('/')
    with client.session_transaction() as session:csrf=session['csrf']
    assert client.post('/articles/read-all',data=MultiDict([('csrf',csrf),('folder','Tech'),('folder','ニュース')])).status_code==400
    assert snapshot(app)==before


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width,javascript',[(1280,True),(375,True),(1280,False),(375,False)])
def test_folder_click_search_and_actions(browser,live_empty,folder_data,width,javascript):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':width,'height':900},java_script_enabled=javascript,
                             is_mobile=width==375,has_touch=width==375,color_scheme='dark') as context:
        page=context.new_page();page.goto(live_empty)
        if width==375 and javascript:page.locator('.mobile-navigation-toggle').tap()
        page.locator('.feed-folder[data-folder="Tech"] .folder-link').click()
        expect(page.get_by_role('heading',level=1)).to_have_text('Tech の記事')
        expect(page.locator('.article-card')).to_have_count(3)
        expect(page.locator('.folder-feed-card')).to_have_count(0)
        assert 'Story 4' not in page.locator('.article-list').inner_text()
        page.get_by_label('記事を検索',exact=True).fill('Story 2')
        page.get_by_role('button',name='検索',exact=True).click()
        expect(page.locator('.article-card')).to_have_count(1)
        assert parse_qs(urlsplit(page.url).query)['folder']==['Tech']
        page.locator('.article-title').click()
        expect(page.locator('#article-detail')).to_contain_text('Story 2')
        page.locator('#article-detail').get_by_role('button',name='★ 保存済み',exact=True).click()
        assert parse_qs(urlsplit(page.url).query)['folder']==['Tech']
        page.locator('#article-detail').get_by_role('button',name='既読にする',exact=True).click()
        assert parse_qs(urlsplit(page.url).query)['folder']==['Tech']
        page.locator('#article-detail').get_by_role('link',name='閉じる ×',exact=True).click()
        expect(page.locator('#article-detail')).to_have_count(0)
        page.get_by_label('記事を検索',exact=True).fill('')
        page.get_by_role('button',name='検索',exact=True).click()
        page.get_by_role('button',name='全て既読',exact=True).click()
        if width==375 and javascript:page.locator('.mobile-navigation-toggle').tap()
        page.get_by_role('navigation',name='記事の表示条件').get_by_role('link').filter(has_text='未読').click()
        expect(page.locator('.article-card')).to_have_count(0)
        assert parse_qs(urlsplit(page.url).query)['folder']==['Tech']
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.goto(live_empty+'/folders?folder=Tech')
        page.screenshot(path=f'/tmp/feedastrolabe-folder-articles-{width}-{javascript}.png',full_page=True)


def test_empty_folder_scope_survives_read_next(folder_data,client):
    response=post(client,'/articles/5/read-next',{'folder':'','view':'all'})
    assert response.status_code==303
    assert urlsplit(response.location).path=='/folders'
    assert parse_qs(urlsplit(response.location).query,keep_blank_values=True)['folder']==['']
    assert article_ids(client.get(response.location))==[5]


def test_folder_sidebar_counts_match_selected_scope(folder_data,client):
    for folder,counts in [('Tech',['3','2','1']),('', ['1','1','0'])]:
        tree=markup(client.get('/folders?'+urlencode({'folder':folder})).data)
        assert [n.text for n in tree.findall(".//nav[@aria-label='記事の表示条件']/a/span[@class='count']")]==counts


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width', [375,1280])
def test_only_folder_arrow_changes_disclosure(browser,live_empty,folder_data,width):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':width,'height':900},is_mobile=width==375,has_touch=width==375) as context:
        page=context.new_page();page.goto(live_empty)
        if width==375:page.locator('.mobile-navigation-toggle').tap()
        folder=page.locator('.feed-folder[data-folder="Tech"]')
        arrow=folder.locator(':scope > summary')
        arrow.click(position={'x':8,'y':16})
        expect(folder).to_have_js_property('open',False)
        page.wait_for_function("() => JSON.parse(localStorage.getItem('feedastrolabe.feed-folders.v2'))?.states?.Tech === false")
        folder.locator('.folder-link').click()
        expect(page.get_by_role('heading',level=1)).to_have_text('Tech の記事')
        expect(page.locator('.article-card')).to_have_count(3)
        expect(folder).to_have_js_property('open',False)
        page.reload()
        expect(folder).to_have_js_property('open',False)
        if width==375:page.locator('.mobile-navigation-toggle').tap()
        current=page.url
        arrow.click(position={'x':8,'y':16})
        expect(folder).to_have_js_property('open',True)
        assert page.url==current
        page.wait_for_function("() => JSON.parse(localStorage.getItem('feedastrolabe.feed-folders.v2'))?.states?.Tech === true")
        folder.locator('.folder-link').click()
        expect(folder).to_have_js_property('open',True)
