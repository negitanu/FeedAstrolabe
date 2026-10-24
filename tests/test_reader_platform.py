"""End-to-end contracts for the continuous reader and contextual library controls."""
import json
import time
from urllib.parse import urlencode, urlsplit, parse_qs
import pytest
from werkzeug.datastructures import MultiDict
from feedastrolabe.db import get_db, init_database
from feedastrolabe import collection
from feedastrolabe.folders import feed_groups, feed_rows, move_feed, move_folder
from feedastrolabe.subscriptions import update_subscription
from test_reader import app, client, post
from test_folders import folder_data, snapshot, sidebar_names
from test_reader_navigation import markup
from test_feed_disclosure import browser, browser_only
from test_task_navigation import live_empty
from test_appearance_and_drag import mouse_drag, touch_drag, assert_theme_contrast


@pytest.fixture
def streaming_data(app,folder_data):
    with app.app_context(),get_db() as db:
        for n in range(6,126):
            db.execute('INSERT INTO articles(id,feed_id,guid,title,content,search_text,published_at) VALUES(?,?,?,?,?,?,?)',
                (n,2,str(n),f'Stream story {n}','<p>Stream body</p>','Stream match','2026-10-25'))
    return 123


def ids(response):
    tree=markup(response.data)
    return [int(row.get('data-article-id')) for row in tree.findall('.//article[@data-article-id]')]


def test_continuation_scope_order_changes_and_bulk_read(app,client,streaming_data):
    first=client.get('/folders?folder=Tech&view=unread')
    assert len(ids(first))==30
    assert markup(first.data).find('.//div[@class="pagination"]') is None
    next_url=markup(first.data).find('.//*[@data-article-loader]').get('data-more-url')
    assert client.get(next_url.replace('folder=Tech','folder=case')).status_code==400
    values=parse_qs(urlsplit(next_url).query);values['cursor'][0]+='x'
    assert client.get('/articles/more?'+urlencode({k:v[0] for k,v in values.items()})).status_code==400
    with app.app_context(),get_db() as db:
        db.execute("INSERT INTO articles(feed_id,guid,title,content,search_text,published_at) VALUES(2,'new','Newest','','','2026-10-26')")
        # Delete an earlier row; offset-based pagination would skip an unseen row.
        db.execute('DELETE FROM articles WHERE id=125')
    seen=ids(first)
    while next_url:
        response=client.get(next_url);assert response.status_code==200
        seen+=ids(type('Fragment',(),{'data':response.json['html'].encode()})())
        next_url=response.json['next']
    assert len(seen)==len(set(seen))==122
    assert seen==list(range(125,5,-1))+[3,2]
    assert 126 not in seen
    post(client,'/articles/read-all',{'folder':'Tech','view':'unread'})
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE f.folder="Tech" AND is_read=0').fetchone()[0]==0
        assert get_db().execute('SELECT is_read FROM articles WHERE id=4').fetchone()[0]==0
    all_results=client.get('/folders?folder=Tech&all=1')
    assert len(ids(all_results))==123
    assert markup(client.get('/settings/general').data).find('.//input[@name="page_size"]') is None


@pytest.mark.parametrize('fid',[1,2,3,8])
def test_stop_resume_preserves_data_and_configuration(app,client,folder_data,monkeypatch,fid):
    with app.app_context():before=dict(get_db().execute('SELECT * FROM feeds WHERE id=?',(fid,)).fetchone())
    articles=snapshot(app)
    assert post(client,f'/feeds/{fid}/subscription',{'enabled':'0'}).json['enabled'] is False
    monkeypatch.setattr(collection,'fetch',lambda *args:pytest.fail('paused feeds must not be fetched'))
    with app.app_context():
        assert collection.refresh_feeds(fid)==(0,0)
        after=dict(get_db().execute('SELECT * FROM feeds WHERE id=?',(fid,)).fetchone())
        assert {k:v for k,v in after.items() if k!='enabled'}=={k:v for k,v in before.items() if k!='enabled'}
    assert snapshot(app)==articles
    assert post(client,f'/feeds/{fid}/subscription',{'enabled':'1'}).json['enabled'] is True


