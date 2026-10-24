from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest

from feedastrolabe import collection, create_app, research as r
from feedastrolabe import social_ai as ai, openrouter_http as http
from feedastrolabe import social_research as social
from feedastrolabe.db import get_db, connect, init_database
from feedastrolabe.evidence_backup import backup_bundle, restore_bundle
from test_reader import app, client, post
from test_social_research import bpost
from test_phase_two import authorization
from test_feed_disclosure import browser, browser_only, live_reader


def setup_ai(app, monkeypatch, automatic=False):
    app.config['OPENROUTER_API_KEY']='synthetic-'+('k'*32)
    monkeypatch.setattr(social,'request_json',lambda *args:({'posts':[bpost('one'),bpost('two',likes=99)]},{}))
    with app.app_context():
        feed_id=social.add_topic('bluesky','AI',name='AI調査')
        assert collection.refresh_feeds(feed_id)==(1,0)
        ai.configure({'expected_revision':1,'model':'vendor/fixture-model','enabled':True})
        if automatic:
            ai.topic_configure(feed_id,{'expected_revision':1,'ai_enabled':True,'ai_criteria':'研究の新規性と実用上の影響'})
        return feed_id


def answer(article_id, title='重要な研究の公開', importance=90):
    return {'title':title,'summary':'具体的な研究成果が公開されたという投稿です。','importance':importance,
            'reason':'分野に関連した新しい成果で、影響範囲を検討する価値があります。',
            'uncertainty':'投稿内容は独立に検証していません。','article_ids':[article_id]}


def model(app, monkeypatch, callback=None):
    calls=[]
    def generate(cfg,wire,bound):
        calls.append(wire)
        data=json.loads(json.loads(wire)['messages'][1]['content'])
        topics=[answer(data['sources'][0]['article_id'])]
        if callback:topics=callback(data)
        return json.dumps({'topics':topics},ensure_ascii=False),{'prompt_tokens':100,'completion_tokens':150,'cost_micro_usd':1000},{'requested_model':cfg['model'],'response_model':cfg['model'],'generation_id':'gen-fixture','adapter':'fixture'}
    monkeypatch.setattr(ai,'generate',generate)
    return calls


def test_exact_snapshot_semantics_results_idempotence_and_immutable_articles(app,client,monkeypatch):
    feed_id=setup_ai(app,monkeypatch);calls=model(app,monkeypatch)
    with app.app_context():
        before=[tuple(row) for row in get_db().execute('SELECT * FROM articles')]
        job=ai.enqueue(feed_id)
        assert ai.enqueue(feed_id)==job and calls==[]
        queued=ai.detail(job);wire=json.loads(queued['input']);data=json.loads(wire['messages'][1]['content'])
        assert wire['provider']=={'allow_fallbacks':False,'data_collection':'deny','max_price':{'prompt':1.0,'completion':3.0,'request':0},'require_parameters':True}
        assert wire['response_format']['type']=='json_schema' and wire['stream'] is False and 'tools' not in wire
        assert len(data['sources'])==2 and all('content' not in s for s in data['sources'])
        assert '信頼できないデータ' in queued['input'] and ai.digest(queued['input'])==queued['input_hash']
        assert ai.process()=={'processed':1}
        result=ai.detail(job)
        assert result['status']=='success' and result['result']['topics'][0]['importance']==90
        assert result['actual_cost']==1000 and calls==[queued['input']]
        assert ai.enqueue(feed_id)==job and ai.process()=={'processed':0}
        assert [tuple(row) for row in get_db().execute('SELECT * FROM articles')]==before
        assert ai.configuration()['today']['calls']==1
    html=client.get(f'/social-research/{feed_id}').text
    assert '重要な研究の公開' in html and 'AIによる未検証の評価' in html


