"""Real Chromium and isolation acceptance in a separate *-verify project."""
import argparse
import json
from pathlib import Path
import subprocess
import textwrap
import uuid


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',default='feedastrolabe-observer-verify')
    args=parser.parse_args()
    if not args.project.endswith('-verify'):
        parser.error('Use a separate project ending in -verify')
    root=Path(__file__).resolve().parent.parent
    command=['docker','compose','-p',args.project,'-f','compose.yaml','-f','compose.observer.yaml']
    def run(*parts):subprocess.run(command+list(parts),cwd=root,check=True)
    def code(value):run('run','--rm','--no-deps','-T','observer','python','-c',textwrap.dedent(value))
    triage_dir='/data/'+uuid.uuid4().hex+'-triage-verify'
    triage_script=(root/'scripts/verify_triage.py').read_text()
    entity_dir='/data/'+uuid.uuid4().hex+'-entity-verify'
    entity_script=(root/'scripts/verify_entities.py').read_text()
    security_dir='/data/'+uuid.uuid4().hex+'-security-verify'
    security_script=(root/'scripts/verify_security.py').read_text()
    try:
        run('up','--build','-d','--wait','--wait-timeout','120')
        run('stop','observer')
        subprocess.run(command+['exec','-T','web','python','-'],cwd=root,input=(root/'scripts/verify_evidence.py').read_text(),text=True,check=True)
        subprocess.run(command+['exec','-T','web','python','-','--data-dir',triage_dir],cwd=root,input=triage_script,text=True,check=True)
        subprocess.run(command+['exec','-T','web','python','-','--data-dir',entity_dir],cwd=root,input=entity_script,text=True,check=True)
        subprocess.run(command+['exec','-T','web','python','-','--data-dir',security_dir],cwd=root,input=security_script,text=True,check=True)
        renderer=subprocess.check_output(command+['ps','-q','renderer'],cwd=root,text=True).strip()
        details=json.loads(subprocess.check_output(['docker','inspect',renderer],text=True))[0]
        assert details['HostConfig']['NetworkMode']=='none'
        assert details['HostConfig']['ReadonlyRootfs']
        assert details['HostConfig']['Memory']==512*1024*1024
        assert details['HostConfig']['PidsLimit']==128
        assert 'ALL' in details['HostConfig']['CapDrop']
        assert details['Config']['User']=='10001:10001'
        assert [item['Destination'] for item in details['Mounts']]==['/run/observer']
        run('exec','-T','renderer','python','-c',textwrap.dedent('''
            import os,socket
            assert os.getuid()==10001
            try:
                socket.create_connection(('1.1.1.1',443),timeout=2)
                raise AssertionError('Renderer should not reach the network')
            except OSError:
                pass
            assert not os.path.exists('/data/feeds.sqlite3')
            print('PASS: renderer network disabled, no DB mount, non-root')
        '''))
        code('''
            import base64, json, urllib.request, uuid
            from feedastrolabe import create_app, observation, collection, page_broker
            from feedastrolabe.db import get_db
            from feedastrolabe.keys import issue_key
            from feedastrolabe.evidence_backup import backup_bundle as backup, restore_bundle as restore
            from feedastrolabe.collection import now
            value='Baseline'
            def fixture(self,url,method='GET'):
                assert method=='GET'
                body='<main id="target">Loading</main><script>setTimeout(()=>document.querySelector("#target").innerText='+json.dumps(value)+',100)</script>'
                return {'type':'response','body':base64.b64encode(body.encode()).decode(),'content_type':'text/html'}
            page_broker.FetchBudget.fetch=fixture
            app=create_app()
            with app.app_context():
                db=get_db()
                old=db.execute("SELECT id FROM feeds WHERE target='https://example.com/observer-fixture'").fetchone()
                if old:
                    with db:db.execute('DELETE FROM feeds WHERE id=?',(old['id'],))
                source=observation.add_page('https://example.com/observer-fixture','#target',settle_ms=300)
                with db:db.execute('UPDATE feeds SET enabled=0 WHERE id=?',(source,))
                collection.refresh_feeds(source)
                assert observation.observe_pages()==(1,0)
                assert db.execute('SELECT count(*) FROM articles WHERE feed_id=?',(source,)).fetchone()[0]==0
                for value in ('Changed','Changed','Baseline'):
                    observation.queue_page(source)
                    assert observation.observe_pages()==(1,0)
                events=db.execute('SELECT * FROM articles WHERE feed_id=? ORDER BY id',(source,)).fetchall()
                assert [event['guid'] for event in events]==['page:1','page:2']
                with db:db.execute('UPDATE articles SET is_read=1,is_starred=1 WHERE id=?',(events[0]['id'],))
                key_id,token=issue_key('observer-smoke','read',1)
                request=urllib.request.Request('http://web:5000/api/v1/articles?source_type=page',headers={'Host':'localhost','Authorization':'Bearer '+token})
                result=json.load(urllib.request.urlopen(request,timeout=10))
                assert len(result['data'])==2 and result['data'][0]['source_type']=='page'
                with db:db.execute('UPDATE api_keys SET revoked_at=? WHERE id=?',(now(),key_id))
                backup('/data/feeds.sqlite3','/data/observer-verified-'+uuid.uuid4().hex+'.sqlite3')
                print('PASS: real JS renderer, queued baseline, change/no-change/revert events, live API')
        ''')
        run('up','-d','--force-recreate','--wait','--wait-timeout','120')
        subprocess.run(command+['exec','-T','web','python','-','--data-dir',triage_dir,'--check-state'],cwd=root,input=triage_script,text=True,check=True)
        subprocess.run(command+['exec','-T','web','python','-','--data-dir',entity_dir,'--check-state'],cwd=root,input=entity_script,text=True,check=True)
        subprocess.run(command+['exec','-T','web','python','-','--data-dir',security_dir,'--check-state'],cwd=root,input=security_script,text=True,check=True)
        code('''
            from feedastrolabe import create_app
            from feedastrolabe.db import get_db
            app=create_app()
            with app.app_context():
                db=get_db()
                row=db.execute("SELECT a.is_read,a.is_starred FROM articles a JOIN feeds f ON a.feed_id=f.id WHERE f.target='https://example.com/observer-fixture' AND a.guid='page:1'").fetchone()
                assert tuple(row)==(1,1)
                assert db.execute('PRAGMA user_version').fetchone()[0]==9
                print('PASS: renderer/worker recreation preserves baseline and event state')
        ''')
    finally:
        run('down')
    print('Observer verification completed; isolated volumes retained.')


if __name__=='__main__':main()
