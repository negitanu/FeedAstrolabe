"""Container acceptance test in an isolated *-verify Compose project.

Leaves its volume intact; never run against the actual library project.
"""
import argparse
import json
from pathlib import Path
import subprocess
import textwrap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', default='feedastrolabe-verify')
    args = parser.parse_args()
    if not args.project.endswith('-verify'):
        parser.error('Use an isolated project name ending in -verify')
    root = Path(__file__).resolve().parent.parent
    command = ['docker', 'compose', '-p', args.project, '-f', 'compose.yaml', '-f', 'compose.local.yaml']
    def run(*arguments):
        subprocess.run(command + list(arguments), cwd=root, check=True)
    def python(code):
        run('exec', '-T', 'web', 'python', '-c', textwrap.dedent(code))

    run('up', '--build', '-d', '--wait', '--wait-timeout', '90')
    container_id = subprocess.check_output(command + ['ps', '-q', 'web'], cwd=root, text=True).strip()
    inspection = json.loads(subprocess.check_output(['docker', 'inspect', container_id], text=True))[0]
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
        from feedastrolabe.maintenance import backup, restore
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
            key_id, token = issue_key('container-smoke', 'write', 1)
            request = urllib.request.Request('http://127.0.0.1:5000/api/v1/articles?is_starred=true', headers={'Authorization': 'Bearer ' + token})
            data = json.load(urllib.request.urlopen(request, timeout=10))
            assert any(a['guid']=='container-smoke-state' for a in data['data'])
            with db:
                db.execute('UPDATE api_keys SET revoked_at=? WHERE id=?', (now(), key_id))
            try:
                urllib.request.urlopen(request, timeout=10)
                raise AssertionError('Revoked key should fail')
            except urllib.error.HTTPError as error:
                assert error.code == 401
            snapshot = '/data/smoke-backup-' + uuid.uuid4().hex + '.sqlite3'
            backup('/data/feeds.sqlite3', snapshot)
            destination = tempfile.mkdtemp() + '/feeds.sqlite3'
            restore(snapshot, destination)
            with connect(destination) as restored:
                row = restored.execute("SELECT is_read,is_starred FROM articles WHERE guid='container-smoke-state'").fetchone()
                assert tuple(row)==(1,1)
        print('PASS: non-root, read-only filesystem, authenticated live API, revocation, consistent backup and restore')
    ''')
    run('up', '-d', '--force-recreate', '--wait', '--wait-timeout', '90')
    python('''
        import json, urllib.request
        from feedastrolabe import create_app
        from feedastrolabe.db import get_db
        app = create_app()
        with app.app_context():
            row = get_db().execute("SELECT is_read,is_starred FROM articles WHERE guid='container-smoke-state'").fetchone()
            assert tuple(row)==(1,1)
        assert json.load(urllib.request.urlopen('http://127.0.0.1:5000/healthz'))['status']=='ok'
        print('PASS: Web/worker recreation retains read and star state')
    ''')
    run('down')
    print('Container verification completed; isolated volume retained.')


if __name__ == '__main__':
    main()