@pytest.mark.parametrize('changes', [
    {'model':'https://evil.example'}, {'model':'vendor/model:online'}, {'model':'openrouter/auto'}, {'model':None},
    {'max_output_tokens':True}, {'daily_calls':0}, {'input_rate':-1}, {'output_rate':1.2},
    {'max_cost':2000000}, {'daily_cost':0}, {'enabled':'true'}, {'api_key':'never-store'}
])
def test_settings_validation_is_atomic(app,monkeypatch,changes):
    setup_ai(app,monkeypatch)
    with app.app_context():
        before=ai.configuration()
        with pytest.raises(ValueError):ai.configure({'expected_revision':before['revision'],**changes})
        assert ai.configuration()==before
        with pytest.raises(r.ResearchConflict):ai.configure({'expected_revision':1,'enabled':False})


def test_disabled_unconfigured_and_empty_input_never_generate(app,monkeypatch):
    monkeypatch.setattr(ai,'generate',lambda *a:pytest.fail('No paid request'))
    with app.app_context():
        with pytest.raises(ValueError):ai.configure({'expected_revision':1,'enabled':True,'model':'vendor/model'})
        feed_id=social.add_topic('bluesky','AI',name='AI')
        with pytest.raises(r.ResearchConflict):ai.enqueue(feed_id)
        app.config['OPENROUTER_API_KEY']='synthetic-'+('k'*32)
        ai.configure({'expected_revision':1,'model':'vendor/model','enabled':True})
        with pytest.raises(ValueError,match='先に'):ai.enqueue(feed_id)
        assert ai.schedule()==0


def test_public_scope_filters_and_dispatch_rechecks_private_associations(app,monkeypatch):
    feed_id=setup_ai(app,monkeypatch)
    monkeypatch.setattr(ai,'generate',lambda *args:pytest.fail('Private source must not send'))
    with app.app_context():
        db=get_db();ids=[row['id'] for row in db.execute('SELECT id FROM articles ORDER BY id')]
        workspace=r.create_workspace({'title':'Private notes','classification':'restricted'})
        r.associate('workspace',workspace,'article',ids[0])
        job=ai.enqueue(feed_id)
        assert [s['article_id'] for s in ai.detail(job)['sources']]==[ids[1]]
        r.associate('workspace',workspace,'article',ids[1])
        assert ai.process()=={'processed':1}
        assert ai.detail(job)['error']=='openrouter-source-policy-changed'
        assert ai.configuration()['today']['calls']==0
        with pytest.raises(ValueError,match='認証値'):
            ai.topic_configure(feed_id,{'expected_revision':1,'ai_criteria':'api_key='+('x'*16)})
        ai.topic_configure(feed_id,{'expected_revision':1,'ai_criteria':'公開情報の重要度'})
        with pytest.raises(ValueError,match='公開記事'):
            ai.enqueue(feed_id)


@pytest.mark.parametrize('relationship', ['feed','evidence','quotation','note'])
def test_private_case_relationships_are_excluded(app,monkeypatch,relationship):
    feed_id=setup_ai(app,monkeypatch)
    from feedastrolabe import evidence as e
    with app.app_context():
        db=get_db();article_id=db.execute('SELECT id FROM articles LIMIT 1').fetchone()[0]
        evidence_id=db.execute('SELECT id FROM evidence WHERE article_id=?',(article_id,)).fetchone()[0]
        workspace=r.create_workspace({'title':'Private','classification':'internal'})
        if relationship=='feed':r.associate('workspace',workspace,'feed',feed_id)
        elif relationship=='evidence':e.pin('workspace',workspace,evidence_id)
        elif relationship=='note':
            note=r.create_note(workspace,{'title':'Private note'});e.pin('note',note,evidence_id)
        else:
            e.pin('workspace',workspace,evidence_id)
            text=e.find(evidence_id)['text'];e.quotation(workspace,{'evidence_id':evidence_id,'start':0,'end':2,'quote':text[:2]})
        assert ai.public_source(article_id,db) is False


