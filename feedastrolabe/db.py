import sqlite3
from pathlib import Path
from flask import current_app, g

SCHEMA_VERSION = 19

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
        db.execute('PRAGMA foreign_keys=OFF')
        db.execute('BEGIN IMMEDIATE')
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version not in range(SCHEMA_VERSION+1):
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
        if version < 4:
            sql = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='feeds'").fetchone()[0]
            sql = sql.replace('CREATE TABLE feeds', 'CREATE TABLE feeds_next', 1).replace("('rss','x','mastodon')", "('rss','x','mastodon','page')")
            db.execute(sql)
            columns = ','.join(row[1] for row in db.execute('PRAGMA table_info(feeds)'))
            db.execute(f'INSERT INTO feeds_next({columns}) SELECT {columns} FROM feeds')
            db.execute('DROP TABLE feeds')
            db.execute('ALTER TABLE feeds_next RENAME TO feeds')
            db.execute('ALTER TABLE feeds ADD COLUMN selector TEXT')
            db.execute('ALTER TABLE feeds ADD COLUMN settle_ms INTEGER NOT NULL DEFAULT 1000 CHECK(settle_ms BETWEEN 0 AND 10000)')
            db.execute('ALTER TABLE feeds ADD COLUMN snapshot TEXT')
            db.execute('ALTER TABLE feeds ADD COLUMN observation_seq INTEGER NOT NULL DEFAULT 0')
            db.execute('ALTER TABLE feeds ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')
            db.execute('ALTER TABLE feeds ADD COLUMN retention_days INTEGER NOT NULL DEFAULT 90 CHECK(retention_days BETWEEN 1 AND 365)')
            db.execute('CREATE TABLE page_jobs (feed_id INTEGER PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE,requested_at TEXT NOT NULL)')
            db.execute('PRAGMA user_version=4')
        if version < 5:
            statements = """
            CREATE TABLE workspaces (
              id INTEGER PRIMARY KEY, title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
              purpose TEXT NOT NULL DEFAULT '' CHECK(length(purpose)<=10000),
              questions TEXT NOT NULL DEFAULT '' CHECK(length(questions)<=10000),
              status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused','completed')),
              classification TEXT NOT NULL DEFAULT 'internal' CHECK(classification IN ('public','internal','restricted')),
              archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE workspace_feeds (
              workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
              PRIMARY KEY(workspace_id,feed_id)
            );
            CREATE TABLE workspace_articles (
              workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
              PRIMARY KEY(workspace_id,article_id)
            );
            CREATE TABLE notes (
              id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
              body TEXT NOT NULL DEFAULT '' CHECK(length(body)<=100000),
              label TEXT NOT NULL DEFAULT 'hypothesis' CHECK(label IN ('fact','source-claim','hypothesis')),
              archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
              revision INTEGER NOT NULL CHECK(revision>=1), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE note_revisions (
              note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
              revision INTEGER NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, label TEXT NOT NULL,
              archived INTEGER NOT NULL CHECK(archived IN (0,1)), created_at TEXT NOT NULL,
              PRIMARY KEY(note_id,revision)
            );
            CREATE TABLE tags (id INTEGER PRIMARY KEY,name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(name) BETWEEN 1 AND 80));
            CREATE TABLE workspace_tags (
              workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,PRIMARY KEY(workspace_id,tag_id)
            );
            CREATE TABLE article_tags (
              article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
              tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,PRIMARY KEY(article_id,tag_id)
            );
            CREATE TABLE note_tags (
              note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
              tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,PRIMARY KEY(note_id,tag_id)
            );
            CREATE INDEX notes_workspace ON notes(workspace_id,archived,id);
            CREATE INDEX workspace_feeds_reverse ON workspace_feeds(feed_id,workspace_id);
            CREATE INDEX workspace_articles_reverse ON workspace_articles(article_id,workspace_id);
            CREATE INDEX workspace_tags_reverse ON workspace_tags(tag_id,workspace_id);
            CREATE INDEX article_tags_reverse ON article_tags(tag_id,article_id);
            CREATE INDEX note_tags_reverse ON note_tags(tag_id,note_id);
            """
            for statement in statements.split(';'):
                if statement.strip():
                    db.execute(statement)
            db.execute('PRAGMA user_version=5')
        if version < 6:
            statements = """
            CREATE TABLE evidence_settings (id INTEGER PRIMARY KEY CHECK(id=1),quota_bytes INTEGER NOT NULL DEFAULT 524288000 CHECK(quota_bytes BETWEEN 10485760 AND 10737418240),retention_days INTEGER NOT NULL DEFAULT 90 CHECK(retention_days BETWEEN 1 AND 3650));
            INSERT INTO evidence_settings(id) VALUES(1);
            CREATE TABLE evidence_blobs (hash TEXT PRIMARY KEY CHECK(length(hash)=64),size INTEGER NOT NULL CHECK(size BETWEEN 0 AND 10485760));
            CREATE TABLE evidence (
              id INTEGER PRIMARY KEY, source_key TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>=1),
              feed_id INTEGER REFERENCES feeds(id) ON DELETE SET NULL,
              article_id INTEGER REFERENCES articles(id) ON DELETE SET NULL,
              source_url TEXT NOT NULL, publisher TEXT NOT NULL, source_guid TEXT NOT NULL,
              title TEXT NOT NULL, method TEXT NOT NULL, published_at TEXT, observed_at TEXT,
              captured_at TEXT NOT NULL, blob_hash TEXT NOT NULL REFERENCES evidence_blobs(hash),
              text_hash TEXT NOT NULL CHECK(length(text_hash)=64), text TEXT NOT NULL CHECK(length(text)<=160000),
              mime TEXT NOT NULL, filename TEXT NOT NULL DEFAULT '',UNIQUE(source_key,version)
            );
            CREATE INDEX evidence_source ON evidence(source_key,id DESC);
            CREATE INDEX evidence_article ON evidence(article_id,id DESC);
            CREATE TABLE workspace_evidence (workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,PRIMARY KEY(workspace_id,evidence_id));
            CREATE TABLE note_evidence (note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,PRIMARY KEY(note_id,evidence_id));
            CREATE TABLE quotations (id INTEGER PRIMARY KEY,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,text_hash TEXT NOT NULL,start INTEGER NOT NULL,end INTEGER NOT NULL,quote TEXT NOT NULL CHECK(length(quote) BETWEEN 1 AND 10000),created_at TEXT NOT NULL,CHECK(start>=0 AND end>start),UNIQUE(workspace_id,evidence_id,start,end,note_id));
            CREATE INDEX workspace_evidence_reverse ON workspace_evidence(evidence_id);
            CREATE INDEX note_evidence_reverse ON note_evidence(evidence_id);
            CREATE INDEX quotations_evidence ON quotations(evidence_id);
            CREATE TABLE evidence_capture_errors (feed_id INTEGER PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE,message TEXT NOT NULL,occurred_at TEXT NOT NULL);
            """
            for statement in statements.split(';'):
                if statement.strip():
                    db.execute(statement)
            db.execute('ALTER TABLE articles ADD COLUMN source_published_at TEXT')
            db.execute('PRAGMA user_version=6')
        if version < 7:
            # Stable increasing IDs are required for incremental processing after retention.
            sql = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='evidence'").fetchone()[0]
            sql = sql.replace('CREATE TABLE evidence', 'CREATE TABLE evidence_next', 1).replace('id INTEGER PRIMARY KEY', 'id INTEGER PRIMARY KEY AUTOINCREMENT', 1)
            db.execute(sql)
            columns = ','.join(row[1] for row in db.execute('PRAGMA table_info(evidence)'))
            db.execute(f'INSERT INTO evidence_next({columns}) SELECT {columns} FROM evidence')
            db.execute('DROP TABLE evidence')
            db.execute('ALTER TABLE evidence_next RENAME TO evidence')
            db.execute('CREATE INDEX evidence_source ON evidence(source_key,id DESC)')
            db.execute('CREATE INDEX evidence_article ON evidence(article_id,id DESC)')
            from .triage_schema import SCHEMA as triage_schema
            for statement in triage_schema.split(';'):
                if statement.strip(): db.execute(statement)
            db.execute('PRAGMA user_version=7')
        if version < 8:
            from .entity_schema import SCHEMA as entity_schema
            for statement in entity_schema.split(';'):
                if statement.strip(): db.execute(statement)
            db.execute('PRAGMA user_version=8')
        if version < 9:
            from .connector_schema import SCHEMA as connector_schema
            for statement in connector_schema.split(';'):
                if statement.strip():db.execute(statement)
            for provider in ('kev','epss','cve'):
                db.execute('INSERT INTO connector_settings(provider) VALUES(?)',(provider,))
                db.execute('INSERT INTO connector_state(provider) VALUES(?)',(provider,))
            db.execute('PRAGMA user_version=9')
        if version < 10:
            from .network_schema import SCHEMA as network_schema
            from .network_adapters import PROVIDERS as network_providers
            for provider in network_providers:
                db.execute('INSERT INTO connector_settings(provider,ttl_seconds) VALUES(?,3600)',(provider,))
                db.execute('INSERT INTO connector_state(provider) VALUES(?)',(provider,))
            for statement in network_schema.split(';'):
                if statement.strip():db.execute(statement)
            db.execute('PRAGMA user_version=10')
        if version < 11:
            from .ai_research_schema import SCHEMA as ai_schema
            for provider in ('arxiv','github-releases'):
                db.execute('INSERT INTO connector_settings(provider) VALUES(?)',(provider,))
                db.execute('INSERT INTO connector_state(provider) VALUES(?)',(provider,))
            for statement in ai_schema.split(';'):
                if statement.strip():db.execute(statement)
            db.execute('PRAGMA user_version=11')
        if version < 12:
            from .assistant_schema import SCHEMA as assistant_schema
            for statement in assistant_schema.split(';'):
                if statement.strip():db.execute(statement)
            db.execute('PRAGMA user_version=12')
        if version < 13:
            from .operations_schema import SCHEMA as operations_schema
            for statement in operations_schema.split(';'):
                if statement.strip():db.execute(statement)
            db.execute('PRAGMA user_version=13')
        if version < 14:
            db.execute("ALTER TABLE settings ADD COLUMN display_timezone TEXT NOT NULL DEFAULT 'UTC' CHECK(display_timezone IN ('UTC','Asia/Tokyo'))")
            db.execute('PRAGMA user_version=14')
        if version < 15:
            sql = db.execute("SELECT sql FROM sqlite_master WHERE name='feeds'").fetchone()[0]
            sql = ('CREATE TABLE feeds_next ' + sql[sql.index('('):]).replace("('rss','x','mastodon','page')", "('rss','x','mastodon','page','bluesky')")
            db.execute(sql)
            columns = ','.join(row[1] for row in db.execute('PRAGMA table_info(feeds)'))
            db.execute(f'INSERT INTO feeds_next({columns}) SELECT {columns} FROM feeds')
            db.execute('DROP TABLE feeds')
            db.execute('ALTER TABLE feeds_next RENAME TO feeds')
            db.execute("UPDATE feeds SET enabled=0,error='X 収集は終了しました。Mastodon／Bluesky の SNS 調査へ移行してください。',retry_at=NULL WHERE source_type='x'")
            db.execute("DELETE FROM provider_cooldowns WHERE provider='x'")
            from .social_schema import SCHEMA as social_schema
            for statement in social_schema.split(';'):
                if statement.strip():
                    db.execute(statement)
            db.execute('PRAGMA user_version=15')
        if version < 16:
            from .social_ai_schema import SCHEMA as social_ai_schema
            for statement in social_ai_schema.split(';'):
                if statement.strip():
                    db.execute(statement)
            db.execute('PRAGMA user_version=16')
        if version < 17:
            db.execute('''CREATE TABLE folder_positions (
                folder TEXT PRIMARY KEY NOT NULL CHECK(length(folder)<=80),
                position INTEGER NOT NULL UNIQUE CHECK(position>=0)
            )''')
            db.execute('PRAGMA user_version=17')
        if version < 18:
            from .platform_schema import migrate
            migrate(db)
            db.execute('PRAGMA user_version=18')
        if version < 19:
            db.execute('CREATE TABLE article_visits (article_id INTEGER PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE, visited_at TEXT NOT NULL)')
            db.execute('CREATE INDEX article_visits_time ON article_visits(visited_at DESC,article_id DESC)')
            db.execute('PRAGMA user_version=19')
        if db.execute('PRAGMA foreign_key_check').fetchone():
            raise RuntimeError('Database foreign key integrity check failed')
        db.commit()
        db.execute('PRAGMA foreign_keys=ON')
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
