"""Live HTTP research acceptance using only an ephemeral fixture library."""
import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import urllib.error
import urllib.request

if __file__ != '<stdin>':
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

from werkzeug.serving import make_server
from feedastrolabe import create_app, collection
from feedastrolabe.db import connect, get_db
from feedastrolabe.keys import issue_key
from feedastrolabe.evidence_backup import backup_bundle as backup, restore_bundle as restore

RSS=b'<rss version="2.0"><channel><title>Security fixture</title><item><guid>one</guid><title>Security bulletin</title><description>Research fixture only</description></item></channel></rss>'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--serve-port',type=int,default=0,help='Keep the fixture UI available for manual browser review')
    args=parser.parse_args()
    if args.serve_port and not 1024<=args.serve_port<=65535:
        parser.error('Use a local test port from 1024 to 65535')
    original=collection.fetch
    collection.fetch=lambda url,*args:(RSS,{'url':url,'etag':None,'modified':None})
    try:
        with TemporaryDirectory(prefix='feedastrolabe-research-') as directory:
            app=create_app({'DATA_DIR':directory})
            with app.app_context():
                _,token=issue_key('ephemeral research acceptance','write',1)
                _,readonly=issue_key('ephemeral read acceptance','read',1)
            server=make_server('127.0.0.1',args.serve_port,app)
            worker=Thread(target=server.serve_forever,daemon=True);worker.start()
            base='http://127.0.0.1:'+str(server.server_port)+'/api/v1'
            def request(method,path,body=None,key=None):
                data=json.dumps(body).encode() if body is not None else None
                req=urllib.request.Request(base+path,data=data,method=method,headers={'Authorization':'Bearer '+(key or token),'Content-Type':'application/json'})
                try:
                    with urllib.request.urlopen(req,timeout=15) as response:
                        raw=response.read();return response.status,json.loads(raw) if raw else None
                except urllib.error.HTTPError as response:
                    return response.code,json.load(response)
            try:
                status,feed=request('POST','/feeds',{'url':'https://example.com/research-fixture'})
                assert status==201
                source=feed['data']['id']
                status,first=request('POST','/workspaces',{'title':'生成 AI のセキュリティ調査','purpose':'公開情報から脅威と対策の変化を追う。','questions':'どの情報が検証済みか？\n次に確認すべき根拠は何か？','classification':'restricted'})
                assert status==201
                wid=first['data']['id'];path='/workspaces/'+str(wid)
                other=request('POST','/workspaces',{'title':'OSINT・ネットワーク情報','purpose':'関連する公開情報を収集する。'})[1]['data']['id']
                assert request('POST',path+'/feeds/'+str(source))[0]==204
                for case in [wid,other]:
                    assert request('POST',f'/workspaces/{case}/articles/1')[0]==204
                assert request('PATCH','/articles/1',{'is_read':True,'is_starred':True})[0]==200
                tag=request('POST','/tags',{'name':'セキュリティ'})[1]['data']['id']
                for parent in [path,'/articles/1']:
                    assert request('POST',parent+'/tags/'+str(tag))[0]==204
                assert [a['id'] for a in request('GET',f'/articles?workspace={wid}&tag={tag}')[1]['data']]==[1]
                status,memo=request('POST',path+'/notes',{'title':'調査の仮説と確認事項','body':'## 確認事項\n\n- 情報源を照合する\n- 主張と事実を分ける','label':'hypothesis'})
                assert status==201
                nid=memo['data']['id'];note_path='/notes/'+str(nid)
                assert request('POST',note_path+'/tags/'+str(tag))[0]==204
                assert request('PATCH',note_path,{'expected_revision':1,'body':'## 確認した事実\n\n**検証用データ**です。実際の調査結果ではありません。\n\n[参照](https://example.com/report)\n\n<script>unsafe</script>\n\n![beacon](https://evil.example/beacon)','label':'fact'})[0]==200
                assert request('PATCH',note_path,{'expected_revision':1,'body':'stale'})[0]==409
                assert request('PATCH',note_path,{'expected_revision':2,'body':'forbidden'},key=readonly)[0]==403
                assert len(request('GET',note_path+'/revisions')[1]['data'])==2
                assert request('PATCH',path,{'archived':True})[0]==200
                assert request('POST',path+'/articles/1')[0]==409
                assert request('GET','/articles/1')[1]['data']['is_starred'] is True
                assert len(request('GET',f'/workspaces/{other}/articles')[1]['data'])==1
                assert request('PATCH',path,{'archived':False})[0]==200
                with app.app_context():
                    snapshot=Path(directory)/'backup.sqlite3';backup(app.config['DATABASE'],snapshot)
                    destination=Path(directory)/'restored'/'feeds.sqlite3';restore(snapshot,destination)
                    with connect(destination) as db:
                        assert db.execute('PRAGMA user_version').fetchone()[0]==9
                        assert db.execute('SELECT count(*) FROM note_revisions').fetchone()[0]==2
                        assert db.execute('SELECT count(*) FROM workspace_articles').fetchone()[0]==2
                        assert not db.execute('PRAGMA foreign_key_check').fetchall()
                for route in ['/workspaces',f'/workspaces/{wid}',f'/workspaces/notes/{nid}','/?article=1']:
                    with urllib.request.urlopen(base.removesuffix('/api/v1')+route,timeout=10) as response:
                        html=response.read().decode()
                        assert response.status==200 and '<script>' not in html and '<img' not in html
                print('PASS: live HTTP research links, tagged union, revisions/conflicts, scopes, archive, UI and v5 backup/restore',flush=True)
                if args.serve_port:
                    print('Fixture UI: http://127.0.0.1:'+str(server.server_port)+'/workspaces (ephemeral, no user data)',flush=True)
                    try:
                        worker.join()
                    except KeyboardInterrupt:
                        pass
            finally:
                server.shutdown();worker.join(timeout=5);server.server_close()
    finally:
        collection.fetch=original


if __name__=='__main__':
    main()