def test_subscription_validation_and_retired_source(app,client,folder_data):
    assert client.post('/feeds/2/subscription',data={'enabled':'0'}).status_code==400
    assert post(client,'/feeds/2/subscription',{'enabled':'false'}).status_code==400
    assert post(client,'/feeds/999/subscription',{'enabled':'0'}).status_code==404
    client.get('/')
    with client.session_transaction() as session:csrf=session['csrf']
    assert client.post('/feeds/2/subscription',data=MultiDict([('csrf',csrf),('enabled','0'),('enabled','1')])).status_code==400
    with app.app_context(),get_db() as db:db.execute("UPDATE feeds SET source_type='x',enabled=0 WHERE id=8")
    assert post(client,'/feeds/8/subscription',{'enabled':'1'}).status_code==400


def test_feed_order_cross_folder_exact_identity_and_restore(app,client,folder_data,tmp_path):
    before=snapshot(app)
    with app.app_context():
        move_feed(3,'Tech','Tech',1)
        assert [f['id'] for g in feed_groups(feed_rows()) if g['name']=='Tech' for f in g['feeds']]==[3,2]
        move_feed(2,'Tech','',1)
        assert [f['id'] for g in feed_groups(feed_rows()) if g['name']=='' for f in g['feeds']]==[2,1]
        with pytest.raises(ValueError):move_feed(2,'Tech','case',1)
    assert snapshot(app)==before
    assert post(client,'/feeds/2/order',{'source':'','folder':'missing','position':'1'}).status_code==404
    assert post(client,'/feeds/2/order',{'source':'','folder':'','position':'0'}).status_code==400
    init_database(app.config['DATABASE'])
    from feedastrolabe.maintenance import backup,restore
    backup(app.config['DATABASE'],tmp_path/'backup.sqlite3');restore(tmp_path/'backup.sqlite3',tmp_path/'restored'/'copy.sqlite3')
    from feedastrolabe.db import connect
    with connect(tmp_path/'restored'/'copy.sqlite3') as db:
        assert db.execute('SELECT folder FROM feeds WHERE id=2').fetchone()[0]==''
        assert db.execute('SELECT position FROM feed_positions WHERE feed_id=2').fetchone()[0]==0
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_large_library_batches_are_bounded_and_complete(app,client):
    with app.app_context(),get_db() as db:
        db.executemany('INSERT INTO feeds(id,url,title,folder,created_at) VALUES(?,?,?,?,?)',
            ((n,f'https://example.com/{n}',f'Feed {n}',f'Group {n%11}','2026-10-24') for n in range(1,501)))
        db.executemany('INSERT INTO articles(id,feed_id,guid,title,content,search_text,published_at) VALUES(?,?,?,?,?,?,?)',
            ((n,n%500+1,str(n),f'Story {n}','<p>Body</p>','Body','2026-10-24') for n in range(1,10001)))
    start=time.monotonic();first=client.get('/');elapsed=time.monotonic()-start
    assert len(ids(first))==30 and len(first.data)<1000000
    assert len(markup(first.data).findall('.//*[@data-feed-id]'))==500
    next_url=markup(first.data).find('.//*[@data-article-loader]').get('data-more-url');seen=ids(first)
    while next_url:
        result=client.get(next_url);assert result.status_code==200
        seen+=ids(type('Fragment',(),{'data':result.json['html'].encode()})())
        next_url=result.json['next']
    assert seen==list(range(10000,0,-1))
    print(f'Large library: initial {elapsed:.3f}s, {len(first.data)} bytes, 30 cards; 10000 unique articles, 500 feeds')


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width,scheme',[(1280,'light'),(375,'dark')])
def test_scroll_retry_detail_history_and_bulk(browser,live_empty,streaming_data,app,width,scheme):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':width,'height':900},color_scheme=scheme) as context:
        page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(live_empty+'/folders?folder=Tech&view=unread')
        expect(page.locator('.article-card')).to_have_count(30)
        assert_theme_contrast(page)
        button=page.get_by_role('button',name='全て既読',exact=True)
        assert button.evaluate('(el)=>getComputedStyle(el).backgroundColor')!=page.locator('body').evaluate('(el)=>getComputedStyle(el).backgroundColor')
        page.route('**/articles/more**',lambda route:route.abort())
        page.locator('[data-article-loader]').scroll_into_view_if_needed()
        expect(page.get_by_role('button',name='再読み込み',exact=True)).to_be_visible()
        expect(page.locator('.article-card')).to_have_count(30)
        page.unroute('**/articles/more**');page.get_by_role('button',name='再読み込み',exact=True).click()
        expect(page.locator('.article-card')).to_have_count(60)
        card=page.locator('.article-card').nth(45);aid=card.get_attribute('data-article-id')
        card.locator('.article-title').click();expect(page.locator('#article-detail')).to_contain_text('Stream story')
        count=page.locator('.article-card').count()
        page.locator('#article-detail .detail-top a').click()
        expect(page.locator('#article-detail')).to_have_count(0)
        expect(page.locator('.article-card')).to_have_count(count)
        page.go_back();expect(page.locator('#article-detail')).to_be_visible()
        page.go_forward();expect(page.locator('#article-detail')).to_have_count(0)
        assert page.locator('.article-card').count()>=count
        # A deep card state action must reconcile that card without losing loaded content.
        row=page.locator(f'[data-article-id="{aid}"]');row.locator('form[action$="/star"] button').click()
        expect(row.locator('form[action$="/star"] [name=value]')).to_have_value('0')
        assert page.locator('.article-card').count()>=count
        for _ in range(6):
            if not page.locator('[data-article-loader]').count():break
            previous=page.locator('.article-card').count()
            page.locator('[data-article-loader]').scroll_into_view_if_needed()
            page.wait_for_function('(count) => document.querySelectorAll(".article-card").length>count || !document.querySelector("[data-article-loader]")',arg=previous)
        expect(page.locator('.article-card')).to_have_count(122)
        assert len(set(page.locator('.article-card').evaluate_all('(nodes)=>nodes.map(node=>node.dataset.articleId)')))==122
        button.click();expect(page.locator('.article-card')).to_have_count(0)
        assert errors==[]
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=f'/tmp/feedastrolabe-continuous-{width}.png',full_page=True)
    with app.app_context():assert get_db().execute('SELECT is_read FROM articles WHERE id=4').fetchone()[0]==0


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width,touch',[(1280,False),(375,True)])
def test_sidebar_feed_drag_stop_and_width(browser,live_empty,folder_data,app,width,touch):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':width,'height':1100},has_touch=touch,is_mobile=touch) as context:
        page=context.new_page();page.goto(live_empty)
        if touch:page.locator('.mobile-navigation-toggle').tap()
        tech=page.locator('.feed-folder[data-folder="Tech"]')
        before=lambda:tech.locator('.feed-row').evaluate_all('(nodes)=>nodes.map(node=>node.dataset.feedId)')
        assert before()==['2','3']
        (touch_drag if touch else mouse_drag)(page,tech.locator('[data-feed-drag]').nth(1),tech.locator('.feed-row').first)
        expect(page.locator('[data-order-status]')).to_contain_text('移動しました')
        assert before()==['3','2']
        tech.locator('[data-feed-drag]').first.press('End')
        expect(page.locator('[data-order-status]')).to_contain_text('2 番目')
        assert before()==['2','3']
        news=page.locator('.feed-folder[data-folder="ニュース"]');news.locator('summary').press('Enter')
        expect(news).not_to_have_attribute('open','')
        (touch_drag if touch else mouse_drag)(page,tech.locator('[data-feed-drag]').first,news.locator('summary'))
        expect(page.locator('[data-order-status]')).to_contain_text('移動しました')
        expect(news).not_to_have_attribute('open','')
        page.reload()
        if touch:page.locator('.mobile-navigation-toggle').tap()
        news.locator('summary').press('Enter')
        row=page.locator('.feed-row[data-feed-id="2"]')
        row.locator('[data-context-trigger]').click();page.get_by_role('menuitem',name='購読停止',exact=True).click()
        expect(page.get_by_role('dialog')).not_to_be_visible()
        page.wait_for_function('() => document.querySelector(".feed-row[data-feed-id=\\"2\\"] .feed-title").textContent.includes("Ⅱ")')
        if touch:page.locator('.mobile-navigation-toggle').tap()
        row.locator('[data-context-trigger]').click();page.get_by_role('menuitem',name='購読再開',exact=True).click()
        page.wait_for_function('() => !document.querySelector(".feed-row[data-feed-id=\\"2\\"] .feed-title").textContent.includes("Ⅱ")')
        if not touch:
            separator=page.get_by_role('separator',name='左ペインの幅')
            separator.focus();separator.press('ArrowRight')
            expect(separator).to_have_attribute('aria-valuenow','264')
            box=separator.bounding_box();y=max(100,box['y']+20);page.mouse.move(box['x']+2,y);page.mouse.down();page.mouse.move(box['x']+82,y,steps=8);page.mouse.up()
            expect(separator).to_have_attribute('aria-valuenow','344')
            page.reload();expect(separator).to_have_attribute('aria-valuenow','344')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=f'/tmp/feedastrolabe-library-{width}.png',full_page=True)


