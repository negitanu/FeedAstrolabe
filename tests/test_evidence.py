import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from datetime import datetime,timezone

import pytest
from pypdf import PdfWriter

from feedastrolabe import create_app,collection,observation
from feedastrolabe.db import get_db,connect,init_database
from feedastrolabe import evidence as e,research as r
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle,validate_bundle
from feedastrolabe.maintenance import backup,restore
from test_reader import app,client,post,subscribe,RSS,META
from test_phase_two import authorization


@pytest.fixture
def writer(app):return authorization(app,'write')[2]


@pytest.fixture
def parser(app):
    with TemporaryDirectory(prefix='fa-parse-',dir='/tmp') as directory:
        endpoint=Path(directory)/'renderer.sock'
        process=subprocess.Popen([sys.executable,'-m','feedastrolabe.renderer','--socket',str(endpoint)],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            until=time.monotonic()+10
            while not endpoint.exists() and time.monotonic()<until:
                assert process.poll() is None
                time.sleep(.05)
            assert endpoint.exists()
            app.config['RENDER_SOCKET']=str(endpoint)
            yield
        finally:
            if process.poll() is None:os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=10)


def case(app):
    with app.app_context():return r.create_workspace({'title':'Case'})


def test_ingest_immutable_versions_quote_and_source_delete(app,client,writer,monkeypatch):
    subscribe(client);wid=case(app)
    with app.app_context():
        db=get_db();first=dict(db.execute('SELECT * FROM evidence WHERE article_id=1').fetchone())
        assert first['method']=='feed-derived' and first['published_at'] and first['captured_at']
        text=first['text'];assert 'Hello' in text
        eid=first['id'];quote=text[:5]
        qid=e.quotation(wid,{'evidence_id':eid,'start':0,'end':5,'quote':quote})
        assert e.quotation(wid,{'evidence_id':eid,'start':0,'end':5,'quote':quote})==qid
        e.pin('workspace',wid,eid)
    for _ in range(2):post(client,'/refresh')
    with app.app_context():assert get_db().execute('SELECT count(*) FROM evidence').fetchone()[0]==2
    monkeypatch.setattr(collection,'fetch',lambda *args:(RSS.replace(b'Hello 100%',b'Revised 100%'),META))
    post(client,'/refresh')
    with app.app_context():
        rows=get_db().execute('SELECT * FROM evidence WHERE article_id=1 ORDER BY id').fetchall()
        assert len(rows)==2 and rows[0]['text']==text and rows[1]['version']==2
        assert e.read_blob(rows[0]['blob_hash'])==text.encode()
    assert client.delete('/api/v1/feeds/1',headers=writer).status_code==204
    with app.app_context():
        item=e.find(eid);assert item['article_id'] is None and item['feed_id'] is None and item['publisher']=='Example News'
        assert item['text']==text
        assert get_db().execute('SELECT quote FROM quotations WHERE id=?',(qid,)).fetchone()[0]==quote
    response=client.get(f'/api/v1/evidence/{eid}/download',headers=writer)
    assert response.status_code==200 and response.data==text.encode() and 'attachment;' in response.headers['Content-Disposition']
    assert response.mimetype=='application/octet-stream'
    assert client.get(f'/api/v1/evidence/{eid}/download').status_code==401


def test_page_baseline_changes_retention_and_backfill(app,client,writer):
    with app.app_context():
        fid=observation.add_page('https://example.com/evidence','main')
        feed=dict(get_db().execute('SELECT * FROM feeds WHERE id=?',(fid,)).fetchone())
        for text in ['Baseline','Baseline','Changed','Baseline']:assert observation.save_observation(feed,text)
        db=get_db();assert [row[0] for row in db.execute("SELECT text FROM evidence WHERE method='page-selected-text' ORDER BY id")]==['Baseline','Changed','Baseline']
        wid=r.create_workspace({'title':'Pinned page'});eid=db.execute("SELECT id FROM evidence WHERE text='Changed'").fetchone()[0]
        e.pin('workspace',wid,eid)
        article_id=db.execute("SELECT id FROM articles WHERE guid='page:1'").fetchone()[0]
        backfilled=e.article_capture(article_id)
        assert e.find(backfilled)['method']=='article-backfill-now'
        assert e.find(backfilled)['captured_at']>=e.find(eid)['captured_at']
        with db:db.execute('DELETE FROM articles WHERE id=?',(article_id,))
        assert e.find(eid)['article_id'] is None
        assert e.find(eid)['text']=='Changed'


