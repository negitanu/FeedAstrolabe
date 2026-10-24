"""Provider isolation and non-secret settings export contracts."""
import json
import pytest
from feedastrolabe import social_ai as ai, ai_providers as gateways, openrouter_http as http
from feedastrolabe.db import get_db
from test_reader import app, client, post
from test_folders import folder_data, snapshot
from test_social_ai import setup_ai, answer
from test_task_navigation import live_empty
from test_feed_disclosure import browser,browser_only


def test_profiles_queue_identity_and_shared_budget(app,monkeypatch):
    fid=setup_ai(app,monkeypatch)
    app.config['ORCAROUTER_API_KEY']='synthetic-'+('o'*32)
    calls=[]
    def generate(cfg,wire,bound):
        payload=json.loads(wire);calls.append((cfg['provider'],payload))
        source=json.loads(payload['messages'][1]['content'])['sources'][0]['article_id']
        return json.dumps({'topics':[answer(source)]}),{'prompt_tokens':100,'completion_tokens':100,'cost_micro_usd':1000},{'provider':cfg['provider']}
    monkeypatch.setattr(ai,'generate',generate)
    with app.app_context():
        old=ai.enqueue(fid)
        ai.configure({'expected_revision':2,'provider':'orcarouter','model':'openai/gpt-4o-mini','enabled':True})
        new=ai.enqueue(fid)
        assert old!=new
        assert ai.detail(old)['provider']=='openrouter' and ai.detail(new)['provider']=='orcarouter'
        ai.process();ai.process()
        assert [value[0] for value in calls]==['openrouter','orcarouter']
        assert 'provider' in calls[0][1] and 'provider' not in calls[1][1]
        assert ai.detail(old)['status']==ai.detail(new)['status']=='success'
        assert ai.configuration()['today']['calls']==2
        ai.configure({'expected_revision':3,'provider':'openrouter'})
        assert ai.configuration()['model']=='vendor/fixture-model'
        assert ai.configuration()['today']['calls']==2
        assert ai.configuration('orcarouter')['model']=='openai/gpt-4o-mini'


def response(cost=True):
    return {'id':'upstream-id','model':'openai/gpt-4o-mini','choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'{"topics":[]}'}}],
            'usage':{'prompt_tokens':10,'completion_tokens':20,**({'cost_usd':0.001} if cost else {})}}


@pytest.mark.parametrize('lookup',[False,True])
def test_orca_wire_cost_and_receipt_normalization(app,monkeypatch,lookup):
    app.config['ORCAROUTER_API_KEY']='synthetic-'+('o'*32);calls=[]
    def transport(wire,**kwargs):
        calls.append(kwargs)
        if kwargs.get('method')=='GET':return {'data':{'id':'orca-request','cost_currency':'USD','total_cost':0.001}}
        return response(not lookup),{'x-orca-request-id':'orca-request'}
    monkeypatch.setattr(http,'request',transport)
    with app.app_context():
        text,usage,lineage=gateways.generate({'provider':'orcarouter','model':'openai/gpt-4o-mini','max_output_tokens':100},'{}',100)
    assert text=='{"topics":[]}' and usage['cost_micro_usd']==1000
    assert lineage['generation_id']=='orca-request' and lineage['provider']=='orcarouter'
    assert calls[0]['host']=='api.orcarouter.ai' and calls[0]['path']=='/v1/chat/completions'
    assert calls[0]['extra_headers']['X-OrcaRouter-Include-Cost']=='true'
    assert len(calls)==(2 if lookup else 1)


def test_orca_unknown_cost_is_not_free_or_regenerated(app,monkeypatch):
    app.config['ORCAROUTER_API_KEY']='synthetic-'+('o'*32);calls=[]
    def transport(wire,**kwargs):
        calls.append(kwargs.get('method','POST'))
        if kwargs.get('method')=='GET':raise http.RouterError('openrouter-http-404')
        return response(False),{'x-orca-request-id':'orca-request'}
    monkeypatch.setattr(http,'request',transport)
    with app.app_context(),pytest.raises(http.RouterError) as error:
        gateways.generate({'provider':'orcarouter','model':'openai/gpt-4o-mini','max_output_tokens':100},'{}',100)
    assert error.value.code=='orcarouter-cost-invalid'
    assert calls==['POST','GET','GET']


@pytest.mark.parametrize('change',[{'usage':{}},{'choices':[]},{'model':'other/model'},{'usage':{'prompt_tokens':1,'completion_tokens':10000,'cost_usd':0.1}}])
def test_orca_rejects_unsupported_responses(app,monkeypatch,change):
    app.config['ORCAROUTER_API_KEY']='synthetic-'+('o'*32)
    monkeypatch.setattr(http,'request',lambda *args,**kwargs:({**response(),**change},{'x-orca-request-id':'orca-request'}))
    with app.app_context(),pytest.raises(http.RouterError):
        gateways.generate({'provider':'orcarouter','model':'openai/gpt-4o-mini','max_output_tokens':100},'{}',100)