def test_empty_sample_secret_exclusion_and_bounded_input(app,monkeypatch):
    feed_id=setup_ai(app,monkeypatch)
    with app.app_context():
        db=get_db()
        with db:db.execute('UPDATE articles SET search_text=?',('Bearer '+('x'*40),))
        with pytest.raises(ValueError,match='公開記事'):ai.enqueue(feed_id)
        with db:db.execute('UPDATE articles SET search_text=?',('正常な日本語の資料。'*10000,))
        job=ai.enqueue(feed_id)
        detail=ai.detail(job)
        assert len(detail['input'].encode())<=http.MAX_INPUT
        assert all(len(s['text'])<=400 for s in detail['sources'])


@pytest.mark.parametrize('mutation', [
    {'article_ids':[999999]}, {'article_ids':[True]}, {'article_ids':[]}, {'importance':True},
    {'importance':101}, {'summary':''}, {'reason':['bad']}, {'extra':'unsupported'}
])
def test_generated_topic_validation(app,monkeypatch,mutation):
    feed_id=setup_ai(app,monkeypatch)
    with app.app_context():
        job=ai.enqueue(feed_id);sources=ai.detail(job)['sources']
        topic=answer(sources[0]['article_id']);topic.update(mutation)
        with pytest.raises(ValueError):ai.output(json.dumps({'topics':[topic]}),sources)


def test_invalid_generation_preserves_last_good_and_renders_escaped_text(app,client,monkeypatch):
    feed_id=setup_ai(app,monkeypatch)
    calls=model(app,monkeypatch,lambda data:[answer(data['sources'][0]['article_id'],'<script>window.bad=true</script>')])
    with app.app_context():
        first=ai.enqueue(feed_id);ai.process()
        assert ai.detail(first)['status']=='success'
        assert collection.refresh_feeds(feed_id)==(1,0)
        model(app,monkeypatch,lambda data:[answer(999999)])
        second=ai.enqueue(feed_id);ai.process()
        assert ai.detail(second)['status']=='failed'
        assert ai.report(feed_id)['success']['id']==first
    text=client.get(f'/social-research/{feed_id}').text
    assert '前回成功時の抽出結果' in text and '<script>window.bad=true</script>' not in text
    assert '&lt;script&gt;window.bad=true&lt;/script&gt;' in text


def test_auto_worker_pause_and_daily_budget(app,monkeypatch):
    feed_id=setup_ai(app,monkeypatch,automatic=True);calls=model(app,monkeypatch)
    with app.app_context():
        ai.configure({'expected_revision':2,'daily_calls':1})
        assert ai.schedule()==1 and ai.schedule()==0
        assert ai.process()=={'processed':1} and len(calls)==1
        assert collection.refresh_feeds(feed_id)==(1,0)
        assert ai.schedule()==1
        ai.process()
        assert ai.report(feed_id)['latest']['error']=='openrouter-daily-budget' and len(calls)==1
        with get_db() as db:db.execute('UPDATE settings SET polling_enabled=0')
        assert ai.schedule()==0
        assert collection.refresh_feeds(feed_id)==(1,0)
        assert ai.schedule()==0
    result=app.test_cli_runner().invoke(args=['worker','--once'])
    assert result.exit_code==0,result.output


def test_queued_pause_revision_and_cooldown_no_automatic_retry(app,monkeypatch):
    feed_id=setup_ai(app,monkeypatch,automatic=True)
    with app.app_context():
        job=ai.enqueue(feed_id,automatic=True)
        ai.topic_configure(feed_id,{'expected_revision':2,'ai_enabled':False})
        monkeypatch.setattr(ai,'generate',lambda *a:pytest.fail('Changed settings'))
        ai.process();assert ai.detail(job)['error']=='openrouter-settings-changed'
        calls=[]
        def limited(*args):calls.append(1);raise http.RouterError('openrouter-rate-limited','2099-01-01 00:00:00')
        monkeypatch.setattr(ai,'generate',limited)
        new=ai.enqueue(feed_id);ai.process()
        assert ai.detail(new)['error']=='openrouter-rate-limited'
        assert ai.configuration()['cooldown_until']=='2099-01-01 00:00:00'
        assert ai.process()=={'processed':0} and calls==[1]
        with pytest.raises(r.ResearchConflict):ai.enqueue(feed_id)