def test_quote_validation_scope_archive_and_input_atomicity(app,client,writer):
    subscribe(client);wid=case(app)
    response=client.post('/api/v1/articles/1/evidence',headers=writer)
    assert response.status_code==201
    item=response.json['data'];eid=item['id'];read=authorization(app,'read')[2]
    for body in [{'evidence_id':eid,'start':0,'end':5,'quote':'wrong'},{'evidence_id':eid,'start':False,'end':5,'quote':'Hello'},{'evidence_id':eid,'start':0,'end':1000000,'quote':'Hello'},{'evidence_id':eid,'start':0,'end':5,'quote':'Hello','unknown':1}]:
        assert client.post(f'/api/v1/workspaces/{wid}/quotations',headers=writer,json=body).status_code==400
    assert client.post(f'/api/v1/workspaces/{wid}/quotations',headers=read,json={}).status_code==403
    assert client.post(f'/api/v1/workspaces/{wid}/evidence/{eid}',headers=read).status_code==403
    assert client.post(f'/api/v1/workspaces/{wid}/evidence/{eid}',headers=writer).status_code==204
    assert [item['id'] for item in client.get(f'/api/v1/evidence?workspace={wid}',headers=read).json['data']]==[eid]
    nid=client.post(f'/api/v1/workspaces/{wid}/notes',headers=writer,json={'title':'Note'}).json['data']['id']
    assert client.post(f'/api/v1/notes/{nid}/evidence/{eid}',headers=writer).status_code==204
    assert client.get(f'/api/v1/evidence?note={nid}',headers=read).json['data'][0]['id']==eid
    client.patch(f'/api/v1/workspaces/{wid}',headers=writer,json={'archived':True})
    assert client.delete(f'/api/v1/workspaces/{wid}/evidence/{eid}',headers=writer).status_code==409
    assert client.post('/evidence/articles/1/capture').status_code==400
    for path in ['/evidence',f'/evidence/{eid}',f'/evidence?workspace={wid}']:
        assert client.get(path).status_code==200
    with app.app_context():assert get_db().execute('SELECT count(*) FROM quotations').fetchone()[0]==0


def test_attachment_real_parser_mime_quota_safe_download(app,client,writer,parser):
    wid=case(app)
    def upload(raw,name,mime):return client.post(f'/api/v1/workspaces/{wid}/attachments',headers=writer,data={'file':(io.BytesIO(raw),name,mime)})
    response=upload('調査\n<script>unsafe</script>'.encode(),'report.txt','text/plain')
    assert response.status_code==201,response.json
    eid=response.json['data']['id'];assert response.json['data']['method']=='attachment-text'
    assert '<script>' not in client.get(f'/evidence/{eid}').get_data(as_text=True)
    assert client.get(f'/api/v1/evidence/{eid}/download',headers=writer).data=='調査\n<script>unsafe</script>'.encode()
    buffer=io.BytesIO();pdf=PdfWriter();pdf.add_blank_page(width=200,height=200);pdf.write(buffer)
    assert upload(buffer.getvalue(),'report.pdf','application/pdf').status_code==201
    assert upload(b'# Markdown','report.md','text/markdown').status_code==201
    for raw,name,mime in [(b'plain','../report.txt','text/plain'),(b'%PDF-fake','report.txt','text/plain'),(b'not pdf','report.pdf','application/pdf'),(b'\xff\x00','report.txt','text/plain'),(b'plain','report.exe','text/plain'),(b'plain','report.txt','application/pdf'),(b'x'*(e.MAX_FILE+1),'report.txt','text/plain'),(b'x'*100001,'report.txt','text/plain')]:
        assert upload(raw,name,mime).status_code==400,(name,mime)
    encrypted=io.BytesIO();pdf.encrypt('fixture-only');pdf.write(encrypted)
    assert upload(encrypted.getvalue(),'locked.pdf','application/pdf').status_code==400
    assert post(client,f'/evidence/workspaces/{wid}/attachments',{'file':(io.BytesIO(b'# Browser Markdown'),'browser.md','text/plain')}).status_code==302
    client.patch(f'/api/v1/workspaces/{wid}',headers=writer,json={'archived':True})
    assert upload(b'blocked','new.txt','text/plain').status_code==409


