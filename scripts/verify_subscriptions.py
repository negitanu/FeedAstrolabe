"""Live HTTP acceptance in an ephemeral library, never the user's database."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import urllib.error
import urllib.request

if __file__ != '<stdin>':
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from werkzeug.serving import make_server
from feedastrolabe import create_app, collection, observation
from feedastrolabe.db import get_db
from feedastrolabe.keys import issue_key

RSS=b'<rss version="2.0"><channel><title>Fixture</title><item><guid>one</guid><title>Saved</title></item></channel></rss>'


def main():
    original=collection.fetch
    def fixture(url,etag=None,modified=None):
        if url.endswith('/repaired'):
            assert etag is None and modified is None
        return RSS,{'url':url,'etag':'fixture','modified':None}
    collection.fetch=fixture
    try:
        with TemporaryDirectory(prefix='feedastrolabe-management-') as directory:
            app=create_app({'DATA_DIR':directory})
            with app.app_context():
                _,token=issue_key('ephemeral management acceptance','write',1)
                _,readonly=issue_key('ephemeral read acceptance','read',1)
            server=make_server('127.0.0.1',0,app)
            worker=Thread(target=server.serve_forever,daemon=True);worker.start()
            base='http://127.0.0.1:'+str(server.server_port)+'/api/v1'
            def request(method,path,body=None,key=None):
                data=json.dumps(body).encode() if body is not None else None
                req=urllib.request.Request(base+path,data=data,method=method,headers={'Authorization':'Bearer '+(key or token),'Content-Type':'application/json'})
                try:
                    with urllib.request.urlopen(req,timeout=30) as result:
                        raw=result.read();return result.status,json.loads(raw) if raw else None
                except urllib.error.HTTPError as result:
                    return result.code,json.load(result)
            try:
                status,response=request('POST','/feeds',{'url':'https://example.com/feed'})
                assert status==201
                source=response['data']['id']
                path='/feeds/'+str(source)
                assert request('PATCH','/articles/1',{'is_read':True,'is_starred':True})[0]==200
                assert request('PATCH',path,{'folder':'Denied'},key=readonly)[0]==403
                assert request('PATCH',path,{'url':'https://example.com/repaired','folder':'New','enabled':False})[0]==200
                assert request('POST',path+'/refresh')[1]['data']['succeeded']==1
                assert request('GET','/articles/1')[1]['data']['is_starred']
                assert request('PATCH',path,{'folder':'Wrong','poll_interval':1})[0]==400
                assert request('GET',path)[1]['data']['folder']=='New'
                status,page=request('POST','/feeds',{'source_type':'page','url':'https://example.com/page','selector':'h1'})
                assert status==201
                pagepath='/feeds/'+str(page['data']['id'])
                for _ in range(2):assert request('POST',pagepath+'/refresh')[0]==202
                with app.app_context():
                    db=get_db()
                    assert db.execute('SELECT count(*) FROM page_jobs').fetchone()[0]==1
                    old=dict(db.execute('SELECT * FROM feeds WHERE id=?',(page['data']['id'],)).fetchone())
                    observation.save_observation(old,'Initial')
                assert request('PATCH',pagepath,{'url':'https://example.com/changed','selector':'main'})[0]==200
                with app.app_context():assert not observation.save_observation(old,'Stale')
                assert request('DELETE',pagepath)[0]==204
                assert request('POST',pagepath+'/refresh')[0]==404
                assert request('DELETE',path)[0]==204
                with app.app_context():
                    db=get_db()
                    assert db.execute('SELECT count(*) FROM articles').fetchone()[0]==0
                    assert db.execute('SELECT count(*) FROM page_jobs').fetchone()[0]==0
                    assert not db.execute('PRAGMA foreign_key_check').fetchall()
                print('PASS live HTTP: edit/refresh, preserved flags, read scope, atomic invalid patch, page queue/revision/delete cascade')
            finally:
                server.shutdown();worker.join(5);server.server_close()
    finally:
        collection.fetch=original


if __name__=='__main__':main()
