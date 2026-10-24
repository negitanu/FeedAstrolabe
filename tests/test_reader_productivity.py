from urllib.parse import urlencode, urlsplit, parse_qs
import pytest
from werkzeug.datastructures import MultiDict
from feedastrolabe import create_app
from feedastrolabe.db import get_db, init_database, connect
from test_reader import app, client, post, subscribe
from test_reader_platform import ids
from test_reader_navigation import markup


def test_visits_independent_restart_delete(app,client,tmp_path):
    subscribe(client)
    assert client.get('/?article=1').status_code==200
    post(client,'/articles/1/read',{'value':'1'})
    post(client,'/articles/2/star',{'value':'1'})
    with app.app_context():assert get_db().execute('SELECT count(*) FROM article_visits').fetchone()[0]==0
    assert client.post('/articles/1/visit').status_code==400
    assert post(client,'/articles/999/visit').status_code==404
    for identifier in (1,2,1):
        assert post(client,f'/articles/{identifier}/visit',headers={'X-Reader-Visit':'1'}).status_code==204
    restarted=create_app({'TESTING':True,'DATA_DIR':app.instance_path})
    with restarted.app_context():
        db=get_db()
        assert [r[0] for r in db.execute('SELECT article_id FROM article_visits ORDER BY visited_at DESC')]==[1,2]
        assert db.execute('SELECT is_read,is_starred FROM articles WHERE id=1').fetchone()[:]==(1,0)
        assert db.execute('SELECT is_read,is_starred FROM articles WHERE id=2').fetchone()[:]==(0,1)
        with db:db.execute('DELETE FROM articles WHERE id=1')
        assert db.execute('SELECT count(*) FROM article_visits').fetchone()[0]==1
    assert ids(client.get('/?view=history'))==[2]


def test_history_migration_and_bundle(app,client,tmp_path):
    subscribe(client)
    with app.app_context():
        db=get_db()
        with db:
            db.execute('DROP TABLE article_visits')
            db.execute('PRAGMA user_version=18')
    from feedastrolabe.evidence_backup import backup_bundle,restore_bundle
    backup_bundle(app.config['DATABASE'],tmp_path/'schema18-bundle')
    restore_bundle(tmp_path/'schema18-bundle',tmp_path/'schema18-restored'/'feeds.sqlite3')
    with connect(tmp_path/'schema18-restored'/'feeds.sqlite3') as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==19
        assert db.execute('SELECT count(*) FROM articles').fetchone()[0]==2
        assert db.execute('SELECT count(*) FROM article_visits').fetchone()[0]==0
    init_database(app.config['DATABASE'])
    post(client,'/articles/1/visit')
    backup_bundle(app.config['DATABASE'],tmp_path/'bundle')
    restore_bundle(tmp_path/'bundle',tmp_path/'restored'/'feeds.sqlite3')
    with connect(tmp_path/'restored'/'feeds.sqlite3') as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==19
        assert db.execute('SELECT count(*) FROM article_visits').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM articles').fetchone()[0]==2
