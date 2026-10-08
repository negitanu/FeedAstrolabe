import json
from pathlib import Path
import pytest
from feedastrolabe import create_app,evidence as e,research as r,triage as t
from feedastrolabe.db import get_db,connect,init_database
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle,validate_bundle
from test_reader import app,client,subscribe,post
from test_phase_two import authorization


def setup(app):
    with app.app_context():
        wid=r.create_workspace({'title':'セキュリティ監視'})
        r.associate('workspace',wid,'feed',1)
        return wid


def rule(name='製品',**extra):
    return {'name':name,'query':{'any':[{'field':'text','op':'contains','value':'Hello'}]},'exclusion':{'any':[{'field':'text','op':'contains','value':'100%'}]},'priority':'high','reason':'使用製品に関連',**extra}


def test_literal_rules_exclusion_scope_revisions_and_digest(app,client):
    subscribe(client);wid=setup(app)
    with app.app_context():
        identifier=t.save(wid,rule());assert t.process()['events_created']==1
        row=get_db().execute('SELECT * FROM watch_events').fetchone();data=t.record(row)
        assert not data['included'] and data['explanation']['include_passed'] and data['explanation']['exclusion_passed']
        assert data['explanation']['include_matches'][0]['value']=='Hello'
        assert t.process()['events_created']==0 and t.reprocess(identifier)['events_created']==0
        assert t.save(wid,{'expected_revision':1,'exclusion':{}},identifier)==identifier
        assert t.process()['events_created']==1
        versions=get_db().execute('SELECT * FROM watchlist_versions ORDER BY id').fetchall();assert len(versions)==2
        assert json.loads(versions[0]['exclusion'])['any'][0]['value']=='100%'
        with pytest.raises(r.ResearchConflict):t.save(wid,{'expected_revision':1,'priority':'low'},identifier)
        other=r.create_workspace({'title':'別案件'});other_rule=t.save(other,rule(exclusion={}))
        assert t.preview(other_rule)['data']==[]
        db=get_db();before=[tuple(row) for row in db.execute('SELECT id,is_read,is_starred FROM articles')]
        r.update_workspace(wid,{'archived':True})
        assert t.process()['events_created']==0
        with pytest.raises(r.ResearchConflict):t.reprocess(identifier)
        assert [tuple(row) for row in db.execute('SELECT id,is_read,is_starred FROM articles')]==before
    writer=authorization(app,'write')[2];reader=authorization(app,'read')[2]
    path=f'/api/v1/workspaces/{wid}'
    assert client.get(path+'/digest',headers=reader).json['data'][0]['included'] is True
    assert len(client.get(path+'/watch-events',headers=reader).json['data'])==2
    assert client.get(path+'/digest?date=2026-02-30',headers=reader).status_code==400
    assert client.post(f'/api/v1/watchlists/{identifier}/reprocess',headers=reader).status_code==403
    assert client.post(f'/api/v1/watchlists/{identifier}/reprocess',headers=writer).status_code==409
    assert client.get(f'/triage/{wid}').status_code==200


def test_ast_bounds_unknown_sql_and_literal_symbols(app,client):
    subscribe(client);wid=setup(app)
    with app.app_context():
        for ast in [[],{'sql':'DROP TABLE articles'},{'all':'Hello'},{'all':[{'field':'text','op':'regex','value':'.*'}]}, {'all':[{'field':['text'],'op':'eq','value':'x'}]}, {'all':[{'field':'captured_at','op':'gte','value':'2026-02-30 00:00:00'}]}, {'all':[{'field':'text','op':'contains','value':'x'}]*41}]:
            with pytest.raises(ValueError):t.save(wid,rule(query=ast))
        with pytest.raises(ValueError):t.save(wid,rule(query={'all':[{'field':'text','op':'contains','value':'x'}]*21},exclusion={'all':[{'field':'text','op':'contains','value':'y'}]*20}))
        for value,expected in [('100%',True),('100_',False),("' OR 1=1 --",False)]:
            identifier=t.save(wid,rule(name=value,query={'any':[{'field':'text','op':'contains','value':value}]},exclusion={}))
            assert t.preview(identifier)['data'][0]['included']==expected
        assert get_db().execute('SELECT count(*) FROM watchlists').fetchone()[0]==3
    read=authorization(app,'read')[2];write=authorization(app,'write')[2]
    assert client.post(f'/api/v1/workspaces/{wid}/watchlists',headers=read,json=rule()).status_code==403
    assert client.post(f'/api/v1/workspaces/{wid}/watchlists',headers=write,json={'name':'X','enabled':1}).status_code==400
    assert client.post(f'/triage/{wid}/create',data={'name':'X'}).status_code==400