def test_interrupted_running_is_not_retried_and_budget_stays_reserved(app,monkeypatch):
    feed_id=setup_ai(app,monkeypatch)
    with app.app_context():
        job=ai.enqueue(feed_id)
        with get_db() as db:
            db.execute("UPDATE social_ai_jobs SET status='running' WHERE id=?",(job,))
            db.execute("INSERT INTO social_ai_budget VALUES('2026-10-21',1,10000)")
        monkeypatch.setattr(ai,'generate',lambda *args:pytest.fail('Do not retry'))
        assert ai.process()=={'processed':0}
        assert ai.detail(job)['error']=='openrouter-interrupted-no-retry'
        assert ai.enqueue(feed_id)==job
        assert get_db().execute('SELECT reserved_cost FROM social_ai_budget').fetchone()[0]==10000


def test_api_scopes_csrf_no_get_dispatch_and_config_revisions(app,client,monkeypatch):
    feed_id=setup_ai(app,monkeypatch)
    read=authorization(app,'read')[2];write=authorization(app,'write')[2]
    config='/api/v1/social-research/ai/config'
    assert client.get(config).status_code==401
    assert client.patch(config,json={'expected_revision':2,'daily_calls':10},headers=read).status_code==403
    assert client.patch(config,json={'expected_revision':1,'daily_calls':10},headers=write).status_code==409
    assert client.patch(config,json={'expected_revision':2,'daily_calls':10},headers=write).status_code==200
    assert 'synthetic-' not in client.get(config,headers=read).text
    jobs=f'/api/v1/social-research/{feed_id}/ai/jobs'
    assert client.post(jobs,json={},headers=read).status_code==403
    assert client.post(jobs,json={'model':'other/model'},headers=write).status_code==400
    result=client.post(jobs,json={},headers=write);assert result.status_code==202,result.json
    job=result.json['data']['id']
    assert client.get(f'/api/v1/social-research/ai/jobs/{job}',headers=read).status_code==200
    assert client.get('/api/v1/social-research/ai/jobs/99999',headers=read).status_code==404
    assert client.post(f'/social-research/{feed_id}/ai/jobs').status_code==400
    assert client.post('/social-research/ai/config').status_code==400
    with app.app_context():assert ai.detail(job)['status']=='queued'


def test_v15_upgrade_and_bundle_restore_disables_paid_dispatch(app,tmp_path,monkeypatch):
    source=tmp_path/'old.sqlite3'
    with sqlite3.connect(source) as db:
        db.executescript(Path('tests/fixtures/v15_schema.sql').read_text())
        db.execute("INSERT INTO feeds(id,url,title,created_at,source_type,source_kind,target,instance_url,poll_interval) VALUES(1,'social-topic:fixture','AI','2026-01-01','bluesky','topic','AI','https://api.bsky.app',1800)")
        db.execute('INSERT INTO social_topics VALUES(1,24)')
    init_database(source);init_database(source)
    with connect(source) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==18
        assert db.execute('SELECT enabled FROM social_ai_config').fetchone()[0]==0
        assert db.execute('SELECT ai_enabled FROM social_topics').fetchone()[0]==0
    feed_id=setup_ai(app,monkeypatch,automatic=True);model(app,monkeypatch)
    with app.app_context():
        job=ai.enqueue(feed_id);ai.process()
        assert collection.refresh_feeds(feed_id)==(1,0)
        pending=ai.enqueue(feed_id)
        backup_bundle(app.config['DATABASE'],tmp_path/'bundle')
    restored=tmp_path/'restored'/'feeds.sqlite3';restore_bundle(tmp_path/'bundle',restored)
    restarted=create_app({'TESTING':True,'DATA_DIR':str(restored.parent)})
    with restarted.app_context():
        assert ai.detail(job)['status']=='success'
        assert ai.detail(pending)['error']=='openrouter-restored-no-retry'
        assert ai.configuration()['enabled'] is False
        assert not get_db().execute('SELECT ai_enabled FROM social_topics').fetchone()[0]
        assert ai.schedule()==0 and ai.process()=={'processed':0}
        assert not get_db().execute('PRAGMA foreign_key_check').fetchall()


