"""Live evidence acceptance in a disposable library; renderer uses private IPC."""
import argparse
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import urllib.error
import urllib.request

if __file__!='<stdin>':sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from werkzeug.serving import make_server
from pypdf import PdfWriter
from feedastrolabe import create_app,collection
from feedastrolabe.db import connect
from feedastrolabe.keys import issue_key
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle
from feedastrolabe import evidence as e

RSS=b'<rss version="2.0"><channel><title>Fixture publisher</title><item><guid>one</guid><title>Saved evidence</title><description>Original research text</description></item></channel></rss>'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--serve-port',type=int,default=0);parser.add_argument('--skip-attachments',action='store_true',help='UI fixture only; does not count as PDF extraction acceptance');args=parser.parse_args()
    if args.serve_port and not 1024<=args.serve_port<=65535:parser.error('Use a local test port')
    original=collection.fetch;collection.fetch=lambda url,*args:(RSS,{'url':url,'etag':None,'modified':None})
    try:
        with TemporaryDirectory(prefix='feedastrolabe-evidence-') as directory:
            app=create_app({'DATA_DIR':directory})
            with app.app_context():
                _,token=issue_key('ephemeral evidence acceptance','write',1);_,readonly=issue_key('ephemeral read acceptance','read',1)
            server=make_server('127.0.0.1',args.serve_port,app);thread=Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
            def request(method,path,body=None,key=None,raw=None,content_type='application/json'):
                data=raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
                req=urllib.request.Request(base+'/api/v1'+path,data=data,method=method,headers={'Authorization':'Bearer '+(key or token),'Content-Type':content_type})
                try:
                    with urllib.request.urlopen(req,timeout=55) as result:
                        content=result.read()
                        return result.status,json.loads(content) if content and 'json' in result.headers['Content-Type'] else content
                except urllib.error.HTTPError as result:return result.code,json.load(result)
            try:
                assert request('POST','/feeds',{'url':'https://example.com/evidence-fixture'})[0]==201
                wid=request('POST','/workspaces',{'title':'根拠・出典の確認','purpose':'取得時点の内容と引用を確実に保持する。','classification':'restricted'})[1]['data']['id']
                item=request('GET','/evidence?article=1')[1]['data'][0];eid=item['id']
                assert request('POST',f'/workspaces/{wid}/evidence/{eid}')[0]==204
                text=request('GET',f'/evidence/{eid}')[1]['data']['text']
                assert request('POST',f'/workspaces/{wid}/quotations',{'evidence_id':eid,'start':0,'end':8,'quote':text[:8]})[0]==201
                assert request('POST',f'/workspaces/{wid}/quotations',{'evidence_id':eid,'start':0,'end':8,'quote':'incorrect'})[0]==400
                assert request('POST',f'/articles/1/evidence',key=readonly)[0]==403
                assert request('GET',f'/evidence/{eid}/download',key=readonly)[1]==text.encode()
                if not args.skip_attachments:
                    pdf=PdfWriter();pdf.add_blank_page(width=200,height=200);buffer=io.BytesIO();pdf.write(buffer)
                    for filename,mime,raw in [('note.txt','text/plain','日本語の資料\n<script>inactive</script>'.encode()),('note.md','text/markdown',b'# Research note'),('note.pdf','application/pdf',buffer.getvalue())]:
                        boundary='FeedAstrolabeFixtureBoundary'
                        multipart=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n').encode()+raw+f'\r\n--{boundary}--\r\n'.encode()
                        response=request('POST',f'/workspaces/{wid}/attachments',raw=multipart,content_type='multipart/form-data; boundary='+boundary)
                        assert response[0]==201,response
                assert request('DELETE','/feeds/1')[0]==204
                saved=request('GET',f'/evidence/{eid}')[1]['data'];assert saved['feed_id'] is None and saved['article_id'] is None and saved['text']==text
                with app.app_context():
                    bundle=Path(directory)/'backup-bundle';backup_bundle(app.config['DATABASE'],bundle)
                    restored=Path(directory)/'restored'/'feeds.sqlite3';restore_bundle(bundle,restored)
                    with connect(restored) as db:
                        assert db.execute('SELECT count(*) FROM quotations').fetchone()[0]==1
                        assert db.execute('PRAGMA user_version').fetchone()[0]==7
                    blob=bundle/'evidence-blobs'/saved['blob_hash'];blob.unlink()
                    try:restore_bundle(bundle,Path(directory)/'invalid-restore'/'feeds.sqlite3');raise AssertionError('Missing blob accepted')
                    except ValueError:pass
                for path in ['/evidence',f'/evidence/{eid}',f'/workspaces/{wid}']:
                    with urllib.request.urlopen(base+path) as result:
                        assert result.status==200 and '<script>' not in result.read().decode()
                print('PASS: live HTTP immutable evidence, quotes, detached source, scopes, download, bundle integrity'+(' (attachment extraction intentionally skipped)' if args.skip_attachments else ', actual text/Markdown/PDF IPC extraction'),flush=True)
                if args.serve_port:
                    print('Fixture UI: '+base+'/evidence',flush=True)
                    try:thread.join()
                    except KeyboardInterrupt:pass
            finally:server.shutdown();thread.join(timeout=5);server.server_close()
    finally:collection.fetch=original


if __name__=='__main__':main()
