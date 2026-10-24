import base64
import io
import os
import socket
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from pathlib import Path

import pytest
from feedastrolabe import collection, create_app
from feedastrolabe import observation, page_broker, renderer
from feedastrolabe.db import connect, get_db, init_database
from feedastrolabe.page_protocol import ObservationError, MAX_MESSAGE, receive_message, send_message
from feedastrolabe.opml import export_opml
from test_reader import app, client, post, subscribe
from test_phase_two import authorization


def row(feed_id):
    return dict(get_db().execute('SELECT * FROM feeds WHERE id=?',(feed_id,)).fetchone())


def test_registration_ui_api_and_duplicate(app,client,monkeypatch):
    monkeypatch.setattr(observation,'capture_page',lambda *a:pytest.fail('Registration must not capture'))
    _,_,read=authorization(app)
    _,_,write=authorization(app,'write')
    payload={'source_type':'page','url':'https://example.com/news','selector':'#news','settle_ms':0,'poll_interval':120,'retention_days':30}
    assert client.post('/api/v1/feeds',json=payload,headers=read).status_code==403
    result=client.post('/api/v1/feeds',json=payload,headers=write)
    assert result.status_code==201
    feed=result.json['data'];feed_id=feed['id']
    assert feed['url']==payload['url'] and not feed['has_baseline'] and 'snapshot' not in feed
    assert client.post('/api/v1/feeds',json=payload,headers=write).status_code==409
    assert client.post('/api/v1/feeds',json={**payload,'selector':'main'},headers=write).status_code==201
    assert client.post('/api/v1/feeds',json={**payload,'token':'do-not-store'},headers=write).status_code==400
    assert client.post(f'/api/v1/feeds/{feed_id}/observe',headers=read).status_code==403
    assert client.post(f'/api/v1/feeds/{feed_id}/observe',headers=write).status_code==202
    assert client.post(f'/api/v1/feeds/{feed_id}/observe',headers=write).status_code==202
    assert client.post('/settings/pages',data=payload).status_code==400
    response=post(client,'/settings/pages',{'url':'https://example.org/page','selector':'h1'},follow_redirects=True)
    assert 'ページ観測を登録しました' in response.get_data(as_text=True)
    assert '観測セレクター' in response.get_data(as_text=True)
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM page_jobs').fetchone()[0]==1
        assert b'example.com/news' not in export_opml()


@pytest.mark.parametrize('url,selector,settle,interval,days',[
    ('https://127.0.0.1','main',0,60,1),('file:///tmp/a','main',0,60,1),('https://user:pass@example.com','main',0,60,1),
    ('https://example.com','',0,60,1),('https://example.com','x'*501,0,60,1),('https://example.com','main',10001,60,1),
    ('https://example.com','main',0,59,1),('https://example.com','main',0,60,366),('https://example.com','main\n',0,60,0),('https://example.com','main',True,60,1),('https://example.com','main',1.5,60,1)])
def test_invalid_observations(url,selector,settle,interval,days):
    with pytest.raises(ValueError):observation.page_values(url,selector,settle,interval,days)


def test_baseline_normalization_revert_state_and_escaping(app,client):
    with app.app_context():
        feed_id=observation.add_page('https://example.com','main')
        observation.save_observation(row(feed_id),'Ａ  test\n\n first')
        assert get_db().execute('SELECT count(*) FROM articles').fetchone()[0]==0
        observation.save_observation(row(feed_id),'A test\n first')
        assert get_db().execute('SELECT count(*) FROM articles').fetchone()[0]==0
        observation.save_observation(row(feed_id),'B <script>bad</script>')
        article=get_db().execute('SELECT * FROM articles').fetchone()
        assert '<script>' not in article['content'] and '&lt;script&gt;' in article['content']
        assert '変更前' in article['content'] and '変更後' in article['content']
        first=article['id']
    post(client,f'/articles/{first}/read',{'value':'1'})
    post(client,f'/articles/{first}/star',{'value':'1'})
    with app.app_context():
        observation.save_observation(row(feed_id),'A test\nfirst')
        observation.save_observation(row(feed_id),'A test\nfirst')
        rows=get_db().execute('SELECT * FROM articles ORDER BY id').fetchall()
        assert [r['guid'] for r in rows]==['page:1','page:2']
        assert rows[0]['is_read']==rows[0]['is_starred']==1
    _,_,headers=authorization(app)
    assert len(client.get('/api/v1/articles?source_type=page',headers=headers).json['data'])==2
    assert '変更 1' in client.get('/?feed='+str(feed_id)).get_data(as_text=True)


