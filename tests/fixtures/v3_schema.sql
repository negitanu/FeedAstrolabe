BEGIN TRANSACTION;
CREATE TABLE api_keys (
              id INTEGER PRIMARY KEY, name TEXT NOT NULL, prefix TEXT NOT NULL,
              token_hash TEXT NOT NULL UNIQUE, scope TEXT NOT NULL CHECK(scope IN ('read','write')),
              created_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT, last_used_at TEXT,
              rate_window INTEGER NOT NULL DEFAULT 0, rate_count INTEGER NOT NULL DEFAULT 0
            );
CREATE TABLE articles (
 id INTEGER PRIMARY KEY, feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
 guid TEXT NOT NULL, title TEXT NOT NULL, link TEXT NOT NULL DEFAULT '',
 content TEXT NOT NULL, search_text TEXT NOT NULL, published_at TEXT NOT NULL,
 is_read INTEGER NOT NULL DEFAULT 0 CHECK(is_read IN (0,1)),
 is_starred INTEGER NOT NULL DEFAULT 0 CHECK(is_starred IN (0,1)),
 UNIQUE(feed_id, guid)
);
CREATE TABLE feeds (
 id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
 folder TEXT NOT NULL DEFAULT '', etag TEXT, modified TEXT,
 checked_at TEXT, success_at TEXT, error TEXT, created_at TEXT NOT NULL
, enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)), poll_interval INTEGER CHECK(poll_interval BETWEEN 60 AND 86400), failures INTEGER NOT NULL DEFAULT 0, source_type TEXT NOT NULL DEFAULT 'rss' CHECK(source_type IN ('rss','x','mastodon')), source_kind TEXT, target TEXT, instance_url TEXT, provider_id TEXT, since_id TEXT, page_cursor TEXT, pending_newest TEXT, retry_at TEXT);
CREATE TABLE provider_cooldowns (provider TEXT PRIMARY KEY, retry_at TEXT NOT NULL);
CREATE TABLE settings (
              id INTEGER PRIMARY KEY CHECK(id=1), poll_interval INTEGER NOT NULL DEFAULT 900,
              polling_enabled INTEGER NOT NULL DEFAULT 1, page_size INTEGER NOT NULL DEFAULT 30,
              default_view TEXT NOT NULL DEFAULT 'all', api_rate_limit INTEGER NOT NULL DEFAULT 120
            );
INSERT INTO "settings" VALUES(1,900,1,30,'all',120);
CREATE INDEX articles_date ON articles(published_at DESC, id DESC);
CREATE INDEX articles_feed ON articles(feed_id);
CREATE INDEX articles_read ON articles(is_read);
CREATE INDEX articles_starred ON articles(is_starred);
COMMIT;
PRAGMA user_version=3;
