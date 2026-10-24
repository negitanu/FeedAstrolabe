import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest

from feedastrolabe import create_app
from feedastrolabe.db import connect, get_db, init_database
from feedastrolabe.maintenance import backup, restore
from feedastrolabe import research as r
from test_reader import app, client, post, subscribe
from test_phase_two import authorization


@pytest.fixture
def writer(app):
    return authorization(app,'write')[2]


def workspace(client,writer,**values):
    response=client.post('/api/v1/workspaces',headers=writer,json={'title':'AI セキュリティ調査',**values})
    assert response.status_code==201,response.json
    return response.json['data']['id']


def note(client,writer,wid,**values):
    response=client.post(f'/api/v1/workspaces/{wid}/notes',headers=writer,json={'title':'調査メモ','body':'最初の仮説',**values})
    assert response.status_code==201,response.json
    return response.json['data']['id']


def test_v4_migration_and_research_backup(tmp_path):
    path=tmp_path/'v4.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript((Path(__file__).parent/'fixtures/v4_schema.sql').read_text())
        db.execute("INSERT INTO feeds(id,url,title,created_at,source_type,snapshot,observation_seq,revision) VALUES(7,'page:fixture','Page','2026-01-01','page','baseline',2,3)")
        db.execute("INSERT INTO articles(id,feed_id,guid,title,content,search_text,published_at,is_read,is_starred) VALUES(17,7,'saved','Saved','safe','safe','2026-01-01',1,1)")
        db.execute("INSERT INTO page_jobs VALUES(7,'2026-01-01')")
        db.execute("INSERT INTO provider_cooldowns VALUES('x','2026-01-02')")
    old_backup=tmp_path/'old.sqlite3';backup(path,old_backup)
    init_database(path);init_database(path)
    with connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==18
        assert tuple(db.execute('SELECT id,feed_id,is_read,is_starred FROM articles').fetchone())==(17,7,1,1)
        assert tuple(db.execute('SELECT snapshot,observation_seq,revision FROM feeds').fetchone())==('baseline',2,3)
        assert db.execute('SELECT count(*) FROM page_jobs').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM provider_cooldowns').fetchone()[0]==0  # Retired X cooldown removed.
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    restored=tmp_path/'restored'/'feeds.sqlite3';restore(old_backup,restored)
    assert connect(restored).execute('PRAGMA user_version').fetchone()[0]==18
    application=create_app({'TESTING':True,'DATA_DIR':str(tmp_path/'live')})
    with application.app_context():
        wid=r.create_workspace({'title':'Case','classification':'restricted'})
        nid=r.create_note(wid,{'title':'Note','body':'original','label':'fact'})
        r.update_note(nid,{'expected_revision':1,'body':'edited'})
        tid=r.save_tag({'name':'OSINT'});r.associate('workspace',wid,'tag',tid);r.associate('note',nid,'tag',tid)
        r.update_workspace(wid,{'archived':True})
    research_backup=tmp_path/'research.sqlite3';backup(application.config['DATABASE'],research_backup)
    restore(research_backup,restored)
    with connect(restored) as db:
        assert tuple(db.execute('SELECT classification,archived FROM workspaces').fetchone())==('restricted',1)
        assert [row['body'] for row in db.execute('SELECT * FROM note_revisions ORDER BY revision')]==['original','edited']
        assert db.execute('SELECT count(*) FROM note_tags').fetchone()[0]==1
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    restarted=create_app({'TESTING':True,'DATA_DIR':application.instance_path})
    with restarted.app_context():
        assert r.find('note',nid)['revision']==2


