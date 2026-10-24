import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
from feedastrolabe import create_app,entities as n,evidence as e,research as r
from feedastrolabe.db import get_db,connect,init_database
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle
from test_reader import app,client,subscribe,post
from test_phase_two import authorization


def capture(app,text,source='entity-fixture'):
    with app.app_context():
        with e.storage_lock(),r.transaction() as db:return e.save(db,source_key=source,title='対象の資料',text=text,method='fixture',publisher='Fixture')


def context(app,eid):
    with app.app_context():
        wid=r.create_workspace({'title':'OSINT 調査'})
        e.pin('workspace',wid,eid);item=e.find(eid)
        qid=e.quotation(wid,{'evidence_id':eid,'start':0,'end':len(item['text']),'quote':item['text']})
        return wid,qid


def test_strict_normalization_and_ambiguous_names(app):
    with app.app_context():
        for kind,value,expected in [('ip','2001:0DB8:0:0:0:0:0:1','2001:db8::1'),('ip','192.0.2.1','192.0.2.1'),('domain','BÜCHER.example.','xn--bcher-kva.example'),('cve','cve-2026-123456','CVE-2026-123456'),('asn','as00064512','AS64512'),('repository','https://GitHub.com/Owner/Repo.git','github.com/owner/repo'),('hash','A'*64,'a'*64)]:assert n.normalize(kind,value)==expected
        for kind,value in [('ip','1.2.3.999'),('ip','010.0.0.1'),('ip','fe80::1%en0'),('ip','2001::x'),('domain','host..example'),('domain','foo.example..'),('domain','-bad.example'),('domain','1.2.3.4'),('asn','AS4294967296'),('cve','CVE-2026-123'),('hash','g'*64),('repository','https://github.com.evil/a/b'),('repository','https://user:x@github.com/a/b')]:
            with pytest.raises(ValueError):n.normalize(kind,value)
        first=n.create({'kind':'organization','value':'ACME'});second=n.create({'kind':'organization','value':'ACME'})
        assert first!=second
        a=n.create({'kind':'domain','value':'Example.COM'});b=n.create({'kind':'domain','value':'example.com.'});assert a==b
        sharp=n.create({'kind':'domain','value':'faß.de'});plain=n.create({'kind':'domain','value':'fass.de'});assert sharp!=plain
        assert n.normalize('domain','faß.de')=='xn--fa-hia.de'
        n.alias(first,{'value':'同じ別名','reviewed':True});n.alias(second,{'value':'同じ別名','reviewed':False})
        assert n.find(first)['merged_into'] is None and n.find(second)['merged_into'] is None


def test_original_ipv6_mentions_correction_retry_and_retention(app,client):
    text='2001:0DB8:0000:0000:0000:0000:0000:0001 and 2001:db8::1. CVE-2026-123456 AS64512 https://github.com/Owner/Repo '+('A'*64)+' Bücher.example'
    eid=capture(app,text);wid,qid=context(app,eid)
    with app.app_context():
        result=n.extract();assert result['mentions_created']>=7
        db=get_db();ips=db.execute("SELECT * FROM entities WHERE kind='ip'").fetchall();assert len(ips)==1
        mentions=db.execute("SELECT * FROM entity_mentions WHERE entity_id=? ORDER BY id",(ips[0]['id'],)).fetchall();assert len(mentions)==2
        assert {row['original'] for row in mentions}=={'2001:0DB8:0000:0000:0000:0000:0000:0001','2001:db8::1'}
        assert all(text[row['start']:row['end']]==row['original'] for row in mentions)
        mid=mentions[0]['id'];old_original=dict(mentions[0]);n.correct_mention(mid,{'expected_revision':1,'status':'rejected'})
        assert n.extract(eid,reprocess=True)['mentions_created']==0
        current=n.mention(mid);assert current['status']=='rejected' and current['revision']==2
        for key in ['original_entity_id','original','start','end','text_hash']:assert current[key]==old_original[key]
        with pytest.raises(r.ResearchConflict):n.correct_mention(mid,{'expected_revision':1,'status':'confirmed'})
        assert db.execute('SELECT count(*) FROM entity_audit WHERE kind=\'mention-corrected\'').fetchone()[0]==1
        with db:db.execute("UPDATE evidence SET captured_at='2000-01-01 00:00:00'")
        e.prune();assert e.find(eid)
    read=authorization(app,'read')[2]
    assert len(client.get(f'/api/v1/entities/{ips[0]["id"]}/mentions?workspace={wid}',headers=read).json['data'])==2
    assert client.get(f'/entities/{ips[0]["id"]}?workspace={wid}').status_code==200


