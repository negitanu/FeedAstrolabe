import sqlite3
from pathlib import Path
from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS feeds (
 id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
 folder TEXT NOT NULL DEFAULT '', etag TEXT, modified TEXT,
 checked_at TEXT, success_at TEXT, error TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS articles (
 id INTEGER PRIMARY KEY, feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
 guid TEXT NOT NULL, title TEXT NOT NULL, link TEXT NOT NULL DEFAULT '',
 content TEXT NOT NULL, search_text TEXT NOT NULL, published_at TEXT NOT NULL,
 is_read INTEGER NOT NULL DEFAULT 0 CHECK(is_read IN (0,1)),
 is_starred INTEGER NOT NULL DEFAULT 0 CHECK(is_starred IN (0,1)),
 UNIQUE(feed_id, guid)
);
CREATE INDEX IF NOT EXISTS articles_date ON articles(published_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS articles_feed ON articles(feed_id);
CREATE INDEX IF NOT EXISTS articles_read ON articles(is_read);
CREATE INDEX IF NOT EXISTS articles_starred ON articles(is_starred);
"""


def connect(path):
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def init_database(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = connect(path)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('BEGIN IMMEDIATE')
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1, 2, 3):
            raise RuntimeError(f'Unsupported database version: {version}')
        if version == 0:
            for statement in SCHEMA.split(';'):
                if statement.strip():
                    db.execute(statement)
        if version < 2:
            db.execute('ALTER TABLE feeds ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1))')
            db.execute('ALTER TABLE feeds ADD COLUMN poll_interval INTEGER CHECK(poll_interval BETWEEN 60 AND 86400)')
            db.execute('ALTER TABLE feeds ADD COLUMN failures INTEGER NOT NULL DEFAULT 0')
            db.execute("""CREATE TABLE settings (
              id INTEGER PRIMARY KEY CHECK(id=1), poll_interval INTEGER NOT NULL DEFAULT 900,
              polling_enabled INTEGER NOT NULL DEFAULT 1, page_size INTEGER NOT NULL DEFAULT 30,
              default_view TEXT NOT NULL DEFAULT 'all', api_rate_limit INTEGER NOT NULL DEFAULT 120
            )""")
            db.execute('INSERT INTO settings(id) VALUES(1)')
            db.execute("""CREATE TABLE api_keys (
              id INTEGER PRIMARY KEY, name TEXT NOT NULL, prefix TEXT NOT NULL,
              token_hash TEXT NOT NULL UNIQUE, scope TEXT NOT NULL CHECK(scope IN ('read','write')),
              created_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT, last_used_at TEXT,
              rate_window INTEGER NOT NULL DEFAULT 0, rate_count INTEGER NOT NULL DEFAULT 0
            )""")
            db.execute('PRAGMA user_version=2')
        if version < 3:
            db.execute("ALTER TABLE feeds ADD COLUMN source_type TEXT NOT NULL DEFAULT 'rss' CHECK(source_type IN ('rss','x','mastodon'))")
            for name in ('source_kind', 'target', 'instance_url', 'provider_id', 'since_id', 'page_cursor', 'pending_newest', 'retry_at'):
                db.execute(f'ALTER TABLE feeds ADD COLUMN {name} TEXT')
            db.execute("CREATE TABLE provider_cooldowns (provider TEXT PRIMARY KEY, retry_at TEXT NOT NULL)")
            db.execute('PRAGMA user_version=3')
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    if 'db' not in g:
        g.db = connect(current_app.config['DATABASE'])
    return g.db


def close_db(_error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