def test_new_feeds_append_and_folder_updates_keep_order(app,folder_data):
    with app.app_context(),get_db() as db:
        move_feed(3,'Tech','Tech',1)
        db.execute("INSERT INTO feeds(id,url,title,folder,created_at) VALUES(9,'https://example.com/new-z','Zed','Tech','2026-10-24')")
        db.execute("INSERT INTO feeds(id,url,title,folder,created_at) VALUES(10,'https://example.com/new-a','Alpha','Tech','2026-10-24')")
    with app.app_context():
        assert [f['id'] for g in feed_groups(feed_rows()) if g['name']=='Tech' for f in g['feeds']]==[3,2,9,10]
        update_subscription(1,{'folder':'Tech'})
        assert [f['id'] for g in feed_groups(feed_rows()) if g['name']=='Tech' for f in g['feeds']]==[3,2,9,10,1]


@pytest.mark.browser
@browser_only
def test_remote_keyboard_and_optional_post_open(browser,live_empty,streaming_data,app):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':1280,'height':900}) as context:
        page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(live_empty+'/folders?folder=Tech')
        cards=page.locator('.article-card');expect(cards).to_have_count(30)
        target=cards.nth(1).get_attribute('data-article-id')
        page.keyboard.press('j');expect(cards.nth(1)).to_have_class(__import__('re').compile('keyboard-focus'))
        page.keyboard.press('o');expect(page.locator('#article-detail')).to_be_visible()
        assert 'article='+target in page.url
        page.keyboard.press('s')
        expect(page.locator(f'[data-article-id="{target}"] form[action$="/star"] [name=value]')).to_have_value('0')
        csrf=page.locator('input[name=csrf]').first.input_value()
        response=page.request.post(live_empty+'/reading-prefs',form={'csrf':csrf,'list_density':'compact','mark_read_on_open':'1'})
        assert response.ok
        page.reload()
        with app.app_context():assert get_db().execute('SELECT is_read FROM articles WHERE id=?',(target,)).fetchone()[0]==0
        page.locator('#article-detail .detail-top a').click()
        expect(page.locator('#article-detail')).to_have_count(0)
        page.locator(f'[data-article-id="{target}"] .open-form button').click()
        expect(page.locator(f'[data-article-id="{target}"]')).to_have_class(__import__('re').compile(r'\bread\b'))
        with app.app_context():assert get_db().execute('SELECT is_read FROM articles WHERE id=?',(target,)).fetchone()[0]==1
        assert errors==[]