def test_manual_mentions_anchors_scope_and_permissions(app,client):
    eid=capture(app,'ACME and Example.COM');wid,qid=context(app,eid)
    write=authorization(app,'write')[2];read=authorization(app,'read')[2]
    created=client.post('/api/v1/entities',headers=write,json={'kind':'organization','value':'ACME'});assert created.status_code==201;identifier=created.json['data']['id']
    body={'entity_id':identifier,'evidence_id':eid,'start':0,'end':4,'original':'ACME'}
    assert client.post('/api/v1/mentions',headers=read,json=body).status_code==403
    assert client.post('/api/v1/mentions',headers=write,json={**body,'original':'Fake'}).status_code==400
    result=client.post('/api/v1/mentions',headers=write,json=body);assert result.status_code==201
    mid=result.json['data']['id']
    assert client.patch(f'/api/v1/mentions/{mid}',headers=write,json={'expected_revision':1,'status':'confirmed','entity_id':9223372036854775808}).status_code==400
    assert client.get(f'/api/v1/entities?q=ACME&workspace={wid}',headers=read).json['data'][0]['id']==identifier
    with app.app_context():other=r.create_workspace({'title':'別案件'})
    assert client.get(f'/api/v1/entities?q=ACME&workspace={other}',headers=read).json['data']==[]
    assert client.get(f'/api/v1/entities/{identifier}/graph?workspace={other}',headers=read).status_code==404
    assert client.post('/entities/create',data={'kind':'organization','value':'X'}).status_code==400
    assert client.get('/api/v1/entities/9223372036854775808',headers=read).status_code==400
    assert client.get('/api/v1/entities?q='+('x'*201),headers=read).status_code==400
    assert client.get('/api/v1/entities?q=100%25',headers=read).json['data']==[]
    assert client.get('/api/v1/entities?q=_',headers=read).json['data']==[]


def test_quoted_relation_versions_scope_dates_and_graph(app,client):
    eid=capture(app,'a.example and b.example share 192.0.2.1');wid,qid=context(app,eid)
    with app.app_context():
        n.extract();db=get_db();a=db.execute("SELECT id FROM entities WHERE canonical='a.example'").fetchone()[0];b=db.execute("SELECT id FROM entities WHERE canonical='b.example'").fetchone()[0];ip=db.execute("SELECT id FROM entities WHERE kind='ip'").fetchone()[0]
        body={'source_id':a,'target_id':ip,'predicate':'observed-address','quotation_id':qid,'label':'source-claim','confidence':'unknown','observed_at':'2026-10-08 00:00:00'}
        rid=n.save_relation(wid,body);second=n.save_relation(wid,{**body,'source_id':b})
        graph=n.graph(a,wid);assert {node['id'] for node in graph['nodes']}=={a,b,ip};assert len(graph['edges'])==2
        assert all(edge['predicate']=='observed-address' and edge['confidence']=='unknown' for edge in graph['edges'])
        n.save_relation(wid,{'expected_revision':1,'confidence':'low','valid_from':'2026-01-01 00:00:00','valid_to':'2026-12-31 23:59:59'},rid)
        assert db.execute('SELECT confidence FROM relation_versions WHERE relation_id=? AND revision=1',(rid,)).fetchone()[0]=='unknown'
        with pytest.raises(r.ResearchConflict):n.save_relation(wid,{'expected_revision':1,'confidence':'high'},rid)
        with pytest.raises(ValueError):n.save_relation(wid,{'expected_revision':2,'valid_to':'2025-12-31 00:00:00'},rid)
        other=r.create_workspace({'title':'Other'})
        with pytest.raises(ValueError):n.save_relation(other,body)
        assert db.execute('SELECT count(*) FROM relations').fetchone()[0]==2
        n.save_relation(wid,{'expected_revision':2,'archived':True},rid);assert len(n.graph(a,wid)['edges'])==0
        r.update_workspace(wid,{'archived':True})
        with pytest.raises(r.ResearchConflict):n.save_relation(wid,{'expected_revision':3,'archived':False},rid)
    read=authorization(app,'read')[2]
    assert client.get(f'/api/v1/relations/{rid}/revisions',headers=read).json['data'][0]['revision']==3
    assert client.get(f'/entities/relations/{rid}').status_code==200
    assert client.get(f'/api/v1/entities/{a}/graph?depth=3',headers=read).status_code==400