def test_quota_capture_error_retention_and_symlink(app,client,writer,monkeypatch,tmp_path):
    subscribe(client);wid=case(app)
    with app.app_context():
        db=get_db();first=e.find(1);e.pin('workspace',wid,1)
        # Force an actual physical quota boundary with an orphan counted in usage.
        orphan=e.blob_path('a'*64);orphan.write_bytes(b'x'*(10*1024*1024))
        with db:db.execute('UPDATE evidence_settings SET quota_bytes=?',(10*1024*1024,))
    monkeypatch.setattr(collection,'fetch',lambda *args:(RSS.replace(b'First story',b'Quota story').replace(b'Hello',b'Quota body'),META))
    post(client,'/refresh')
    assert client.get('/api/v1/feeds/1',headers=writer).json['data']['evidence_capture_error'] is not None
    assert client.get('/api/v1/articles/1',headers=writer).json['data']['title']=='Quota story'
    class Future(datetime):
        @classmethod
        def now(cls,tz=None):return datetime(2040,1,1,tzinfo=timezone.utc)
    monkeypatch.setattr(e,'datetime',Future)
    with app.app_context():
        assert e.prune()==1
        assert e.find(1)['text']==first['text']
        assert not orphan.exists()
        protected=e.blob_path(first['blob_hash']);protected.unlink();protected.symlink_to(tmp_path/'elsewhere')
        with pytest.raises(ValueError):e.read_blob(first['blob_hash'])
    assert client.get('/api/v1/evidence?limit=101',headers=writer).status_code==400
    assert client.get('/api/v1/evidence?workspace=999',headers=writer).status_code==404


def test_bundle_integrity_partial_restore_and_legacy_refusal(app,client,tmp_path):
    subscribe(client);wid=case(app)
    with app.app_context():
        e.pin('workspace',wid,1)
        item=e.find(1);e.quotation(wid,{'evidence_id':1,'start':0,'end':5,'quote':item['text'][:5]})
        source=Path(app.config['DATABASE']);bundle=tmp_path/'bundle';backup_bundle(source,bundle)
        with pytest.raises(ValueError,match='bundle'):backup(source,tmp_path/'unsafe.sqlite3')
    destination=tmp_path/'restored'/'feeds.sqlite3';restore_bundle(bundle,destination)
    with connect(destination) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==8
        assert db.execute('SELECT count(*) FROM quotations').fetchone()[0]==1
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    old_bytes=destination.read_bytes();blob=bundle/'evidence-blobs'/item['blob_hash'];original=blob.read_bytes()
    for corrupt in ['missing','hash','symlink','extra']:
        if corrupt=='missing':blob.unlink()
        elif corrupt=='hash':blob.write_bytes(b'wrong')
        elif corrupt=='symlink':blob.unlink();blob.symlink_to(tmp_path/'elsewhere')
        else:(bundle/'evidence-blobs'/'traversal').write_bytes(b'bad')
        with pytest.raises(ValueError):restore_bundle(bundle,destination)
        assert destination.read_bytes()==old_bytes
        if corrupt=='extra':(bundle/'evidence-blobs'/'traversal').unlink()
        else:blob.unlink(missing_ok=True);blob.write_bytes(original)
    with pytest.raises(ValueError,match='bundle'):restore(bundle/'feeds.sqlite3',tmp_path/'db-only'/'feeds.sqlite3')
    assert validate_bundle(bundle)


def test_v5_upgrade_preserves_research_and_does_not_backfill(tmp_path):
    import sqlite3
    path=tmp_path/'v5.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript((Path(__file__).parent/'fixtures/v5_schema.sql').read_text())
        db.execute("INSERT INTO feeds(id,url,title,created_at) VALUES(7,'https://example.com/feed','Legacy','2026-01-01')")
        db.execute("INSERT INTO articles(id,feed_id,guid,title,content,search_text,published_at,is_read,is_starred) VALUES(9,7,'saved','Saved','content','content','2026-01-01',1,1)")
        db.execute("INSERT INTO workspaces(id,title,created_at,updated_at) VALUES(3,'Case','2026-01-01','2026-01-01')")
        db.execute('INSERT INTO workspace_articles VALUES(3,9)')
    init_database(path);init_database(path)
    with connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==8
        assert tuple(db.execute('SELECT id,is_read,is_starred,source_published_at FROM articles').fetchone())==(9,1,1,None)
        assert tuple(db.execute('SELECT * FROM workspace_articles').fetchone())==(3,9)
        assert db.execute('SELECT count(*) FROM evidence').fetchone()[0]==0
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
