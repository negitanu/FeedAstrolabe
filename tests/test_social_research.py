from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from feedastrolabe import collection, create_app, social
from feedastrolabe import social_research as research
from feedastrolabe.db import get_db, init_database
from feedastrolabe.evidence_backup import backup_bundle, restore_bundle
from feedastrolabe.preferences import due_at, preferences
from feedastrolabe.social_http import SocialError
from feedastrolabe.subscriptions import update_subscription, delete_subscription
from test_reader import app, client, post
from test_phase_two import authorization
from test_feed_disclosure import browser, browser_only, live_reader
from test_social import mastodon_post


def bpost(key='one', hours=1, likes=3, reposts=2, replies=1):
    return {'uri': 'at://did:plc:researchfixture/app.bsky.feed.post/' + key,
            'author': {'did': 'did:plc:researchfixture', 'handle': 'fixture.bsky.social'},
            'record': {'$type': 'app.bsky.feed.post', 'text': 'AI 研究 <script>window.bad=true</script> #AI',
                       'createdAt': (datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat(),
                       'tags': ['AI', 'ai'], 'facets': [{'features': [{'$type': 'app.bsky.richtext.facet#tag', 'tag': '研究'}]}]},
            'likeCount': likes, 'repostCount': reposts, 'replyCount': replies}


def mpost(key, hours=1, likes=4):
    row = mastodon_post(key)
    row.update(created_at=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat(), favourites_count=likes,
               reblogs_count=2, replies_count=1, tags=[{'name': 'AI'}, {'name': 'ai'}])
    return row


def test_registration_ui_api_and_editing_no_network(app, client, monkeypatch):
    monkeypatch.setattr(research, 'request_json', lambda *a: pytest.fail('registration must not fetch'))
    _, _, read = authorization(app)
    _, _, write = authorization(app, 'write')
    body = {'source_type': 'bluesky', 'source_kind': 'topic', 'target': '人工知能', 'name': 'AI 調査', 'folder': '技術'}
    assert client.post('/api/v1/feeds', json=body, headers=read).status_code == 403
    result = client.post('/api/v1/feeds', json=body, headers=write)
    assert result.status_code == 201
    feed_id = result.json['data']['id']
    assert result.json['data']['window_hours'] == 24 and result.json['data']['poll_interval'] == 1800
    assert client.post('/api/v1/feeds', json=body, headers=write).status_code == 409
    assert client.post('/api/v1/feeds', json={**body, 'token': 'no-credentials'}, headers=write).status_code == 400
    assert client.post('/api/v1/feeds', json={**body, 'poll_interval': '1800'}, headers=write).status_code == 400
    assert client.post('/social-research', data=body).status_code == 400
    result = post(client, '/social-research', {'source_type': 'mastodon', 'name': 'セキュリティ', 'target': '#Security, AI',
                                            'instance_url': 'https://example.com', 'interval_minutes': '15'}, follow_redirects=True)
    assert result.status_code == 200 and 'SNS 調査を登録しました' in result.text
    assert 'まだ収集していません' in result.text
    assert client.get('/social-research').status_code == 200
    assert client.get('/api/v1/social-research').status_code == 401
    assert len(client.get('/api/v1/social-research?limit=1', headers=read).json['data']) == 1
    assert client.get('/api/v1/social-research?limit=1', headers=read).json['next_before_id']
    assert client.get('/api/v1/social-research/999', headers=read).status_code == 404
    assert client.patch(f'/api/v1/feeds/{feed_id}', headers=write, json={'name':'改名','window_hours':48,'poll_interval':900,'enabled':False}).status_code == 200
    for patch in ({'window_hours':0,'name':'bad'}, {'poll_interval':60}, {'poll_interval':None}, {'window_hours':True}, {'target':'other'}):
        assert client.patch(f'/api/v1/feeds/{feed_id}', headers=write, json=patch).status_code == 400
    with app.app_context():
        assert research.topic_report(feed_id)['topic']['title'] == '改名'
        assert research.topic_report(feed_id)['topic']['window_hours'] == 48


@pytest.mark.parametrize('changes', [
    {'source_type':'x'}, {'source_type':[]}, {'name':''}, {'name':'a\n'}, {'target':''}, {'target':None},
    {'poll_interval':60}, {'poll_interval':True}, {'window_hours':169}, {'window_hours':1.5}, {'folder':['bad']},
    {'instance_url':'https://other.example'}, {'source_type':'mastodon','instance_url':'https://127.0.0.1'},
    {'source_type':'mastodon','instance_url':'http://example.com'}, {'source_type':'mastodon','instance_url':'https://example.com/path'},
    {'source_type':'mastodon','instance_url':'https://example.com:8443'},
    {'source_type':'mastodon','instance_url':'https://example.com/?key=foo'},
    {'source_type':'mastodon','instance_url':'https://example.com','target':'one,two,three,four'},
    {'source_type':'mastodon','instance_url':'https://example.com','target':'a/b'},
])
def test_topic_input_validation(app, changes):
    values = {'source_type':'bluesky','target':'AI','name':'分野'}
    with app.app_context(), pytest.raises(ValueError):
        research.add_topic(**{**values, **changes})
    with app.app_context():
        assert not get_db().execute('SELECT 1 FROM feeds').fetchone()


def test_bluesky_window_rank_deduplication_evidence_and_last_good(app, client, monkeypatch):
    calls = []
    def request(url):
        calls.append(url)
        return {'posts':[bpost(), bpost('popular', likes=30), bpost('old', hours=25), bpost('future', hours=-1)]}, {}
    monkeypatch.setattr(research, 'request_json', request)
    with app.app_context():
        feed_id = research.add_topic('bluesky', 'AI lang:ja', name='AI')
        assert collection.refresh_feeds(feed_id) == (1,0)
        report = research.topic_report(feed_id)
        assert len(calls) == 2 and 'sort=top' in calls[0] and 'sort=latest' in calls[1]
        assert all(url.startswith(research.BLUESKY+'/xrpc/app.bsky.feed.searchPosts?') for url in calls)
        assert report['latest']['sample_count'] == report['latest']['new_count'] == 2
        assert report['results'][0]['score'] == 35
        assert report['latest']['hashtags'] == [{'tag':'ai','posts':2},{'tag':'研究','posts':2}]
        article_id = report['results'][0]['article_id']
        db = get_db()
        with db:
            db.execute('UPDATE articles SET is_read=1,is_starred=1 WHERE id=?', (article_id,))
        assert '&lt;script&gt;' in db.execute('SELECT content FROM articles WHERE id=?',(article_id,)).fetchone()[0]
        assert db.execute('SELECT count(*) FROM evidence').fetchone()[0] == 2
        first_run = report['latest']['id']
        monkeypatch.setattr(research, 'request_json', lambda *a: ({'posts':[bpost(likes=3), bpost('popular', likes=40)]}, {}))
        assert collection.refresh_feeds(feed_id) == (1,0)
        assert research.topic_report(feed_id)['latest']['new_count'] == 0
        assert research.topic_report(feed_id)['results'][0]['score'] == 45
        assert db.execute('SELECT score FROM social_results WHERE run_id=? AND rank=1', (first_run,)).fetchone()[0] == 35
        assert research.topic_report(feed_id)['results'][0]['is_starred'] == 1
        last_id = research.topic_report(feed_id)['latest']['id']
        def fail_second(url):
            if 'sort=latest' in url:
                raise SocialError('temporary')
            return {'posts':[bpost('uncommitted')]}, {}
        monkeypatch.setattr(research, 'request_json', fail_second)
        assert collection.refresh_feeds(feed_id) == (0,1)
        assert research.topic_report(feed_id)['latest']['id'] == last_id
        assert db.execute('SELECT count(*) FROM articles').fetchone()[0] == 2
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    _, _, read = authorization(app)
    result = client.get('/api/v1/articles?source_type=bluesky', headers=read)
    assert len(result.json['data']) == 2
    assert client.get(f'/api/v1/social-research/{feed_id}', headers=read).json['data']['latest']['id'] == last_id
    assert '前回成功時の結果を表示' in client.get(f'/social-research/{feed_id}').text


def test_mastodon_tag_samples_scope_and_private_boost_exclusion(app, monkeypatch):
    calls=[]
    private=mpost(3);private['visibility']='private'
    boost=mpost(4);boost['reblog']=mpost(10)
    def request(url):
        calls.append(url)
        return [mpost(1),mpost(2),private,boost,mpost(5,hours=48)], {}
    monkeypatch.setattr(research,'request_json',request)
    with app.app_context():
        feed_id=research.add_topic('mastodon','#AI,研究,ai','https://example.com',name='研究')
        assert collection.refresh_feeds(feed_id)==(1,0)
        assert len(calls)==2 and all('/api/v1/timelines/tag/' in url and url.endswith('?limit=40') for url in calls)
        report=research.topic_report(feed_id)
        assert report['latest']['sample_count']==2
        assert report['latest']['hashtags']==[{'tag':'ai','posts':2}]
        assert '<img' not in get_db().execute('SELECT content FROM articles LIMIT 1').fetchone()[0]


def test_mastodon_durable_pages_resume_after_failure(app, monkeypatch):
    from urllib.parse import parse_qs, urlsplit
    with app.app_context():
        feed_id=social.add_social('mastodon','account','alice','https://example.com')
        with get_db() as db:
            db.execute("UPDATE feeds SET provider_id='1',since_id='10',success_at='2020-01-01 00:00:00'")
    calls=[]
    fail=True
    def request(url):
        nonlocal fail
        params=parse_qs(urlsplit(url).query)
        assert params['since_id']==['10']
        cursor=params.get('max_id',[''])[0];calls.append(cursor)
        if cursor=='61' and fail:
            fail=False
            raise SocialError('temporary')
        values={'':range(100,60,-1),'61':range(60,20,-1),'21':range(20,10,-1)}
        return [mastodon_post(n) for n in values[cursor]],{}
    monkeypatch.setattr(social,'request_json',request)
    with app.app_context():
        assert collection.refresh_feeds(feed_id)==(0,1)
        row=get_db().execute('SELECT * FROM feeds').fetchone()
        assert row['since_id']=='10' and row['page_cursor']=='61' and row['pending_newest']=='100'
    restarted=create_app({'TESTING':True,'DATA_DIR':app.instance_path})
    with restarted.app_context():
        assert collection.refresh_feeds(feed_id)==(1,0)
        row=get_db().execute('SELECT * FROM feeds').fetchone()
        assert row['since_id']=='100' and row['page_cursor'] is None
        assert get_db().execute('SELECT count(*) FROM articles').fetchone()[0]==90
    assert calls==['','61','61','21']


@pytest.mark.parametrize('mutation', [
    {'uri':'at://evil/app.bsky.feed.post/a'}, {'author':{'did':'did:plc:another'}}, {'likeCount':True},
    {'likeCount':-1}, {'replyCount':'1'}, {'record':{'$type':'other','text':'unsafe'}}, {'record':None}
])
def test_untrusted_provider_rows_fail_atomically(app, monkeypatch, mutation):
    bad=bpost('bad');bad.update(mutation)
    monkeypatch.setattr(research,'request_json',lambda *a:({'posts':[bpost(),bad]},{}))
    with app.app_context():
        feed_id=research.add_topic('bluesky','AI',name='AI')
        assert collection.refresh_feeds(feed_id)==(0,1)
        assert not get_db().execute('SELECT 1 FROM articles').fetchone()
        assert not get_db().execute('SELECT 1 FROM social_runs').fetchone()


@pytest.mark.parametrize('response', [None, {}, {'posts':'bad'}, {'posts':[None]}, {'posts':[bpost()]*101}])
def test_response_limits(app, monkeypatch, response):
    monkeypatch.setattr(research,'request_json',lambda *a:(response,{}))
    with app.app_context():
        feed_id=research.add_topic('bluesky','AI',name='AI')
        assert collection.refresh_feeds(feed_id)==(0,1)


def test_cooldown_scheduling_pause_and_scoped_instances(app, client, monkeypatch):
    calls=[]
    def request(url):
        calls.append(url)
        raise SocialError('rate limit','2099-01-01 00:00:00')
    monkeypatch.setattr(research,'request_json',request)
    with app.app_context():
        first=research.add_topic('bluesky','AI',name='AI',poll_interval=900)
        second=research.add_topic('bluesky','security',name='Security')
        assert collection.refresh_feeds(due_only=True)==(0,1) and len(calls)==1
        assert collection.refresh_feeds(second)==(0,0)
        for origin in ('https://one.example','https://two.example'):
            research.add_topic('mastodon','AI',origin,name='AI')
        assert collection.refresh_feeds(due_only=True)==(0,2) and len(calls)==3
        db=get_db()
        with db:
            db.execute('DELETE FROM provider_cooldowns')
            db.execute('UPDATE feeds SET retry_at=NULL,checked_at=NULL')
            db.execute('UPDATE settings SET polling_enabled=0')
        assert collection.refresh_feeds(due_only=True)==(0,0)
        row=dict(db.execute('SELECT * FROM feeds WHERE id=?',(first,)).fetchone())
        row.update(checked_at='2026-10-21 00:00:00',poll_interval=None,failures=0)
        assert due_at(row,{'poll_interval':60},interval_override=60).strftime('%H:%M')=='00:15'
        with db:
            db.execute("UPDATE feeds SET retry_at='2099-01-01 00:00:00' WHERE id=?",(second,))
    _,_,write=authorization(app,'write')
    assert client.post(f'/api/v1/feeds/{second}/refresh',headers=write).status_code==429


def test_snapshot_retention_backup_restore_restart_and_delete(app, tmp_path, monkeypatch):
    monkeypatch.setattr(research,'request_json',lambda *a:({'posts':[bpost()]},{}))
    with app.app_context():
        feed_id=research.add_topic('bluesky','AI',name='AI')
        for _ in range(32):
            assert collection.refresh_feeds(feed_id)==(1,0)
        report=research.topic_report(feed_id)
        assert len(report['history'])==30 and get_db().execute('SELECT count(*) FROM social_results').fetchone()[0]==30
        get_db().execute('UPDATE articles SET is_starred=1');get_db().commit()
        backup_bundle(app.config['DATABASE'],tmp_path/'bundle')
    restored=tmp_path/'restored'/'feeds.sqlite3'
    restore_bundle(tmp_path/'bundle',restored)
    restarted=create_app({'TESTING':True,'DATA_DIR':str(restored.parent)})
    with restarted.app_context():
        assert research.topic_report(feed_id)['latest']['id']==report['latest']['id']
        assert collection.refresh_feeds(feed_id)==(1,0)
        assert research.topic_report(feed_id)['latest']['new_count']==0
        assert research.topic_report(feed_id)['results'][0]['is_starred']==1
        delete_subscription(feed_id)
        assert not get_db().execute('SELECT 1 FROM social_runs').fetchone()
        assert not get_db().execute('SELECT 1 FROM social_results').fetchone()
        assert not get_db().execute('PRAGMA foreign_key_check').fetchall()


def test_bundle_rejects_cross_topic_rankings_and_invalid_tag_summaries(app, tmp_path, monkeypatch):
    monkeypatch.setattr(research,'request_json',lambda *a:({'posts':[bpost()]},{}))
    with app.app_context():
        first=research.add_topic('bluesky','AI',name='AI')
        second=research.add_topic('bluesky','security',name='Security')
        assert collection.refresh_feeds()==(2,0)
        db=get_db()
        first_run=research.topic_report(first)['latest']['id']
        second_article=research.topic_report(second)['results'][0]['article_id']
        with db:
            db.execute('UPDATE social_results SET article_id=? WHERE run_id=?',(second_article,first_run))
        with pytest.raises(ValueError,match='参照'):
            backup_bundle(app.config['DATABASE'],tmp_path/'bad-references')
        with db:
            db.execute('DELETE FROM social_results WHERE run_id=?',(first_run,))
            db.execute('UPDATE social_runs SET hashtags=? WHERE id=?', ('[{"tag":"ai","posts":999}]',first_run))
        with pytest.raises(ValueError,match='タグ'):
            backup_bundle(app.config['DATABASE'],tmp_path/'bad-tags')


def test_v14_x_retirement_preserves_state_and_denies_network(tmp_path, monkeypatch):
    path=tmp_path/'feeds.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript(Path('tests/fixtures/v14_schema.sql').read_text())
        db.execute("INSERT INTO feeds(id,url,title,source_type,source_kind,target,created_at) VALUES(1,'https://x.com/alice','Legacy','x','account','alice','2026-01-01')")
        db.execute("INSERT INTO articles(feed_id,guid,title,content,search_text,published_at,is_read,is_starred) VALUES(1,'x:1','Saved','','','2026-01-01',1,1)")
    init_database(path);init_database(path)
    restarted=create_app({'TESTING':True,'DATA_DIR':str(tmp_path)})
    monkeypatch.setattr(social,'request_json',lambda *a:pytest.fail('X requests forbidden'))
    with restarted.app_context():
        assert not get_db().execute('SELECT enabled FROM feeds').fetchone()[0]
        assert get_db().execute('SELECT is_starred FROM articles').fetchone()[0]==1
        assert collection.refresh_feeds(1)==(0,0)
        with pytest.raises(ValueError):update_subscription(1,{'enabled':True})
        with pytest.raises(ValueError):social.add_social('x','account','alice')
        assert not get_db().execute('PRAGMA foreign_key_check').fetchall()
    client=restarted.test_client();_,_,write=authorization(restarted,'write')
    assert client.post('/api/v1/feeds/1/refresh',headers=write).status_code==410
    assert client.get('/api/v1/articles?source_type=x',headers=write).json['data'][0]['title']=='Saved'


@pytest.mark.browser
@browser_only
def test_desktop_mobile_topic_workflow(browser, live_reader, app, monkeypatch, tmp_path):
    monkeypatch.setattr(research,'request_json',lambda *a:({'posts':[bpost(),bpost('popular',likes=99)]},{}))
    with browser.new_context(viewport={'width':1440,'height':900}) as context:
        page=context.new_page();page.goto(live_reader+'/sources/new/sns')
        page.get_by_label('分野名',exact=True).fill('AI 研究')
        page.get_by_label('検索語／ハッシュタグ',exact=True).fill('AI lang:ja')
        page.get_by_label('フォルダー',exact=True).fill('調査')
        page.get_by_role('button',name='調査を登録',exact=True).click()
        page.get_by_role('button',name='今すぐ収集',exact=False).click()
        assert page.locator('.social-results li').count()==2
        assert 'スコア 104' in page.locator('.social-results li').first.inner_text()
        assert page.evaluate('window.bad') is None
        page.screenshot(path=str(tmp_path/'social-desktop.png'),full_page=True)
        detail=page.url
        page.get_by_role('link',name='この分野の設定 →',exact=True).click()
        page.get_by_label('収集間隔（分）',exact=True).fill('60')
        page.get_by_label('対象期間（時間）',exact=True).fill('48')
        page.get_by_role('button',name='設定を保存',exact=True).click()
        assert page.get_by_label('収集間隔（分）',exact=True).input_value() == '60'
        from playwright.sync_api import expect
        expect(page.locator('[data-editor-feedback]')).to_have_text('保存しました。')
        with page.expect_navigation():
            page.get_by_role('dialog').get_by_role('button',name='閉じる',exact=True).click()
        assert '60 分ごと／過去 48 時間' in page.locator('main').inner_text()
        page.get_by_text('記事一覧で読む →',exact=True).click()
        assert page.locator('.feed-folder[data-folder="調査"]').count()==1
    with browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True) as context:
        page=context.new_page();page.goto(detail)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        assert page.locator('.social-results li').count()==2
        page.screenshot(path=str(tmp_path/'social-mobile.png'),full_page=True)
