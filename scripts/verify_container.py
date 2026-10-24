"""Container acceptance test in an isolated *-verify Compose project.

Leaves its volume intact; never run against the actual library project.
"""
import argparse
import json
import subprocess
import textwrap
from compose_verification import VerificationCompose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', default='feedastrolabe-verify')
    args = parser.parse_args()
    if not args.project.endswith('-verify'):
        parser.error('Use an isolated project name ending in -verify')
    with VerificationCompose(args.project) as target:
        try:
            verify(target)
        finally:
            subprocess.run(target.command + ['down'], cwd=target.root, env=target.env, check=True)


def verify(target):
    root = target.root
    command = target.command
    def run(*arguments):
        subprocess.run(command + list(arguments), cwd=root, env=target.env, check=True)
    def python(code):
        run('exec', '-T', 'web', 'python', '-c', textwrap.dedent(code))

    run('up', '--build', '-d', '--wait', '--wait-timeout', '90', 'web', 'worker')
    # Keep fixture jobs deterministic; the worker is health-checked again on recreation.
    run('stop', 'worker')
    container_id = subprocess.check_output(command + ['ps', '-q', 'web'], cwd=root, env=target.env, text=True).strip()
    inspection = json.loads(subprocess.check_output(['docker', 'inspect', container_id], env=target.env, text=True))[0]
    assert inspection['HostConfig']['ReadonlyRootfs'] is True
    assert 'ALL' in inspection['HostConfig']['CapDrop']
    assert inspection['Config']['User'] == '10001:10001'
    python('''
        import json, os, tempfile, uuid, urllib.request, urllib.error
        from pathlib import Path
        from feedastrolabe import create_app
        from feedastrolabe.db import get_db, connect
        from feedastrolabe.collection import now
        from feedastrolabe.keys import issue_key
        from feedastrolabe import research as research
        from feedastrolabe import social, collection
        from feedastrolabe.evidence_backup import backup_bundle as backup, restore_bundle as restore
        assert os.getuid() == 10001
        try:
            Path('/app/write-probe').write_text('unexpected')
            raise AssertionError('Root filesystem should be read-only')
        except OSError:
            pass
        app = create_app()
        with app.app_context():
            db = get_db()
            with db:
                db.execute("INSERT OR IGNORE INTO feeds(url,title,folder,created_at,enabled) VALUES('https://example.com/container-smoke.xml','Container verification','Verification',?,0)", (now(),))
                feed_id = db.execute("SELECT id FROM feeds WHERE url='https://example.com/container-smoke.xml'").fetchone()[0]
                db.execute("INSERT OR IGNORE INTO articles(feed_id,guid,title,content,search_text,published_at,is_read,is_starred) VALUES(?,'container-smoke-state','Persistent smoke article','<p>safe</p>','safe',?,1,1)", (feed_id, now()))
            existing = db.execute("SELECT id FROM feeds WHERE url='https://example.com/@container_test'").fetchone()
            social_id = existing['id'] if existing else social.add_social('mastodon', 'account', 'container_test', 'https://example.com', 'Verification')
            with db:
                db.execute('UPDATE feeds SET enabled=0 WHERE id=?', (social_id,))
            def fixture_request(url, token=None):
                if '/lookup?' in url:
                    return {'id': '123'}, {}
                return [{'id': '789', 'visibility': 'public', 'content': '<p>Container social verification</p>', 'url': 'https://example.com/@container_test/789', 'created_at': '2026-10-08T00:00:00Z'}], {}
            social.request_json = fixture_request
            assert collection.refresh_feeds(social_id) == (1, 0)
            from feedastrolabe import social_research as topic
            existing_topic = db.execute("SELECT feed_id FROM social_topics JOIN feeds ON feeds.id=feed_id WHERE title='Container social topic'").fetchone()
            topic_id = existing_topic[0] if existing_topic else topic.add_topic('bluesky', 'container fixture', name='Container social topic', folder='Verification')
            with db:
                db.execute('UPDATE feeds SET enabled=0 WHERE id=?', (topic_id,))
            topic.request_json = lambda url: ({'posts':[{'uri':'at://did:plc:containerfixture/app.bsky.feed.post/one','author':{'did':'did:plc:containerfixture'},'record':{'$type':'app.bsky.feed.post','text':'Container topic fixture','createdAt':now().replace(' ','T')+'Z'},'likeCount':5,'repostCount':2,'replyCount':1}]}, {})
            assert collection.refresh_feeds(topic_id) == (1, 0)
            assert topic.topic_report(topic_id)['latest']['sample_count'] == 1
            assert topic.topic_report(topic_id)['results'][0]['score'] == 10
            from feedastrolabe import social_ai as ai
            app.config['OPENROUTER_API_KEY']='synthetic-'+('k'*32)
            cfg=ai.settings()
            ai.configure({'expected_revision':cfg['revision'],'model':'vendor/container-fixture','enabled':True})
            def fake_generation(config,wire,bound):
                source=json.loads(json.loads(wire)['messages'][1]['content'])['sources'][0]['article_id']
                return json.dumps({'topics':[{'title':'Container important topic','summary':'Synthetic public research summary','importance':90,'reason':'Concrete impact','uncertainty':'Unverified fixture','article_ids':[source]}]}),{'prompt_tokens':100,'completion_tokens':100,'cost_micro_usd':1000},{'requested_model':config['model'],'response_model':config['model'],'adapter':'fixture','generation_id':'gen-container-fixture'}
            ai.generate=fake_generation
            ai_id=ai.enqueue(topic_id)
            if ai.detail(ai_id)['status']=='queued':
                assert ai.process()['processed']==1
            assert ai.detail(ai_id)['status']=='success'
            key_id, token = issue_key('container-smoke', 'write', 1)
            request = urllib.request.Request('http://127.0.0.1:5000/api/v1/articles?is_starred=true', headers={'Authorization': 'Bearer ' + token})
            data = json.load(urllib.request.urlopen(request, timeout=10))
            assert any(a['guid']=='container-smoke-state' for a in data['data'])
            sns_request = urllib.request.Request('http://127.0.0.1:5000/api/v1/articles?source_type=mastodon', headers={'Authorization': 'Bearer ' + token})
            sns = json.load(urllib.request.urlopen(sns_request, timeout=10))
            assert any(a['guid']=='mastodon:789' for a in sns['data'])
            topic_request = urllib.request.Request('http://127.0.0.1:5000/api/v1/social-research/'+str(topic_id), headers={'Authorization':'Bearer '+token})
            assert json.load(urllib.request.urlopen(topic_request, timeout=10))['data']['results'][0]['score'] == 10
            ai_request = urllib.request.Request('http://127.0.0.1:5000/api/v1/social-research/ai/jobs/'+str(ai_id), headers={'Authorization':'Bearer '+token})
            assert json.load(urllib.request.urlopen(ai_request,timeout=10))['data']['result']['topics'][0]['importance']==90
            with db:
                db.execute('UPDATE api_keys SET revoked_at=? WHERE id=?', (now(), key_id))
            try:
                urllib.request.urlopen(request, timeout=10)
                raise AssertionError('Revoked key should fail')
            except urllib.error.HTTPError as error:
                assert error.code == 401
            existing = db.execute("SELECT id FROM workspaces WHERE title='Container research fixture'").fetchone()
            workspace_id = existing['id'] if existing else research.create_workspace({'title':'Container research fixture','classification':'restricted'})
            research.associate('workspace',workspace_id,'feed',feed_id)
            article_id = db.execute("SELECT id FROM articles WHERE guid='container-smoke-state'").fetchone()[0]
            research.associate('workspace',workspace_id,'article',article_id)
            existing_note = db.execute('SELECT * FROM notes WHERE workspace_id=?',(workspace_id,)).fetchone()
            note_id = existing_note['id'] if existing_note else research.create_note(workspace_id,{'title':'Container note','body':'original'})
            if research.find('note',note_id)['revision']==1:
                research.update_note(note_id,{'expected_revision':1,'body':'edited','label':'fact'})
            snapshot = '/data/smoke-backup-' + uuid.uuid4().hex + '.sqlite3'
            backup('/data/feeds.sqlite3', snapshot)
            destination = tempfile.mkdtemp() + '/feeds.sqlite3'
            restore(snapshot, destination)
            with connect(destination) as restored:
                row = restored.execute("SELECT is_read,is_starred FROM articles WHERE guid='container-smoke-state'").fetchone()
                assert tuple(row)==(1,1)
                assert restored.execute('SELECT count(*) FROM note_revisions WHERE note_id=?',(note_id,)).fetchone()[0]==2
                assert restored.execute('SELECT body FROM notes WHERE id=?',(note_id,)).fetchone()[0]=='edited'
                assert restored.execute('SELECT count(*) FROM workspace_articles WHERE workspace_id=?',(workspace_id,)).fetchone()[0]==1
                assert restored.execute('SELECT count(*) FROM social_runs WHERE feed_id=?',(topic_id,)).fetchone()[0]>=1
                assert not restored.execute('PRAGMA foreign_key_check').fetchall()
                assert restored.execute('SELECT enabled FROM social_ai_config').fetchone()[0]==0
                assert restored.execute('SELECT status FROM social_ai_jobs WHERE id=?',(ai_id,)).fetchone()[0]=='success'
        print('PASS: non-root, read-only filesystem, authenticated live API, revocation, consistent backup and restore')
    ''')
    run('up', '-d', '--force-recreate', '--wait', '--wait-timeout', '90', 'web', 'worker')
    python('''
        import json, urllib.request
        from feedastrolabe import create_app
        from feedastrolabe.db import get_db
        app = create_app()
        with app.app_context():
            row = get_db().execute("SELECT is_read,is_starred FROM articles WHERE guid='container-smoke-state'").fetchone()
            assert tuple(row)==(1,1)
            assert get_db().execute("SELECT count(*) FROM articles WHERE guid='mastodon:789'").fetchone()[0] == 1
            assert get_db().execute('PRAGMA user_version').fetchone()[0] == 18
            from feedastrolabe.social_research import topic_report
            topic_id=get_db().execute("SELECT id FROM feeds WHERE title='Container social topic'").fetchone()[0]
            assert topic_report(topic_id)['results'][0]['score']==10
            from feedastrolabe.social_ai import report
            assert report(topic_id)['success']['result']['topics'][0]['importance']==90
            assert get_db().execute("SELECT count(*) FROM note_revisions nr JOIN notes n ON n.id=nr.note_id JOIN workspaces w ON w.id=n.workspace_id WHERE w.title='Container research fixture'").fetchone()[0]==2
            assert get_db().execute("SELECT n.body FROM notes n JOIN workspaces w ON w.id=n.workspace_id WHERE w.title='Container research fixture'").fetchone()[0]=='edited'
        assert json.load(urllib.request.urlopen('http://127.0.0.1:5000/healthz'))['status']=='ok'
        print('PASS: Web/worker recreation retains read and star state')
    ''')
    print('Container verification completed; isolated volume retained.')


if __name__ == '__main__':
    main()