def test_audited_merge_unmerge_originals_and_concurrent_review(app,client):
    eid=capture(app,'ACME');wid,qid=context(app,eid)
    with app.app_context():
        a=n.create({'kind':'organization','value':'ACME'});b=n.create({'kind':'organization','value':'ACME Labs'})
        mid=n.add_mention({'entity_id':a,'evidence_id':eid,'start':0,'end':4,'original':'ACME'})
        n.alias(a,{'value':'Acme original alias','reviewed':True})
        relation=n.save_relation(wid,{'source_id':a,'target_id':b,'quotation_id':qid,'predicate':'possible-name-variant','label':'hypothesis'})
        before=dict(n.mention(mid));n.merge(a,{'target_id':b,'expected_revision':1,'reviewed':True,'reason':'人が同一対象と判断'})
        assert n.root(a)==b and n.root(b)==b
        assert dict(n.mention(mid))==before and n.relation(relation)['source_id']==a
        assert set(n.family(b)[0])=={a,b}
        with pytest.raises(r.ResearchConflict):n.merge(b,{'target_id':a,'expected_revision':1,'reviewed':True,'reason':'cycle'})
        with pytest.raises(r.ResearchConflict):n.merge(a,{'expected_revision':1,'reason':'stale'},undo=True)
        n.merge(a,{'expected_revision':2,'reason':'誤った統合を戻す'},undo=True)
        assert n.root(a)==a and n.find(a)['revision']==3
        assert dict(n.mention(mid))==before and n.relation(relation)['source_id']==a
        assert get_db().execute('SELECT count(*) FROM entity_aliases WHERE entity_id=?',(a,)).fetchone()[0]==1
        assert get_db().execute("SELECT count(*) FROM entity_audit WHERE kind IN ('entity-merged','entity-unmerged')").fetchone()[0]==2
    def worker():
        with app.app_context():return n.extract(eid,reprocess=True)['mentions_created']
    with ThreadPoolExecutor(max_workers=2) as pool:assert list(pool.map(lambda _:worker(),range(2)))==[0,0]
    writer=authorization(app,'write')[2];reader=authorization(app,'read')[2]
    assert client.post(f'/api/v1/entities/{a}/merge',headers=reader,json={'target_id':b,'expected_revision':3,'reason':'test','reviewed':True}).status_code==403
    assert client.get(f'/entities/{a}').status_code==200


def test_graph_caps_extraction_bounds_and_literal_search(app,client):
    eid=capture(app,'CVE-2026-123456');wid,qid=context(app,eid)
    with app.app_context():
        n.extract();center=get_db().execute("SELECT id FROM entities WHERE kind='cve'").fetchone()[0]
        with e.storage_lock(),r.transaction() as db:
            targets=[n.ensure(db,'product','製品'+str(index)) for index in range(205)]
        for target in targets:n.save_relation(wid,{'source_id':center,'target_id':target,'predicate':'hypothetical-reference','quotation_id':qid,'label':'hypothesis'})
        graph=n.graph(center,wid);assert len(graph['nodes'])==200 and len(graph['edges'])<=400 and graph['truncated']
        assert len(n.graph(center,wid,depth=0)['nodes'])==1
        bounded=n.graph(center,wid,limit=3);assert len(bounded['nodes'])==3 and bounded['truncated']
        long=capture(app,' '.join('CVE-2026-'+str(10000+i) for i in range(550)),source='many-cves')
        assert n.extract(long)['mentions_created']==500
        assert get_db().execute('SELECT truncated FROM entity_extractions WHERE evidence_id=?',(long,)).fetchone()[0]==1
        assert n.extract(long,reprocess=True)['mentions_created']==0
        assert get_db().execute('SELECT count(*) FROM entity_mentions WHERE evidence_id=?',(long,)).fetchone()[0]==500
        # No partial identifier from a malformed address or scoped IPv6 is recorded.
        bad=capture(app,'fe80::1%eth0 1.2.3.999 AS4294967296 CVE-2026-12',source='malformed')
        assert n.extract(bad)['mentions_created']==0
    reader=authorization(app,'read')[2]
    result=client.get(f'/api/v1/entities/{center}/graph?workspace={wid}&limit=3',headers=reader);assert result.status_code==200 and result.json['data']['truncated']
    assert client.get(f'/entities/{center}?workspace={wid}').status_code==200