def test_multiple_workspaces_feed_union_archive_and_delete(app,client,writer):
    subscribe(client)
    w1=workspace(client,writer);w2=workspace(client,writer,title='別の案件')
    for path in [f'/workspaces/{w1}/articles/1',f'/workspaces/{w2}/articles/1',f'/workspaces/{w1}/feeds/1']:
        for _ in range(2):
            assert client.post('/api/v1'+path,headers=writer).status_code==204
    client.patch('/api/v1/articles/1',headers=writer,json={'is_read':True,'is_starred':True})
    response=client.get(f'/api/v1/workspaces/{w1}/articles?limit=1',headers=writer).json
    assert response['has_more'] and response['data'][0]['id']==2
    next_page=client.get(f'/api/v1/articles?workspace={w1}&before_id={response["next_before_id"]}',headers=writer).json
    assert [a['id'] for a in next_page['data']]==[1]
    assert client.patch(f'/api/v1/workspaces/{w1}',headers=writer,json={'archived':True}).status_code==200
    for path,method,body in [(f'/workspaces/{w1}','patch',{'title':'changed'}),(f'/workspaces/{w1}/articles/1','delete',None),(f'/workspaces/{w1}/feeds/1','post',None),(f'/workspaces/{w1}/notes','post',{'title':'blocked'})]:
        assert getattr(client,method)('/api/v1'+path,headers=writer,**({'json':body} if body is not None else {})).status_code==409
    assert [w['id'] for w in client.get('/api/v1/workspaces?archived=true',headers=writer).json['data']]==[w1]
    assert [a['id'] for a in client.get(f'/api/v1/workspaces/{w2}/articles',headers=writer).json['data']]==[1]
    assert client.get('/api/v1/articles/1',headers=writer).json['data']['is_starred'] is True
    with app.app_context():
        db=get_db()
        with db:
            db.execute("INSERT INTO articles(feed_id,guid,title,content,search_text,published_at) VALUES(1,'future','Future','safe','safe','2026-10-08')")
    assert len(client.get(f'/api/v1/workspaces/{w1}/articles',headers=writer).json['data'])==3
    assert client.patch(f'/api/v1/workspaces/{w1}',headers=writer,json={'archived':False,'title':'combined'}).status_code==409
    assert client.patch(f'/api/v1/workspaces/{w1}',headers=writer,json={'archived':False}).status_code==200
    assert client.delete(f'/api/v1/workspaces/{w1}/articles/1',headers=writer).status_code==204
    assert len(client.get(f'/api/v1/workspaces/{w1}/articles',headers=writer).json['data'])==3
    nid=note(client,writer,w1)
    assert client.delete('/api/v1/feeds/1',headers=writer).status_code==204
    with app.app_context():
        db=get_db()
        assert not db.execute('SELECT * FROM workspace_articles').fetchall()
        assert not db.execute('SELECT * FROM workspace_feeds').fetchall()
        assert r.find('note',nid)['body']=='最初の仮説'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_note_atomic_conflict_history_and_archive(client,writer):
    wid=workspace(client,writer);nid=note(client,writer,wid,label='source-claim')
    assert client.patch(f'/api/v1/notes/{nid}',headers=writer,json={'expected_revision':1,'body':'saved','label':'fact'}).status_code==200
    assert client.patch(f'/api/v1/notes/{nid}',headers=writer,json={'expected_revision':1,'body':'lost','label':'hypothesis'}).status_code==409
    response=client.get(f'/api/v1/notes/{nid}',headers=writer).json['data']
    assert response['revision']==2 and response['body']=='saved' and response['label']=='fact'
    history=client.get(f'/api/v1/notes/{nid}/revisions?limit=1',headers=writer).json
    assert history['has_more'] and history['data'][0]['revision']==2
    first=client.get(f'/api/v1/notes/{nid}/revisions?before_id=2',headers=writer).json['data'][0]
    assert first['revision']==1 and first['label']=='source-claim' and first['body']=='最初の仮説'
    assert client.patch(f'/api/v1/notes/{nid}/revisions',headers=writer,json={'body':'overwrite'}).status_code==405
    assert client.patch(f'/api/v1/notes/{nid}',headers=writer,json={'expected_revision':2,'archived':True}).status_code==200
    assert not client.get(f'/api/v1/workspaces/{wid}/notes',headers=writer).json['data']
    assert client.get(f'/api/v1/workspaces/{wid}/notes?archived=true',headers=writer).json['data'][0]['revision']==3
    assert client.patch(f'/api/v1/notes/{nid}',headers=writer,json={'expected_revision':3,'body':'blocked'}).status_code==409
    assert client.patch(f'/api/v1/notes/{nid}',headers=writer,json={'expected_revision':3,'archived':False}).status_code==200
    client.patch(f'/api/v1/workspaces/{wid}',headers=writer,json={'archived':True})
    assert client.patch(f'/api/v1/notes/{nid}',headers=writer,json={'expected_revision':4,'archived':True}).status_code==409


def test_concurrent_note_writers(app,client,writer):
    wid=workspace(client,writer);nid=note(client,writer,wid)
    def edit(body):
        with app.app_context():
            try:
                r.update_note(nid,{'expected_revision':1,'body':body})
                return 'saved'
            except r.ResearchConflict:
                return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(edit,['first writer','second writer']))
    assert sorted(outcomes)==['conflict','saved']
    with app.app_context():
        assert r.find('note',nid)['revision']==2
        assert get_db().execute('SELECT count(*) FROM note_revisions').fetchone()[0]==2