def test_retention_preserves_stars_other_sources_and_baseline(app,client):
    subscribe(client)
    with app.app_context():
        feed_id=observation.add_page('https://example.org','main',retention_days=1)
        for text in ('A','B','C'):observation.save_observation(row(feed_id),text)
        db=get_db()
        with db:
            db.execute("UPDATE articles SET published_at='2000-01-01 00:00:00'")
            db.execute("UPDATE articles SET is_starred=1 WHERE feed_id=? AND guid='page:1'",(feed_id,))
        observation.save_observation(row(feed_id),'C')
        assert db.execute('SELECT count(*) FROM articles WHERE feed_id=?',(feed_id,)).fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM articles WHERE feed_id<>?',(feed_id,)).fetchone()[0]==2
        assert row(feed_id)['snapshot']=='C'


def test_queue_worker_pause_failure_and_stale_result(app,client,monkeypatch,caplog):
    with app.app_context():
        feed_id=observation.add_page('https://example.org','main')
        db=get_db()
        with db:db.execute('UPDATE feeds SET enabled=0 WHERE id=?',(feed_id,))
        calls=[]
        monkeypatch.setattr(observation,'capture_page',lambda feed:(calls.append(feed['id']) or 'A'))
        assert observation.observe_pages()==(0,0)
        assert collection.refresh_feeds(feed_id)==(0,0)
        assert observation.observe_pages()==(0,0) and calls==[]
        with db:db.execute('UPDATE feeds SET enabled=1 WHERE id=?',(feed_id,))
        observation.queue_page(feed_id)
        assert observation.observe_pages()==(1,0) and calls==[feed_id]
        with db:db.execute('UPDATE settings SET polling_enabled=0')
        observation.queue_page(feed_id)
        monkeypatch.setattr(observation,'capture_page',lambda feed:(_ for _ in ()).throw(RuntimeError('do-not-log-this-secret')))
        assert observation.observe_pages()==(0,1)
        assert row(feed_id)['snapshot']=='A' and row(feed_id)['failures']==1
        assert 'do-not-log' not in caplog.text
        assert db.execute('SELECT count(*) FROM page_jobs').fetchone()[0]==0
        stale=row(feed_id)
        observation.edit_page(feed_id,'article',0,90)
        assert observation.save_observation(stale,'wrong') is False
        assert row(feed_id)['snapshot'] is None
        observation.save_observation(row(feed_id),'new baseline')
        assert row(feed_id)['snapshot']=='new baseline'
        observation.queue_page(feed_id)
        with db:db.execute('DELETE FROM feeds WHERE id=?',(feed_id,))
        assert db.execute('SELECT count(*) FROM page_jobs').fetchone()[0]==0
        assert observation.save_observation(stale,'deleted') is False


def test_v3_migration_foreign_keys_and_rollback(tmp_path):
    # Reconstruct exact v3 schema from committed source, before v4 rebuild.
    path=tmp_path/'v3.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript((Path(__file__).parent/'fixtures/v3_schema.sql').read_text())
    with connect(path) as db:
        db.execute("INSERT INTO feeds(id,url,title,created_at,source_type,target) VALUES(1,'https://x.com/alice','Alice','2026-01-01','x','alice')")
        db.execute("INSERT INTO articles(id,feed_id,guid,title,content,search_text,published_at,is_read,is_starred) VALUES(5,1,'x:20','Saved','safe','safe','2026-01-01',1,1)")
    init_database(path);init_database(path)
    with connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==19
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert tuple(db.execute('SELECT id,is_read,is_starred FROM articles').fetchone())==(5,1,1)
        db.execute("INSERT INTO feeds(url,title,created_at,source_type) VALUES('https://example.org#page','Page','2026-01-01','page')")
        db.execute('DELETE FROM feeds WHERE id=1')
        assert db.execute('SELECT count(*) FROM articles').fetchone()[0]==0