class Response:
    def __init__(self,status=200,body=b'{}',headers=None):self.status,self.body,self.headers=status,body,headers or {}
    def getheader(self,name,default=None):return self.headers.get(name,default)
    def getheaders(self):return list(self.headers.items())
    def read1(self,size):value,self.body=self.body[:size],self.body[size:];return value


def transport(app,monkeypatch,response):
    calls=[];app.config['OPENROUTER_API_KEY']='synthetic-'+('k'*32)
    class Connection:
        sock=None
        def __init__(self,*args):calls.append({'args':args})
        def request(self,method,path,body,headers):calls[-1].update(method=method,path=path,body=body,headers=headers)
        def getresponse(self):return response
        def close(self):calls[-1]['closed']=True
    monkeypatch.setattr(http,'PinnedHTTP',Connection);monkeypatch.setattr(http,'public_address',lambda *args:'1.1.1.1')
    return calls


@pytest.mark.parametrize('status,headers,body', [(302,{},b'secret-body'),(401,{},b'secret-body'),(402,{},b'secret-body'),
    (200,{'Content-Encoding':'gzip'},b''),(200,{'Content-Length':'1048577'},b''),(200,{},b'{"x":1,"x":2}'),(200,{},b'{"x":NaN}')])
def test_fixed_transport_safe_errors_no_retry(app,monkeypatch,status,headers,body):
    calls=transport(app,monkeypatch,Response(status,body,headers))
    with app.app_context(),pytest.raises(http.RouterError) as error:http.request('{}')
    assert len(calls)==1 and calls[0]['args'][:2]==('openrouter.ai',443)
    assert calls[0]['path']=='/api/v1/chat/completions' and calls[0]['method']=='POST' and calls[0]['closed']
    assert 'secret-body' not in str(error.value) and 'synthetic-' not in str(error.value)


def test_rate_limit_and_response_validation(app,monkeypatch):
    transport(app,monkeypatch,Response(429,b'secret-body',{'Retry-After':'3600'}))
    with app.app_context(),pytest.raises(http.RouterError) as error:http.request('{}')
    assert error.value.retry_at
    base={'id':'gen-fixture','model':'vendor/model','choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'{"topics":[]}'}}],
          'usage':{'prompt_tokens':10,'completion_tokens':20,'cost':0.001}}
    cfg={'model':'vendor/model','max_output_tokens':100}
    for change in ('tools','tokens','truncated','cost','model'):
        value=deepcopy(base)
        if change=='tools':value['choices'][0]['message']['tool_calls']=[{}]
        if change=='tokens':value['usage']['completion_tokens']=101
        if change=='truncated':value['choices'][0]['finish_reason']='length'
        if change=='cost':value['usage']['cost']=None
        if change=='model':value['model']='other/model'
        monkeypatch.setattr(http,'request',lambda *args,value=value:value)
        with pytest.raises(http.RouterError):http.generate(cfg,'{}',100)