def test_tags_rename_association_filters_and_bounds(app,client,writer):
    subscribe(client);wid=workspace(client,writer);nid=note(client,writer,wid)
    tid=client.post('/api/v1/tags',headers=writer,json={'name':'OSINT'}).json['data']['id']
    assert client.post('/api/v1/tags',headers=writer,json={'name':'osint'}).status_code==409
    for path in [f'/workspaces/{wid}/tags/{tid}',f'/articles/1/tags/{tid}',f'/notes/{nid}/tags/{tid}',f'/workspaces/{wid}/feeds/1',f'/workspaces/{wid}/articles/1']:
        assert client.post('/api/v1'+path,headers=writer).status_code==204
    assert [a['id'] for a in client.get(f'/api/v1/articles?workspace={wid}&tag={tid}',headers=writer).json['data']]==[1]
    assert client.get(f'/api/v1/workspaces?tag={tid}',headers=writer).json['data'][0]['id']==wid
    assert client.get(f'/api/v1/workspaces/{wid}/notes?tag={tid}',headers=writer).json['data'][0]['id']==nid
    assert client.patch(f'/api/v1/tags/{tid}',headers=writer,json={'name':'Threat research'}).status_code==200
    for path in [f'/workspaces/{wid}',f'/notes/{nid}']:
        assert client.get('/api/v1'+path,headers=writer).json['data']['tags']==[{'id':tid,'name':'Threat research'}]
    assert 'First story' in client.get(f'/?workspace={wid}&tag={tid}').get_data(as_text=True)
    assert 'Second story' not in client.get(f'/?workspace={wid}&tag={tid}').get_data(as_text=True)
    post(client,'/articles/read-all',{'workspace':str(wid),'tag':str(tid)})
    with app.app_context():
        assert [row[0] for row in get_db().execute('SELECT is_read FROM articles ORDER BY id')]==[1,0]
    for path,status in [('/articles?workspace=999',404),('/articles?tag=999',404),(f'/workspaces/{wid}/articles?workspace=999',400),('/workspaces?tag=999',404),('/workspaces?limit=101',400),('/tags?after_id=-1',400),('/tags?before_id=2&after_id=1',400),('/articles?workspace=0',400),(f'/workspaces/{wid}/notes?archived=maybe',400)]:
        assert client.get('/api/v1'+path,headers=writer).status_code==status,path
    assert client.post(f'/api/v1/workspaces/{wid}/articles/999',headers=writer).status_code==404
    assert client.post(f'/api/v1/workspaces/{wid}/articles/1',headers=writer,json={'ignored':True}).status_code==400
    assert client.delete(f'/api/v1/articles/1/tags/{tid}',headers=writer).status_code==204
    assert not client.get(f'/api/v1/articles?tag={tid}',headers=writer).json['data']


@pytest.mark.parametrize('body',[{},[],{'title':''},{'title':'a'*121},{'title':'null\x00'},{'title':False},{'title':'fine','purpose':'a'*10001},{'title':'fine','status':[]},{'title':'fine','classification':'secret'},{'title':'fine','archived':1},{'title':'fine','sql':'drop table'}])
def test_workspace_invalid_atomic(app,client,writer,body):
    assert client.post('/api/v1/workspaces',headers=writer,json=body).status_code==400
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM workspaces').fetchone()[0]==0


@pytest.mark.parametrize('body',[{'expected_revision':True,'body':'bad'},{'expected_revision':1},{'expected_revision':1,'body':'x'*100001},{'expected_revision':1,'label':'truth'},{'expected_revision':1,'workspace_id':999},{'expected_revision':1,'archived':'true'},{'body':'missing revision'}])
def test_note_invalid_atomic(app,client,writer,body):
    wid=workspace(client,writer);nid=note(client,writer,wid)
    assert client.patch(f'/api/v1/notes/{nid}',headers=writer,json=body).status_code==400
    with app.app_context():
        assert r.find('note',nid)['revision']==1
        assert get_db().execute('SELECT count(*) FROM note_revisions').fetchone()[0]==1


