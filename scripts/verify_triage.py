"""Real HTTP acceptance in a disposable or explicitly isolated verification library."""
import argparse,json,sys
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import urllib.request,urllib.error
if __file__!='<stdin>':sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from werkzeug.serving import make_server
from feedastrolabe import create_app,collection,triage as t
from feedastrolabe.db import get_db,connect
from feedastrolabe.keys import issue_key
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--serve-port',type=int,default=0);parser.add_argument('--data-dir',type=Path);parser.add_argument('--check-state',action='store_true');args=parser.parse_args()
    if args.data_dir and not args.data_dir.name.endswith('-verify'):parser.error('Use a separate directory ending in -verify')
    if args.check_state and not args.data_dir:parser.error('A verification directory is required')
    if args.serve_port and not 1024<=args.serve_port<=65535:parser.error('Use a local test port')
    context=nullcontext(str(args.data_dir)) if args.data_dir else TemporaryDirectory(prefix='feedastrolabe-triage-')
    with context as directory:
        app=create_app({'DATA_DIR':directory})
        marker=Path(directory)/'triage-state.json'
        if args.check_state:
            state=json.loads(marker.read_text())
            with app.app_context():
                db=get_db();assert db.execute('PRAGMA user_version').fetchone()[0]==11
                assert db.execute('SELECT count(*) FROM watch_events WHERE version_id=?',(state['version_id'],)).fetchone()[0]==2
                assert db.execute('SELECT included,seen FROM watch_events WHERE id=?',(state['event_id'],)).fetchone()[:]==(1,1)
                assert t.group(state['group_id'])['suppressed']==1
                assert t.process()['events_created']==0
                assert not db.execute('PRAGMA foreign_key_check').fetchall()
            print('PASS: schema11 immutable rule/events/seen/group suppression retained after container recreation');return
        old_fetch=collection.fetch
        def fixture(url,*unused):
            publisher='Publisher A' if url.endswith('/a') else 'Publisher B'
            rss=f'<rss version="2.0"><channel><title>{publisher}</title><item><guid>one</guid><title>生成AI Security signal</title><link>https://example.com/signal?id=1&amp;utm_source={publisher[-1]}</link><description>Security 100% research</description></item></channel></rss>'.encode()
            return rss,{'url':url,'etag':None,'modified':None}
        collection.fetch=fixture
        with app.app_context():_,token=issue_key('ephemeral triage acceptance','write',1);_,read=issue_key('ephemeral read acceptance','read',1)
        server=make_server('127.0.0.1',args.serve_port,app);thread=Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
        def request(method,path,body=None,key=None):
            data=json.dumps(body).encode() if body is not None else None
            req=urllib.request.Request(base+'/api/v1'+path,data=data,method=method,headers={'Authorization':'Bearer '+(key or token),'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(req,timeout=15) as response:
                    raw=response.read();return response.status,json.loads(raw) if raw else None
            except urllib.error.HTTPError as response:return response.code,json.load(response)
        try:
            ids=[request('POST','/feeds',{'url':'https://example.com/triage-fixture/'+part})[1]['data']['id'] for part in ('a','b')]
            wid=request('POST','/workspaces',{'title':'生成AI・セキュリティ監視','purpose':'出典を保持して重要な新着を整理する'})[1]['data']['id']
            for fid in ids:assert request('POST',f'/workspaces/{wid}/feeds/{fid}')[0]==204
            body={'name':'Security signal','query':{'any':[{'field':'text','op':'contains','value':'100%'}]},'exclusion':{},'priority':'high','reason':'調査中のテーマに関連'}
            result=request('POST',f'/workspaces/{wid}/watchlists',body);assert result[0]==201;rule_id=result[1]['data']['id'];version_id=result[1]['data']['version_id']
            assert request('POST',f'/watchlists/{rule_id}/reprocess',key=read)[0]==403
            assert request('POST',f'/watchlists/{rule_id}/reprocess')[1]['data']['events_created']==2
            assert request('POST',f'/watchlists/{rule_id}/process')[1]['data']['events_created']==0
            items=request('GET',f'/workspaces/{wid}/digest')[1]['data'];assert len(items)==2 and all(item['included'] for item in items)
            event_id=items[0]['id'];assert request('PATCH',f'/watch-events/{event_id}',{'seen':True})[1]['data']['seen']
            groups=request('GET','/duplicate-groups')[1]['data'];assert len(groups)==2
            group_id=groups[0]['id'];assert len(request('GET',f'/duplicate-groups/{group_id}/members')[1]['data'])==2
            assert request('PATCH',f'/duplicate-groups/{group_id}',{'suppressed':True})[0]==200
            assert request('PATCH',f'/watchlists/{rule_id}',{'expected_revision':0,'priority':'low'})[0]==409
            with app.app_context():
                t.process();assert t.group(group_id)['suppressed']==1
                bundle=Path(directory)/'bundle';backup_bundle(app.config['DATABASE'],bundle)
                restored=Path(directory)/'restored'/'feeds.sqlite3';restore_bundle(bundle,restored)
                db=connect(restored);assert db.execute('SELECT count(*) FROM watch_events').fetchone()[0]==2;assert db.execute('PRAGMA user_version').fetchone()[0]==11;db.close()
            state={'workspace_id':wid,'rule_id':rule_id,'version_id':version_id,'event_id':event_id,'group_id':group_id};marker.write_text(json.dumps(state))
            for path in [f'/triage/{wid}',f'/triage/watchlists/{rule_id}',f'/triage/groups/{group_id}']:
                with urllib.request.urlopen(base+path) as response:assert response.status==200 and b'<script' not in response.read()
            print('PASS: live HTTP literal query, scope, digest, seen, duplicate provenance/undo, stale revision, v7 bundle restore')
            if args.serve_port:
                print('UI fixture: '+base+f'/triage/{wid}',flush=True)
                try:thread.join()
                except KeyboardInterrupt:pass
        finally:
            server.shutdown();thread.join(timeout=5);collection.fetch=old_fetch

if __name__=='__main__':main()