def test_v7_migration_entity_bundle_integrity_and_recovery(tmp_path):
    data=tmp_path/'data';data.mkdir();dbpath=data/'feeds.sqlite3';db=connect(dbpath);db.executescript(Path('tests/fixtures/v7_schema.sql').read_text());db.close()
    bundle=tmp_path/'v7-bundle';backup_bundle(dbpath,bundle);assert json.loads((bundle/'manifest.json').read_text())['schema']==7
    init_database(dbpath);app=create_app({'DATA_DIR':str(data),'TESTING':True})
    eid=capture(app,'a.example 2001:db8::1');wid,qid=context(app,eid)
    with app.app_context():
        n.extract();db=get_db();ids=[row[0] for row in db.execute('SELECT id FROM entities ORDER BY id')]
        rid=n.save_relation(wid,{'source_id':ids[0],'target_id':ids[1],'quotation_id':qid,'predicate':'reported-association'})
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    newbundle=tmp_path/'v8-bundle';backup_bundle(dbpath,newbundle);restored=tmp_path/'restored'/'feeds.sqlite3';restore_bundle(newbundle,restored)
    recovered=create_app({'DATA_DIR':str(restored.parent),'TESTING':True})
    with recovered.app_context():
        assert n.extract(eid,reprocess=True)['mentions_created']==0
        assert n.relation(rid)['predicate']=='reported-association'
        assert get_db().execute('SELECT count(*) FROM entity_mentions').fetchone()[0]==2
        assert get_db().execute('PRAGMA user_version').fetchone()[0]==19
        assert not get_db().execute('PRAGMA foreign_key_check').fetchall()
    oldrestore=tmp_path/'old-restored'/'feeds.sqlite3';restore_bundle(bundle,oldrestore);db=connect(oldrestore);assert db.execute('PRAGMA user_version').fetchone()[0]==19;db.close()
    # A semantic anchor corruption is rejected even when DB bytes are internally consistent.
    with app.app_context():
        with get_db() as db:db.execute("UPDATE entity_mentions SET original='not the source'")
    with pytest.raises(ValueError):backup_bundle(dbpath,tmp_path/'corrupt-bundle')


def test_ui_unscoped_navigation_and_localized_form_values(app,client):
    from html.parser import HTMLParser
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.urls=[];self.options=[]
        def handle_starttag(self,tag,attrs):
            values=dict(attrs)
            if tag=='a' and values.get('href','').startswith('/entities'):self.urls.append(values['href'])
            if tag=='option':self.options.append(values.get('value'))
    with app.app_context():identifier=n.create({'kind':'domain','value':'example.com'})
    response=client.get('/entities?workspace=&kind=');assert response.status_code==200
    parsed=Links();parsed.feed(response.text)
    assert 'domain' in parsed.options and 'ドメイン' not in parsed.options
    assert f'/entities/{identifier}' in parsed.urls
    for url in parsed.urls:assert client.get(url).status_code==200,url
    assert client.get('/entities/relations?entity=&workspace=').status_code==200
    result=post(client,'/entities/create',{'kind':'organization','value':'画面から登録','author':'local-user'})
    assert result.status_code==302
    assert client.get(result.headers['Location']).status_code==200