def test_complete_transport_to_important_topics_and_cost_audit(app,monkeypatch):
    feed_id=setup_ai(app,monkeypatch)
    with app.app_context():
        job=ai.enqueue(feed_id);queued=ai.detail(job)
        article_id=queued['sources'][0]['article_id']
        data={'id':'gen-valid-fixture','model':'vendor/fixture-model',
              'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps({'topics':[answer(article_id)]})}}],
              'usage':{'prompt_tokens':100,'completion_tokens':100,'cost':0.001}}
        calls=transport(app,monkeypatch,Response(body=json.dumps(data).encode()))
        assert ai.process()=={'processed':1}
        assert ai.detail(job)['status']=='success'
        assert calls[0]['body']==queued['input'].encode()
        assert calls[0]['headers']['Authorization']=='Bearer '+app.config['OPENROUTER_API_KEY']
        assert ai.detail(job)['usage']['cost_micro_usd']==1000


def test_reported_cost_over_reservation_stays_charged_to_budget(app,monkeypatch):
    feed_id=setup_ai(app,monkeypatch)
    with app.app_context():
        job=ai.enqueue(feed_id);queued=ai.detail(job)
        def expensive(*args):
            return '{"topics":[]}',{'prompt_tokens':100,'completion_tokens':100,'cost_micro_usd':queued['reserved_cost']+1000},{'response_model':'vendor/fixture-model'}
        monkeypatch.setattr(ai,'generate',expensive)
        ai.process()
        assert ai.detail(job)['error']=='openrouter-cost-over-reservation'
        assert ai.configuration()['today']['reserved_cost']==queued['reserved_cost']+1000


def test_corrupt_snapshots_are_rejected_before_dispatch_and_backup(app,tmp_path,monkeypatch):
    feed_id=setup_ai(app,monkeypatch)
    with app.app_context():
        job=ai.enqueue(feed_id)
        with get_db() as db:
            db.execute("UPDATE social_ai_jobs SET input_hash=? WHERE id=?",('f'*64,job))
        monkeypatch.setattr(ai,'generate',lambda *args:pytest.fail('Corrupted snapshot'))
        ai.process()
        assert ai.detail(job)['error']=='openrouter-snapshot-invalid'
        assert ai.configuration()['today']['calls']==0
        with pytest.raises(ValueError):backup_bundle(app.config['DATABASE'],tmp_path/'invalid-bundle')


@pytest.mark.browser
@browser_only
def test_browser_important_topics_configuration_and_mobile(browser,live_reader,app,monkeypatch,tmp_path):
    feed_id=setup_ai(app,monkeypatch);calls=model(app,monkeypatch)
    with browser.new_context(viewport={'width':1440,'height':900}) as context:
        page=context.new_page();page.goto(live_reader+f'/social-research/{feed_id}')
        page.get_by_role('button',name='重要トピックを抽出',exact=True).click()
        assert '予約済み' in page.locator('#important-topics').inner_text()
        assert calls==[]
        with app.app_context():ai.process()
        page.reload();assert '重要な研究の公開' in page.locator('#important-topics').inner_text()
        page.get_by_role('link',name='評価観点・自動抽出の設定 →',exact=True).click()
        page.get_by_label('重視する観点',exact=True).fill('実用性と具体的な根拠')
        page.get_by_label('定期収集後に自動抽出する',exact=True).check()
        page.get_by_role('button',name='抽出設定を保存',exact=True).click()
        page.screenshot(path=str(tmp_path/'openrouter-desktop.png'),full_page=True)
        from playwright.sync_api import expect
        expect(page.locator('[data-editor-feedback]')).to_have_text('保存しました。')
        with page.expect_navigation():
            page.get_by_role('dialog').get_by_role('button',name='閉じる',exact=True).click()
        page.get_by_role('link',name='AI接続 →',exact=True).click()
        assert page.url.endswith('/settings/ai')
        assert page.locator('h1').inner_text() == 'AI接続'
        assert page.get_by_label('モデルID',exact=True).input_value()=='vendor/fixture-model'
        assert 'synthetic-' not in page.content()
    with browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True) as context:
        page=context.new_page();page.goto(live_reader+f'/social-research/{feed_id}')
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        assert page.locator('.social-ai-topics li').count()==1
        page.screenshot(path=str(tmp_path/'openrouter-mobile.png'),full_page=True)