def test_incremental_batches_new_versions_and_seen_state(app,client):
    subscribe(client);wid=setup(app)
    with app.app_context():
        identifier=t.save(wid,rule(query={},exclusion={}))
        db=get_db()
        with e.storage_lock(),r.transaction() as tx:
            for n in range(105):
                eid=e.save(tx,source_key='batch'+str(n),title='Signal',text='one '+str(n),method='fixture',feed_id=1)
        assert t.process()['evidence_scanned']==100
        assert t.process()['evidence_scanned']==7
        assert t.process()['evidence_scanned']==0
        assert db.execute('SELECT count(*) FROM watch_events').fetchone()[0]==107
        first=db.execute('SELECT id FROM watch_events ORDER BY id LIMIT 1').fetchone()[0]
        t.reprocess(identifier);t.process();assert db.execute('SELECT count(*) FROM watch_events').fetchone()[0]==107
        with e.storage_lock(),r.transaction() as tx:
            changed=e.save(tx,source_key='batch0',title='Signal',text='changed',method='fixture',feed_id=1)
        assert t.process()['events_created']==1
        assert db.execute('SELECT evidence_id FROM watch_events ORDER BY id DESC').fetchone()[0]==changed
    writer=authorization(app,'write')[2];reader=authorization(app,'read')[2]
    assert client.patch(f'/api/v1/watch-events/{first}',headers=writer,json={'seen':True}).json['data']['seen'] is True
    assert client.patch(f'/api/v1/watch-events/{first}',headers=reader,json={'seen':False}).status_code==403
    response=client.get(f'/api/v1/workspaces/{wid}/watch-events?limit=100',headers=reader).json
    assert len(response['data'])==100 and response['has_more']
    assert client.get('/triage/'+str(wid)).status_code==200


def test_provenance_groups_canonical_queries_undo_and_retention(app,client,monkeypatch):
    subscribe(client);wid=setup(app)
    with app.app_context():
        db=get_db();before=[tuple(row) for row in db.execute('SELECT id,is_read,is_starred FROM articles')]
        with e.storage_lock(),r.transaction() as tx:
            a=e.save(tx,source_key='publisher-a',title='First',text='identical',method='fixture',source_url='https://example.com/item?utm_source=a&id=1',publisher='A')
            b=e.save(tx,source_key='publisher-b',title='Second',text='identical',method='fixture',source_url='https://example.com/item?id=1&gclid=tracking#part',publisher='B')
            e.save(tx,source_key='publisher-c',title='Different',text='different',method='fixture',source_url='https://example.com/item?id=2',publisher='C')
        t.process();groups=db.execute('SELECT * FROM duplicate_groups').fetchall();assert len(groups)==2
        for group in groups:
            assert {row[0] for row in db.execute('SELECT evidence_id FROM duplicate_members WHERE group_id=?',(group['id'],))}=={a,b}
            t.toggle_group(group['id'],{'suppressed':True})
        t.process();assert db.execute('SELECT count(*) FROM duplicate_groups WHERE suppressed=1').fetchone()[0]==2
        with e.storage_lock(),r.transaction() as tx:
            c=e.save(tx,source_key='publisher-d',title='Third',text='identical',method='fixture',publisher='D')
        t.process();assert db.execute('SELECT count(*) FROM duplicate_groups WHERE suppressed=0').fetchone()[0]==0
        assert [tuple(row) for row in db.execute('SELECT id,is_read,is_starred FROM articles')]==before
        assert t.canonical_url('https://example.com/a?q=1&q=&UTM_medium=x')=='https://example.com/a?q=&q=1'
        assert t.canonical_url('http://127.0.0.1/') is None
        gid=groups[0]['id'];t.toggle_group(gid,{'suppressed':False})
        with db:db.execute("UPDATE evidence SET captured_at='2000-01-01 00:00:00'")
        e.prune();assert e.find(a) and e.find(b) and e.find(c)
    reader=authorization(app,'read')[2]
    assert client.get(f'/api/v1/duplicate-groups/{gid}/members',headers=reader).status_code==200
    assert client.get(f'/triage/groups/{gid}').status_code==200


