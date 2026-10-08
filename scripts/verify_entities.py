"""Actual HTTP entity/assessment acceptance; disposable or isolated verification DB."""
import argparse,json,sys
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import urllib.request,urllib.error
if __file__!='<stdin>':sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from werkzeug.serving import make_server
from feedastrolabe import create_app,collection,entities as n
from feedastrolabe.db import get_db,connect
from feedastrolabe.keys import issue_key
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--serve-port',type=int,default=0);parser.add_argument('--data-dir',type=Path);parser.add_argument('--check-state',action='store_true');args=parser.parse_args()
    if args.data_dir and not args.data_dir.name.endswith('-verify'):parser.error('Use a separate directory ending in -verify')
    if args.check_state and not args.data_dir:parser.error('Use a verification directory')
    if args.serve_port and not 1024<=args.serve_port<=65535:parser.error('Use a local test port')
    context=nullcontext(str(args.data_dir)) if args.data_dir else TemporaryDirectory(prefix='feedastrolabe-entities-')
    with context as directory:
        app=create_app({'DATA_DIR':directory});marker=Path(directory)/'entities-state.json'
        if args.check_state:
            state=json.loads(marker.read_text())
            with app.app_context():
                db=get_db();assert db.execute('PRAGMA user_version').fetchone()[0]==13
                assert n.root(state['original_organization'])==state['merged_organization']
                assert n.mention(state['mention_id'])['original_entity_id']==state['original_organization']
                assert n.mention(state['mention_id'])['status']=='confirmed'
                assert n.relation(state['relation_id'])['revision']==2
                assert db.execute('SELECT count(*) FROM relations').fetchone()[0]==3
                assert db.execute("SELECT count(*) FROM entity_audit WHERE kind='entity-unmerged'").fetchone()[0]==1
                assert n.extract()['mentions_created']==0 and not db.execute('PRAGMA foreign_key_check').fetchall()
            print('PASS: schema13 original mentions, merge/unmerge audit, quoted relation revisions and idempotent extraction retained after recreation');return
        old_fetch=collection.fetch
        text_a='ACME a.example observed 2001:db8::1 CVE-2026-123456 AS64512 https://github.com/Owner/Repo'
        text_b='b.example observed 2001:0DB8:0000:0000:0000:0000:0000:0001'
        def fixture(url,*unused):
            rss=f'<rss version="2.0"><channel><title>OSINT Fixture</title><item><guid>a</guid><title>観測 A</title><description>{text_a}</description></item><item><guid>b</guid><title>観測 B</title><description>{text_b}</description></item></channel></rss>'.encode()
            return rss,{'url':url,'etag':None,'modified':None}
        collection.fetch=fixture
        with app.app_context():_,token=issue_key('ephemeral entity acceptance','write',1);_,read=issue_key('ephemeral read acceptance','read',1)
        server=make_server('127.0.0.1',args.serve_port,app);thread=Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
        def request(method,path,body=None,key=None):
            req=urllib.request.Request(base+'/api/v1'+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+(key or token),'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(req,timeout=15) as response:
                    raw=response.read();return response.status,json.loads(raw) if raw else None
            except urllib.error.HTTPError as response:return response.code,json.load(response)
        try:
            assert request('POST','/feeds',{'url':'https://example.com/entity-fixture'})[0]==201
            wid=request('POST','/workspaces',{'title':'OSINT：根拠付き対象と関係','purpose':'元表記を確認し、観測と推論を区別する'})[1]['data']['id']
            assert request('POST',f'/workspaces/{wid}/feeds/1')[0]==204
            evidence=request('GET','/evidence')[1]['data'];qids=[]
            for item in sorted(evidence,key=lambda item:item['id']):
                assert request('POST',f'/evidence/{item["id"]}/extract-entities',key=read)[0]==403
                assert request('POST',f'/evidence/{item["id"]}/extract-entities')[0]==200
                text=request('GET',f'/evidence/{item["id"]}')[1]['data']['text']
                qids.append(request('POST',f'/workspaces/{wid}/quotations',{'evidence_id':item['id'],'start':0,'end':len(text),'quote':text})[1]['data']['id'])
            ips=request('GET','/entities?kind=ip')[1]['data'];assert len(ips)==1;ip=ips[0]['id']
            mentions=request('GET',f'/entities/{ip}/mentions?workspace={wid}')[1]['data'];assert len(mentions)==2 and len({item['original'] for item in mentions})==2
            a=request('GET','/entities?q=a.example&kind=domain')[1]['data'][0]['id'];b=request('GET','/entities?q=b.example&kind=domain')[1]['data'][0]['id']
            relation_ids=[]
            for source,qid in [(a,qids[0]),(b,qids[1])]:
                body={'source_id':source,'target_id':ip,'quotation_id':qid,'predicate':'observed-address','label':'source-claim','confidence':'unknown'}
                result=request('POST',f'/workspaces/{wid}/relations',body);assert result[0]==201;relation_ids.append(result[1]['data']['id'])
            rid=relation_ids[0];assert request('PATCH',f'/relations/{rid}',{'expected_revision':1,'confidence':'low'})[0]==200
            assert request('PATCH',f'/relations/{rid}',{'expected_revision':1,'confidence':'high'})[0]==409
            org=request('POST','/entities',{'kind':'organization','value':'ACME'})[1]['data']['id'];other=request('POST','/entities',{'kind':'organization','value':'ACME Labs'})[1]['data']['id']
            assert request('POST',f'/entities/{org}/aliases',{'value':'ACME','reviewed':True})[0]==201
            mention=request('POST','/mentions',{'entity_id':org,'evidence_id':1,'start':0,'end':4,'original':'ACME'})[1]['data']['id']
            assert request('PATCH',f'/mentions/{mention}',{'expected_revision':1,'status':'rejected'})[0]==200
            assert request('POST','/evidence/1/extract-entities')[1]['data']['mentions_created']==0
            assert request('PATCH',f'/mentions/{mention}',{'expected_revision':2,'status':'confirmed'})[0]==200
            assert request('POST',f'/workspaces/{wid}/relations',{'source_id':org,'target_id':a,'quotation_id':qids[0],'predicate':'references','label':'source-claim'})[0]==201
            assert request('POST',f'/entities/{org}/merge',{'target_id':other,'expected_revision':1,'reviewed':True,'reason':'確認した別名'})[0]==200
            assert request('GET',f'/entities/{org}')[1]['data']['root_id']==other
            assert request('POST',f'/entities/{org}/unmerge',{'expected_revision':2,'reason':'統合を戻せることを確認'})[0]==200
            assert request('POST',f'/entities/{org}/merge',{'target_id':other,'expected_revision':3,'reviewed':True,'reason':'確認済みの代表を設定'})[0]==200
            graph=request('GET',f'/entities/{ip}/graph?workspace={wid}')[1]['data'];assert len(graph['edges'])==3 and len(graph['nodes'])<=200
            assert request('GET',f'/entities/{other}/graph?workspace={wid}')[0]==200
            assert request('GET',f'/entities/{org}/timeline?workspace={wid}')[0]==200
            with app.app_context():
                bundle=Path(directory)/'bundle';backup_bundle(app.config['DATABASE'],bundle);restored=Path(directory)/'restored'/'feeds.sqlite3';restore_bundle(bundle,restored)
                db=connect(restored);assert db.execute('SELECT count(*) FROM relations').fetchone()[0]==3;assert db.execute('PRAGMA user_version').fetchone()[0]==13;db.close()
            state={'workspace_id':wid,'ip_id':ip,'original_organization':org,'merged_organization':other,'mention_id':mention,'relation_id':rid};marker.write_text(json.dumps(state))
            for path in ['/entities',f'/entities/{ip}?workspace={wid}',f'/entities/{other}?workspace={wid}',f'/entities/relations/{rid}',f'/entities/relations/new/{wid}']:
                with urllib.request.urlopen(base+path) as response:assert response.status==200 and b'<script' not in response.read()
            print('PASS: actual HTTP normalized originals, scoped mentions, quoted assessments, conflict, merge/undo audit, graph and v8 bundle')
            if args.serve_port:
                print('UI fixture: '+base+f'/entities/{ip}?workspace={wid}',flush=True)
                try:thread.join()
                except KeyboardInterrupt:pass
        finally:server.shutdown();thread.join(timeout=5);collection.fetch=old_fetch

if __name__=='__main__':main()
