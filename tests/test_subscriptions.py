from datetime import datetime, timedelta, timezone

import pytest

from feedastrolabe import collection, observation
from feedastrolabe.db import get_db
from feedastrolabe.social import add_social
from feedastrolabe.subscriptions import update_subscription, delete_subscription
from test_reader import app, client, post, subscribe, RSS, META
from test_phase_two import authorization


def test_rss_patch_repairs_url_preserving_state(app, client, monkeypatch):
    subscribe(client)
    post(client, '/articles/1/read', {'value': '1'})
    post(client, '/articles/1/star', {'value': '1'})
    _, _, headers = authorization(app, 'write')
    response = client.patch('/api/v1/feeds/1', headers=headers, json={'url': 'https://example.com/new-feed', 'folder': 'New', 'enabled': False, 'poll_interval': None})
    assert response.status_code == 200
    feed = response.json['data']
    assert feed['url'] == 'https://example.com/new-feed' and feed['folder'] == 'New'
    assert feed['etag'] is None and feed['modified'] is None and feed['checked_at'] is None
    seen = []
    def fetch(url, etag, modified):
        seen.append((url, etag, modified))
        return RSS, META
    monkeypatch.setattr(collection, 'fetch', fetch)
    result = client.post('/api/v1/feeds/1/refresh', headers=headers)
    assert result.status_code == 200 and result.json['data']['succeeded'] == 1
    assert seen == [('https://example.com/new-feed', None, None)]
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM articles').fetchone()[0] == 2
        assert tuple(get_db().execute('SELECT id,is_read,is_starred FROM articles WHERE id=1').fetchone()) == (1, 1, 1)


@pytest.mark.parametrize('patch', [
    {}, [], {'enabled': 1}, {'enabled': 'false'}, {'folder': None}, {'folder': 'x'*81},
    {'folder': 'bad\nname'}, {'folder':'Changed','poll_interval':59}, {'poll_interval':True},
    {'poll_interval':60.5}, {'poll_interval':'120'}, {'url':'http://127.0.0.1/feed'}, {'url':'http://localhost/feed'},
    {'url':'https://user:pass@example.com/feed'}, {'url':None}, {'selector':'h1'}, {'source_type':'page'}, {'api_key':'unsupported'},
])
def test_invalid_patches_are_atomic(app, client, patch):
    subscribe(client)
    _, _, headers = authorization(app, 'write')
    with app.app_context():
        before = dict(get_db().execute('SELECT * FROM feeds WHERE id=1').fetchone())
    assert client.patch('/api/v1/feeds/1', headers=headers, json=patch).status_code == 400
    with app.app_context():
        assert dict(get_db().execute('SELECT * FROM feeds WHERE id=1').fetchone()) == before


def test_duplicate_missing_scope_and_csrf(app, client):
    subscribe(client)
    subscribe(client, 'https://example.com/other')
    _, _, read = authorization(app)
    _, _, write = authorization(app, 'write')
    for method, path, body in [('patch','/api/v1/feeds/1', {'folder':'New'}),('delete','/api/v1/feeds/1',None),('post','/api/v1/feeds/1/refresh',None)]:
        assert getattr(client,method)(path,headers=read,json=body).status_code == 403
        assert getattr(client,method)(path,json=body).status_code == 401
    assert client.patch('/api/v1/feeds/1',headers=write,json={'folder':'New','url':'https://example.com/other'}).status_code == 409
    for method in ('patch','delete'):
        assert getattr(client,method)('/api/v1/feeds/999',headers=write,json={'folder':'New'}).status_code == 404
    assert client.post('/api/v1/feeds/999/refresh',headers=write).status_code == 404
    assert client.post('/settings/feeds/1/url',data={'url':'https://example.com/new'}).status_code == 400
    with app.app_context():
        assert get_db().execute('SELECT folder FROM feeds WHERE id=1').fetchone()[0] == 'Technology'