def test_v6_migration_bundle_and_monotonic_cursor(tmp_path):
    data=tmp_path/'data';data.mkdir();database=data/'feeds.sqlite3';db=connect(database)
    db.executescript(Path('tests/fixtures/v6_schema.sql').read_text())
    db.execute("INSERT INTO evidence_blobs(hash,size) VALUES(?,1)",(e.digest(b'x'),))
    db.execute("INSERT INTO evidence(id,source_key,version,source_url,publisher,source_guid,title,method,captured_at,blob_hash,text_hash,text,mime,filename) VALUES(30,'old',1,'','','','Old','fixture','2026-01-01 00:00:00',?,?,'x','text/plain','')",(e.digest(b'x'),e.digest(b'x')));db.commit();db.close()
    blobs=data/'evidence-blobs';blobs.mkdir();(blobs/e.digest(b'x')).write_bytes(b'x')
    db=connect(database)
    db.execute("INSERT INTO workspaces(id,title,created_at,updated_at) VALUES(9,'Old case','2026-01-01','2026-01-01')")
    db.execute("INSERT INTO notes(id,workspace_id,title,revision,created_at,updated_at) VALUES(6,9,'Old note',1,'2026-01-01','2026-01-01')")
    db.execute('INSERT INTO workspace_evidence VALUES(9,30)');db.execute('INSERT INTO note_evidence VALUES(6,30)')
    db.execute("INSERT INTO quotations(workspace_id,note_id,evidence_id,text_hash,start,end,quote,created_at) VALUES(9,6,30,?,0,1,'x','2026-01-01')",(e.digest(b'x'),))
    db.commit();db.close()
    # A genuine v6 bundle remains valid and upgrades on restore.
    bundle=tmp_path/'v6-bundle';backup_bundle(database,bundle);assert json.loads((bundle/'manifest.json').read_text())['schema']==6
    init_database(database);app=create_app({'TESTING':True,'DATA_DIR':str(data)})
    with app.app_context():
        db=get_db();assert db.execute('PRAGMA user_version').fetchone()[0]==13 and not db.execute('PRAGMA foreign_key_check').fetchall()
        assert db.execute('SELECT quote FROM quotations WHERE evidence_id=30').fetchone()[0]=='x'
        assert db.execute('SELECT evidence_id FROM note_evidence').fetchone()[0]==30
        with db:
            db.execute('DELETE FROM workspaces WHERE id=9')
            db.execute('DELETE FROM evidence WHERE id=30')
        with e.storage_lock(),r.transaction() as tx:new=e.save(tx,source_key='new',title='New',text='y',method='fixture')
        assert new>30
        wid=r.create_workspace({'title':'復元'});e.pin('workspace',wid,new);identifier=t.save(wid,{'name':'Every','query':{}});t.process()
    newbundle=tmp_path/'v7-bundle';backup_bundle(database,newbundle);restore=tmp_path/'restored'/'feeds.sqlite3';restore_bundle(newbundle,restore)
    restored=create_app({'TESTING':True,'DATA_DIR':str(restore.parent)})
    with restored.app_context():
        assert get_db().execute('SELECT count(*) FROM watch_events').fetchone()[0]==1
        assert t.reprocess(identifier)['events_created']==0
    oldrestore=tmp_path/'old-restored'/'feeds.sqlite3';restore_bundle(bundle,oldrestore)
    db=connect(oldrestore);assert db.execute('PRAGMA user_version').fetchone()[0]==13;assert db.execute('SELECT text FROM evidence').fetchone()[0]=='x';assert db.execute('SELECT quote FROM quotations').fetchone()[0]=='x';assert not db.execute('PRAGMA foreign_key_check').fetchall();db.close()


def test_disabled_search_continuation_tags_dates_and_rule_caps(app,client):
    subscribe(client);wid=setup(app)
    with app.app_context():
        tag=r.save_tag({'name':'生成AI'});r.associate('article',1,'tag',tag)
        identifier=t.save(wid,rule(kind='saved-search',enabled=False,exclusion={},query={'all':[{'field':'tag','op':'eq','value':'生成AI'},{'field':'published_at','op':'gte','value':'2026-10-01 00:00:00'}],'none':[{'field':'title','op':'contains','value':'Second'}]}))
        assert t.process()['events_created']==0
        results=t.preview(identifier)['data'];assert [x['included'] for x in results]==[True,False]
        assert t.process(identifier)['events_created']==1
        assert t.reprocess(identifier)['events_created']==0
        for n in range(99):t.save(wid,{'name':str(n),'enabled':False})
        with pytest.raises(ValueError):t.save(wid,{'name':'101st'})
        assert get_db().execute('SELECT count(*) FROM watchlists WHERE workspace_id=?',(wid,)).fetchone()[0]==100
    writer=authorization(app,'write')[2]
    assert client.post(f'/api/v1/watchlists/{identifier}/process',headers=writer).status_code==200
    assert client.get('/api/v1/watchlists/9223372036854775808',headers=writer).status_code==400
    assert client.patch('/api/v1/watch-events/9223372036854775808',headers=writer,json={'seen':True}).status_code==400
    assert client.get('/triage/groups?suppressed=invalid').status_code==400
    assert client.get(f'/triage/{wid}?digest=invalid').status_code==400


def test_parallel_worker_idempotency_and_rule_edit_conflict(app,client):
    from concurrent.futures import ThreadPoolExecutor
    subscribe(client);wid=setup(app)
    with app.app_context():identifier=t.save(wid,rule(exclusion={}))
    def run():
        with app.app_context():return t.process()['events_created']
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(lambda _:run(),range(2)))==[0,1]
    def edit(reason):
        with app.app_context():
            try:t.save(wid,{'expected_revision':1,'reason':reason},identifier);return 'saved'
            except r.ResearchConflict:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(edit,['a','b']))==['conflict','saved']
    with app.app_context():assert get_db().execute('SELECT count(*) FROM watchlist_versions').fetchone()[0]==2


def test_worker_integration_and_fair_bounded_rule_batches(app,client):
    subscribe(client);wid=setup(app)
    with app.app_context():
        for n in range(25):t.save(wid,rule(name='rule '+str(n),exclusion={}))
    runner=app.test_cli_runner()
    assert runner.invoke(args=['worker','--once']).exit_code==0
    with app.app_context():assert get_db().execute('SELECT count(*) FROM watch_events').fetchone()[0]==20
    assert runner.invoke(args=['worker','--once']).exit_code==0
    with app.app_context():assert get_db().execute('SELECT count(DISTINCT version_id) FROM watch_events').fetchone()[0]==25