def test_export_allowlist_snapshot_and_credentials(app,client,folder_data,monkeypatch):
    from feedastrolabe.keys import issue_key
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-DO-NOT-EXPORT-'+('x'*32))
    before=snapshot(app)
    with app.app_context(),get_db() as db:
        db.execute("INSERT INTO delivery_profiles(name,kind,destination,enabled,created_at,updated_at) VALUES('Private','webhook','https://example.com/hook?token=PRIVATE-CREDENTIAL',0,'2026-10-24','2026-10-24')")
    with app.app_context():_,secret=issue_key('private key','read',90)
    client.set_cookie('feedastrolabe_theme','dark')
    result=post(client,'/settings/export',{'presentation':json.dumps({'width':320,'layout':'line','disclosure':{'Tech':False}})})
    assert result.status_code==200
    data=result.json
    assert data['format']=='feedastrolabe-settings' and data['format_version']==1 and data['db_schema_version']==18
    assert data['settings']['presentation']=={'width':320,'layout':'line','disclosure':{'Tech':False},'appearance':'dark'}
    assert len(data['settings']['subscriptions'])==8
    assert data['settings']['notifications'][0]['destination'] is None
    assert data['omissions'] and 'no-store' in result.headers['Cache-Control']
    assert 'attachment;' in result.headers['Content-Disposition']
    text=result.get_data(as_text=True)
    assert secret not in text and 'PRIVATE-CREDENTIAL' not in text and 'DO-NOT-EXPORT' not in text
    assert 'api_keys' not in text and 'input_hash' not in text and 'article' not in data['settings']
    assert snapshot(app)==before


@pytest.mark.parametrize('raw',['[]','null','{"width":999}','{"width":true}','{"layout":"bad"}','{"disclosure":{"Tech":1}}','{"secret":"bad"}','{"width":320,"width":340}'])
def test_export_rejects_invalid_browser_values(client,raw):
    assert post(client,'/settings/export',{'presentation':raw}).status_code==400
    assert client.post('/settings/export',data={'presentation':'{}'}).status_code==400


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width',[375,1280])
def test_provider_picker_and_export_download(browser,live_empty,folder_data,width):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':width,'height':1000},accept_downloads=True) as context:
        page=context.new_page();page.goto(live_empty+'/settings/ai')
        expect(page.get_by_role('heading',level=1)).to_have_text('AI接続')
        with page.expect_navigation():page.get_by_label('プロバイダ',exact=True).select_option('orcarouter')
        expect(page.get_by_label('モデルID',exact=True)).to_have_value('')
        page.get_by_label('モデルID',exact=True).fill('openai/gpt-4o-mini')
        page.get_by_role('button',name='保存',exact=True).click()
        expect(page.get_by_role('status')).to_contain_text('保存しました')
        with page.expect_navigation():page.get_by_label('プロバイダ',exact=True).select_option('openrouter')
        expect(page.get_by_label('モデルID',exact=True)).to_have_value('')
        with page.expect_navigation():page.get_by_label('プロバイダ',exact=True).select_option('orcarouter')
        expect(page.get_by_label('モデルID',exact=True)).to_have_value('openai/gpt-4o-mini')
        page.goto(live_empty+'/settings')
        expect(page.locator('a[href="/settings/feeds"]')).to_have_count(0)
        expect(page.locator('a[href^="/settings/items/feeds/"]')).to_have_count(0)
        page.evaluate("localStorage.setItem('feedastrolabe.sidebar-width.v1',JSON.stringify({version:1,width:320}))")
        with page.expect_download() as download:page.get_by_role('button',name='設定をエクスポート').click()
        with open(download.value.path()) as file:data=json.load(file)
        assert data['settings']['presentation']['width']==320
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=f'/tmp/feedastrolabe-ai-selection-{width}.png',full_page=True)


def test_v17_upgrade_keeps_configuration_order_and_articles(tmp_path):
    import sqlite3
    from pathlib import Path
    from feedastrolabe.db import connect,init_database
    path=tmp_path/'v17.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript(Path('tests/fixtures/v17_schema.sql').read_text())
        db.execute("INSERT INTO feeds(id,url,title,folder,created_at) VALUES(1,'https://example.com/a','Zed','Tech','2026-10-24'),(2,'https://example.com/b','Alpha','Tech','2026-10-24')")
        db.execute("INSERT INTO articles(feed_id,guid,title,content,search_text,published_at,is_read,is_starred) VALUES(1,'x','Article','Body','Body','2026-10-24',1,1)")
        db.execute("INSERT INTO folder_positions VALUES('Tech',0)")
        db.execute("UPDATE social_ai_config SET model='vendor/existing',enabled=1")
    init_database(path);init_database(path)
    with connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==18
        assert db.execute('SELECT group_concat(feed_id) FROM (SELECT feed_id FROM feed_positions ORDER BY position)').fetchone()[0]=='2,1'
        assert tuple(db.execute('SELECT content,is_read,is_starred FROM articles').fetchone())==('Body',1,1)
        assert db.execute('SELECT provider FROM social_ai_config').fetchone()[0]=='openrouter'
        assert json.loads(db.execute('SELECT settings FROM ai_provider_settings').fetchone()[0])['model']=='vendor/existing'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_pause_automatic_queue_and_backup_profiles(app,client,monkeypatch,tmp_path):
    from feedastrolabe.evidence_backup import backup_bundle,restore_bundle
    from feedastrolabe.db import connect
    fid=setup_ai(app,monkeypatch,automatic=True)
    app.config['ORCAROUTER_API_KEY']='synthetic-'+('o'*32)
    with app.app_context():
        job=ai.enqueue(fid,automatic=True)
    post(client,f'/feeds/{fid}/subscription',{'enabled':'0'})
    with app.app_context():
        assert ai.detail(job)['status']=='failed'
        ai.configure({'expected_revision':2,'provider':'orcarouter','model':'openai/gpt-4o-mini','enabled':True})
        backup_bundle(app.config['DATABASE'],tmp_path/'bundle')
        restore_bundle(tmp_path/'bundle',tmp_path/'restored'/'feeds.sqlite3')
    with connect(tmp_path/'restored'/'feeds.sqlite3') as db:
        profiles={row['provider']:json.loads(row['settings']) for row in db.execute('SELECT * FROM ai_provider_settings')}
        assert profiles['openrouter']['model']=='vendor/fixture-model'
        assert profiles['orcarouter']['model']=='openai/gpt-4o-mini'
        assert all(not cfg['enabled'] for cfg in profiles.values())