class Response:
    def __init__(self,status=200,headers=None,body=b'<h1>Safe</h1>'):
        self.status,self.headers,self.body=status,headers or {},body
    def getheader(self,name,default=None):return self.headers.get(name,default)
    def read1(self,size):
        data,self.body=self.body[:size],self.body[size:]
        return data


def fake_http(monkeypatch,response):
    calls=[]
    class HTTP:
        sock=None
        def __init__(self,*args):calls.append({'args':args})
        def request(self,method,path,headers):calls[-1].update(method=method,path=path,headers=headers)
        def getresponse(self):return response
        def close(self):calls[-1]['closed']=True
    monkeypatch.setattr(page_broker,'PinnedHTTP',HTTP)
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('1.1.1.1',443))])
    return calls


@pytest.mark.parametrize('url,method',[('https://evil.example/','GET'),('http://example.com/','GET'),('https://example.com/','POST'),('https://user:pass@example.com','GET')])
def test_broker_refuses_origin_method_credentials(monkeypatch,url,method):
    calls=fake_http(monkeypatch,Response())
    with pytest.raises(ObservationError):page_broker.FetchBudget('https://example.com').fetch(url,method)
    assert not calls


@pytest.mark.parametrize('response',[Response(302,{'Location':'http://127.0.0.1/'}),Response(403,body=b'secret'),Response(200,{'Content-Length':str(5*1024*1024+1)}),Response(200,{'Content-Encoding':'gzip'})])
def test_broker_limits_redirect_no_provider_errors(monkeypatch,response):
    calls=fake_http(monkeypatch,response)
    with pytest.raises(ObservationError) as error:page_broker.FetchBudget('https://example.com').fetch('https://example.com/')
    assert len(calls)==1 and calls[0]['closed'] and 'secret' not in str(error.value)


def test_broker_dns_pin_and_budget(monkeypatch):
    calls=fake_http(monkeypatch,Response(headers={'Content-Type':'text/html'}))
    budget=page_broker.FetchBudget('https://example.com')
    value=budget.fetch('https://example.com/')
    assert base64.b64decode(value['body'])==b'<h1>Safe</h1>'
    assert 'Authorization' not in calls[0]['headers'] and 'Cookie' not in calls[0]['headers']
    assert calls[0]['args'][2][-1]==('1.1.1.1',443)
    budget.requests=50
    with pytest.raises(ObservationError):budget.fetch('https://example.com/')
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(ObservationError):page_broker.FetchBudget('https://example.com').fetch('https://example.com/')
    assert len(calls)==1


def test_protocol_bounds_and_no_raw_errors():
    stream=io.BytesIO();send_message(stream,{'type':'result','text':'日本語'});stream.seek(0)
    assert receive_message(stream)['text']=='日本語'
    for data in (b'',b'[]\n',b'raw secret\n',b'x'*(MAX_MESSAGE+1)):
        with pytest.raises(ObservationError) as error:receive_message(io.BytesIO(data))
        assert 'secret' not in str(error.value)
    with pytest.raises(ObservationError):send_message(io.BytesIO(),{'text':'x'*MAX_MESSAGE})


@pytest.mark.browser
@pytest.mark.skipif(os.environ.get('FEEDASTROLABE_TEST_BROWSER')!='1',reason='Enable real Chromium tests explicitly')
def test_real_js_renderer_extracts_only_selected_text():
    seen=[]
    def fetch(url,method):
        seen.append((url,method))
        html=b'<h1>Ignore</h1><div id="target">Loading</div><script src="/app.js"></script><iframe src="https://evil.example/"></iframe>'
        body=b'setTimeout(()=>document.querySelector("#target").innerText="Rendered text",100)' if url.endswith('/app.js') else html
        return {'type':'response','body':base64.b64encode(body).decode(),'content_type':'text/javascript' if url.endswith('/app.js') else 'text/html'}
    result=renderer.render({'type':'capture','url':'https://example.com/','selector':'#target','settle_ms':300},fetch)
    assert result=='Rendered text'
    assert all('evil.example' not in url for url,_ in seen)
    with pytest.raises(ObservationError,match='CSS セレクター'):
        renderer.render({'type':'capture','url':'https://example.com/','selector':'[','settle_ms':0},fetch)