def test_page_edits_reject_stale_capture_preserve_history_and_queue(app, client):
    with app.app_context():
        source=observation.add_page('https://example.com/page', 'h1')
        feed=dict(get_db().execute('SELECT * FROM feeds WHERE id=?',(source,)).fetchone())
        observation.save_observation(feed, 'A')
        observation.save_observation(feed, 'B')
        with get_db() as db:db.execute('UPDATE articles SET is_read=1,is_starred=1')
    _, _, headers=authorization(app,'write')
    path=f'/api/v1/feeds/{source}'
    assert client.patch(path,headers=headers,json={'folder':'Pages','retention_days':30,'enabled':False}).status_code==200
    with app.app_context():
        db=get_db();current=dict(db.execute('SELECT * FROM feeds WHERE id=?',(source,)).fetchone())
        assert current['snapshot']=='B'
        assert not observation.save_observation(feed,'Stale')
    for _ in range(2):
        assert client.post(path+'/refresh',headers=headers).status_code==202
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM page_jobs').fetchone()[0]==1
    result=client.patch(path,headers=headers,json={'url':'https://example.com/repaired','selector':'main','settle_ms':0})
    assert result.status_code==200 and not result.json['data']['has_baseline']
    with app.app_context():
        db=get_db();new=dict(db.execute('SELECT * FROM feeds WHERE id=?',(source,)).fetchone())
        assert not observation.save_observation(current,'Old target')
        assert new['observation_seq']==1
        assert tuple(db.execute('SELECT guid,is_read,is_starred FROM articles').fetchone())==('page:1',1,1)
        observation.save_observation(new,'C')
        observation.save_observation(new,'D')
        assert db.execute('SELECT count(*) FROM articles').fetchone()[0]==2
    assert client.delete(path,headers=headers).status_code==204
    with app.app_context():
        db=get_db()
        assert not db.execute('SELECT * FROM articles').fetchall()
        assert not db.execute('SELECT * FROM page_jobs').fetchall()
        assert not observation.save_observation(new,'Deleted')
        assert not observation.queue_page(source)


def test_page_duplicates_and_invalid_atomic_edit(app, client):
    with app.app_context():
        one=observation.add_page('https://example.com/page','h1')
        observation.add_page('https://example.com/page','main')
    _, _, headers=authorization(app,'write')
    assert client.patch(f'/api/v1/feeds/{one}',headers=headers,json={'selector':'main','folder':'Wrong'}).status_code==409
    assert client.patch(f'/api/v1/feeds/{one}',headers=headers,json={'retention_days':0,'folder':'Wrong'}).status_code==400
    with app.app_context():
        assert get_db().execute('SELECT folder FROM feeds WHERE id=?',(one,)).fetchone()[0]==''


def test_collection_lock_blocks_ui_and_api_mutations(app, client):
    subscribe(client)
    _, _, headers=authorization(app,'write')
    with app.app_context(), collection.refresh_lock():
        assert client.patch('/api/v1/feeds/1',headers=headers,json={'folder':'Wrong'}).status_code==409
        assert client.delete('/api/v1/feeds/1',headers=headers).status_code==409
        assert client.post('/api/v1/feeds/1/refresh',headers=headers).status_code==409
        result=post(client,'/feeds/1/delete',follow_redirects=True)
        assert '更新処理が実行中' in result.get_data(as_text=True)
        assert get_db().execute('SELECT count(*) FROM feeds').fetchone()[0]==1


def test_sns_identity_and_provider_cooldown(app, client, monkeypatch):
    with app.app_context():
        source=add_social('mastodon','account','alice','https://mastodon.social')
        retry=(datetime.now(timezone.utc)+timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
        with get_db() as db:db.execute('UPDATE feeds SET retry_at=? WHERE id=?',(retry,source))
    _, _, headers=authorization(app,'write')
    assert client.patch(f'/api/v1/feeds/{source}',headers=headers,json={'folder':'Social','enabled':False,'poll_interval':120}).status_code==200
    assert client.patch(f'/api/v1/feeds/{source}',headers=headers,json={'url':'https://example.com/feed'}).status_code==400
    import importlib
    monkeypatch.setattr(importlib.import_module('feedastrolabe.api'), 'refresh_feeds',lambda *a:pytest.fail('must not refresh during cooldown'))
    result=client.post(f'/api/v1/feeds/{source}/refresh',headers=headers)
    assert result.status_code==429 and int(result.headers['Retry-After'])>0


def test_ui_url_repair_schedule_and_missing(app, client):
    subscribe(client)
    result=post(client,'/settings/feeds/1/url',{'url':'https://example.com/new'},follow_redirects=True)
    assert '取得 URL を保存' in result.get_data(as_text=True)
    assert '取得 URL を編集' in result.get_data(as_text=True)
    assert post(client,'/settings/feeds/999/url',{'url':'https://example.com/new'}).status_code==404
    assert post(client,'/settings/feeds/999',{'poll_interval':'120'}).status_code==404
    with app.app_context():
        assert get_db().execute('SELECT url FROM feeds').fetchone()[0]=='https://example.com/new'
