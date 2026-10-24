from datetime import datetime, timezone
import sqlite3
import pytest
from feedastrolabe.db import get_db, init_database
from feedastrolabe.display_time import display_time
from feedastrolabe.preferences import preferences
from test_reader import app, client, subscribe, post
from test_phase_two import authorization, settings_data


def test_jst_ui_persistence_rollover_and_api_utc(app, client):
    subscribe(client)
    with app.app_context():
        db = get_db()
        db.execute("UPDATE articles SET published_at='2026-10-08 18:30:00'")
        db.commit()
    assert '2026-10-08 18:30 UTC' in client.get('/').get_data(as_text=True)
    response = post(client, '/settings', settings_data(display_timezone='Asia/Tokyo'), follow_redirects=True)
    assert 'value="Asia/Tokyo" selected' in response.get_data(as_text=True)
    assert '2026-10-09 03:30 JST' in client.get('/').get_data(as_text=True)
    assert '2026-10-09 03:30:00 JST' in client.get('/?article=1').get_data(as_text=True)
    _, _, read = authorization(app)
    assert client.get('/api/v1/articles', headers=read).json['data'][0]['published_at'] == '2026-10-08 18:30:00'
    with app.app_context():
        assert preferences()['display_timezone'] == 'Asia/Tokyo'
        assert get_db().execute('SELECT published_at FROM articles').fetchone()[0] == '2026-10-08 18:30:00'
    # Legacy form without the new field preserves the timezone.
    post(client, '/settings', settings_data())
    assert '2026-10-09 03:30 JST' in client.get('/').get_data(as_text=True)
    post(client, '/settings', settings_data(display_timezone='UTC'))
    assert '2026-10-08 18:30 UTC' in client.get('/').get_data(as_text=True)


def test_invalid_timezone_atomic_and_scoped_api(app, client):
    _, _, read = authorization(app)
    _, _, write = authorization(app, 'write')
    assert client.patch('/api/v1/settings', headers=read, json={'display_timezone':'Asia/Tokyo'}).status_code == 403
    assert client.patch('/api/v1/settings', headers=write, json={'display_timezone':'Asia/Tokyo'}).status_code == 200
    before = client.get('/api/v1/settings', headers=read).json
    for value in ('Europe/London', '', None, 9, ['UTC']):
        assert client.patch('/api/v1/settings', headers=write, json={'display_timezone':value,'page_size':50}).status_code == 400
        assert client.get('/api/v1/settings', headers=read).json == before
    post(client, '/settings', settings_data(display_timezone='bad', page_size='50'))
    assert client.get('/api/v1/settings', headers=read).json == before


def test_formatter_offsets_empty_invalid_and_templates(app):
    with app.test_request_context('/'):
        get_db().execute("UPDATE settings SET display_timezone='Asia/Tokyo'")
        assert display_time('2026-10-08T18:30:00Z') == '2026-10-09 03:30:00 JST'
        assert display_time('2026-10-09T03:30:00+09:00') == '2026-10-09 03:30:00 JST'
        assert display_time(datetime(2026,10,8,18,30,tzinfo=timezone.utc)) == '2026-10-09 03:30:00 JST'
        assert display_time(None,missing='未確認') == '未確認'
        assert display_time('not a date') == '不明'
        for name in app.jinja_env.list_templates():
            app.jinja_env.get_template(name)


def test_v13_migration_preserves_data_and_default(tmp_path):
    from pathlib import Path
    path = tmp_path/'v13.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript(Path('tests/fixtures/v13_schema.sql').read_text())
    with sqlite3.connect(path) as db:
        db.execute("UPDATE settings SET page_size=50")
        db.execute("INSERT INTO feeds(url,title,created_at) VALUES('https://example.com/rss','Existing','2026-10-08 18:30:00')")
    init_database(path)
    init_database(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 19
        assert db.execute('SELECT page_size,display_timezone FROM settings').fetchone() == (50,'UTC')
        assert db.execute('SELECT title,created_at FROM feeds').fetchone() == ('Existing','2026-10-08 18:30:00')
        assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_timezone_bundle_round_trip(app, tmp_path):
    from feedastrolabe.db import connect
    from feedastrolabe.evidence_backup import backup_bundle, restore_bundle
    with app.app_context():
        db = get_db()
        with db:
            db.execute("UPDATE settings SET display_timezone='Asia/Tokyo'")
        bundle = tmp_path/'bundle'
        backup_bundle(app.config['DATABASE'], bundle)
        restored = tmp_path/'restored'/'feeds.sqlite3'
        restore_bundle(bundle, restored)
        with connect(restored) as db:
            assert db.execute('SELECT display_timezone FROM settings').fetchone()[0] == 'Asia/Tokyo'
            assert db.execute('PRAGMA user_version').fetchone()[0] == 19