@pytest.mark.browser
@pytest.mark.skipif(os.environ.get('FEEDASTROLABE_TEST_BROWSER')!='1',reason='Enable real Chromium tests explicitly')
def test_real_ipc_renderer_roundtrip(app,monkeypatch,tmp_path):
    temporary=TemporaryDirectory(prefix='fa-ipc-',dir='/tmp')
    endpoint=Path(temporary.name)/'renderer.sock'
    process=subprocess.Popen([sys.executable,'-m','feedastrolabe.renderer','--socket',str(endpoint)],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        deadline=time.monotonic()+10
        while not endpoint.exists() and time.monotonic()<deadline:
            if process.poll() is not None:pytest.fail('Renderer startup failed')
            time.sleep(0.05)
        app.config['RENDER_SOCKET']=str(endpoint)
        monkeypatch.setattr(page_broker.FetchBudget,'fetch',lambda self,*args:{'type':'response','body':base64.b64encode(b'<main>IPC text</main>').decode(),'content_type':'text/html'})
        with app.app_context():
            feed_id=observation.add_page('https://example.com','main',settle_ms=0)
            assert observation.observe_pages()==(1,0)
            assert row(feed_id)['snapshot']=='IPC text'
    finally:
        if process.poll() is None:
            os.killpg(process.pid,15);process.wait(timeout=10)
        temporary.cleanup()


def test_selector_error_preserves_baseline(app,monkeypatch):
    with app.app_context():
        source=observation.add_page('https://example.com','main')
        observation.save_observation(row(source),'Known baseline')
        observation.queue_page(source)
        monkeypatch.setattr(observation,'capture_page',lambda feed:(_ for _ in ()).throw(ObservationError('selector')))
        assert observation.observe_pages()==(0,1)
        current=row(source)
        assert current['snapshot']=='Known baseline' and current['failures']==1
        assert '対象要素' in current['error']


def test_renderer_hard_timeout_kills_job_group(monkeypatch):
    import multiprocessing
    import signal
    from feedastrolabe.page_protocol import send_message
    def hanging_job(conn):
        os.setsid()
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
        with conn.makefile('rwb') as stream:
            send_message(stream,{'type':'started','pid':child.pid})
            time.sleep(60)
    monkeypatch.setattr(renderer,'handle_connection',hanging_job)
    with TemporaryDirectory(prefix='fa-timeout-',dir='/tmp') as directory:
        endpoint=str(Path(directory)/'socket')
        server=multiprocessing.get_context('fork').Process(target=renderer.serve,args=(endpoint,0.3))
        server.start()
        try:
            deadline=time.monotonic()+5
            while not Path(endpoint).exists() and time.monotonic()<deadline:time.sleep(0.01)
            with socket.socket(socket.AF_UNIX) as conn:
                conn.settimeout(5);conn.connect(endpoint)
                with conn.makefile('rwb') as stream:
                    started=receive_message(stream)
                    assert receive_message(stream)=={'type':'error','code':'timeout'}
            time.sleep(0.1)
            state=subprocess.run(['ps','-o','stat=','-p',str(started['pid'])],capture_output=True,text=True).stdout.strip()
            assert not state or state.startswith('Z')
        finally:
            server.terminate();server.join(5)


def test_restore_preserves_page_state_and_refuses_active_observer(app, tmp_path):
    from feedastrolabe.evidence_backup import backup_bundle as backup, restore_bundle as restore
    from feedastrolabe.db import connect
    import fcntl
    with app.app_context():
        source = observation.add_page('https://example.com/restore', 'main')
        feed = get_db().execute('SELECT * FROM feeds WHERE id=?', (source,)).fetchone()
        observation.save_observation(feed, 'Baseline')
        observation.queue_page(source)
        snapshot = tmp_path / 'v4-backup.sqlite3'
        backup(Path(app.instance_path) / 'feeds.sqlite3', snapshot)
    destination = tmp_path / 'restored' / 'feeds.sqlite3'
    destination.parent.mkdir()
    with (destination.parent / 'observer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            restore(snapshot, destination)
        assert not destination.exists()
    restore(snapshot, destination)
    with connect(destination) as db:
        assert db.execute('SELECT snapshot FROM feeds WHERE id=?', (source,)).fetchone()[0] == 'Baseline'
        assert db.execute('SELECT feed_id FROM page_jobs').fetchone()[0] == source
        assert db.execute('PRAGMA user_version').fetchone()[0] == 19