def test_scope_csrf_and_safe_markdown_ui(app,client,writer):
    wid=workspace(client,writer)
    hostile='# Findings\n\n**bold**\n\n<script>alert(1)</script><svg onload="alert(1)"></svg>\n\n[unsafe](javascript:alert(1))\n\n![image](https://evil.example/beacon)\n\n[reference](https://example.com/report)'
    nid=note(client,writer,wid,body=hostile)
    read=authorization(app,'read')[2]
    for path,method,body in [('/workspaces','post',{'title':'forbidden'}),(f'/workspaces/{wid}','patch',{'title':'forbidden'}),(f'/notes/{nid}','patch',{'expected_revision':1,'body':'forbidden'}),('/tags','post',{'name':'forbidden'}),(f'/workspaces/{wid}/tags/1','post',None),(f'/articles/1/tags/1','delete',None)]:
        assert getattr(client,method)('/api/v1'+path,headers=read,**({'json':body} if body else {})).status_code==403
    for path in ['/workspaces',f'/workspaces/{wid}',f'/notes/{nid}',f'/notes/{nid}/revisions','/tags']:
        assert client.get('/api/v1'+path,headers=read).status_code==200
        assert client.get('/api/v1'+path).status_code==401
    assert client.post('/workspaces',data={'title':'missing csrf'}).status_code==400
    assert client.post(f'/workspaces/notes/{nid}',data={'expected_revision':'1','body':'unsafe'}).status_code==400
    for path in ['/workspaces',f'/workspaces/{wid}',f'/workspaces/notes/{nid}']:
        response=client.get(path)
        assert response.status_code==200
        assert "script-src 'nonce-" in response.headers['Content-Security-Policy']
    html=client.get(f'/workspaces/notes/{nid}').get_data(as_text=True)
    assert '<strong>bold</strong>' in html and '<h1>Findings</h1>' in html
    assert '<script>' not in html and '<svg' not in html and '<img' not in html and 'href="javascript:' not in html
    assert 'href="https://example.com/report"' in html
    assert '同じライブラリ' in client.get(f'/workspaces/{wid}').get_data(as_text=True)
    response=post(client,f'/workspaces/notes/{nid}',{'title':'保存成功','body':'first save','label':'fact','expected_revision':'1'})
    assert response.status_code==302
    response=post(client,f'/workspaces/notes/{nid}',{'title':'未保存の題名','body':'RECOVER ME </textarea><script>evil</script>','label':'hypothesis','expected_revision':'1'})
    assert response.status_code==409
    assert '未保存の題名' in response.get_data(as_text=True) and 'RECOVER ME &lt;/textarea&gt;' in response.get_data(as_text=True)
    assert 'name="expected_revision" value="2"' in response.get_data(as_text=True)
    assert client.get(f'/api/v1/notes/{nid}',headers=writer).json['data']['body']=='first save'


def test_ui_forms_archive_links_tags_and_pagination(app,client,writer):
    subscribe(client)
    response=post(client,'/workspaces',{'title':'ネットワーク調査','purpose':'調査目的','questions':'問い','status':'active','classification':'internal'})
    assert response.status_code==302
    wid=1
    tid=client.post('/api/v1/tags',headers=writer,json={'name':'ネットワーク'}).json['data']['id']
    for kind,target in [('feed',1),('article',1),('tag',tid)]:
        assert post(client,f'/workspaces/{wid}/links/{kind}',{'target_id':str(target)}).status_code==302
    assert post(client,f'/workspaces/{wid}/notes',{'title':'接続の仮説','body':'**メモ**','label':'hypothesis'}).status_code==302
    assert post(client,'/workspaces/tags/note/1',{'tag_id':str(tid)}).status_code==302
    assert post(client,'/workspaces/tags/article/1',{'tag_id':str(tid)}).status_code==302
    assert post(client,'/workspaces/article/2/link',{'workspace_id':str(wid)}).status_code==302
    assert client.get('/?article=1').status_code==200
    with app.app_context():
        for i in range(31):
            r.create_workspace({'title':f'Case {i}'})
            r.update_note(1,{'expected_revision':i+1,'body':f'version {i}'})
    for path in ['/workspaces?page=2','/workspaces/notes/1?page=2']:
        response=client.get(path)
        assert response.status_code==200 and '2 / 2' in response.get_data(as_text=True)
    for path in ['/workspaces?page=-1','/workspaces?tag=999','/workspaces/1?notes_archived=invalid','/?workspace=999','/?tag=0']:
        assert client.get(path).status_code in (400,404)
    assert post(client,'/workspaces/1/archive',{'archived':'true'}).status_code==302
    assert post(client,'/workspaces/1/links/article',{'target_id':'2'}).status_code==409
    assert post(client,'/workspaces/1/archive',{'archived':'false'}).status_code==302
    assert post(client,'/workspaces/notes/1/archive',{'expected_revision':'32','archived':'true'}).status_code==302
    assert client.get('/workspaces/1?notes_archived=true').status_code==200


def test_tag_association_bound_and_older_selected_filter(app,client,writer):
    wid=workspace(client,writer)
    with app.app_context():
        tags=[r.save_tag({'name':f'tag {i:03}'}) for i in range(101)]
        for tid in tags[:100]:
            r.associate('workspace',wid,'tag',tid)
        r.associate('workspace',wid,'tag',tags[0])
        with pytest.raises(ValueError):
            r.associate('workspace',wid,'tag',tags[100])
        assert len(r.tag_rows('workspace',wid))==100
        for i in range(100):
            r.create_workspace({'title':f'new {i}'})
    html=client.get(f'/?workspace={wid}&tag={tags[100]}').get_data(as_text=True)
    assert f'value="{wid}" selected' in html
    assert f'value="{tags[100]}" selected' in html
    assert f'value="{tags[100]}" selected' in client.get(f'/workspaces?tag={tags[100]}').get_data(as_text=True)
