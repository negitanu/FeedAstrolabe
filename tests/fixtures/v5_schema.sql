CREATE TABLE api_keys (
              id INTEGER PRIMARY KEY, name TEXT NOT NULL, prefix TEXT NOT NULL,
              token_hash TEXT NOT NULL UNIQUE, scope TEXT NOT NULL CHECK(scope IN ('read','write')),
              created_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT, last_used_at TEXT,
              rate_window INTEGER NOT NULL DEFAULT 0, rate_count INTEGER NOT NULL DEFAULT 0
            );
CREATE TABLE article_tags (
              article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
              tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,PRIMARY KEY(article_id,tag_id)
            );
CREATE TABLE articles (
 id INTEGER PRIMARY KEY, feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
 guid TEXT NOT NULL, title TEXT NOT NULL, link TEXT NOT NULL DEFAULT '',
 content TEXT NOT NULL, search_text TEXT NOT NULL, published_at TEXT NOT NULL,
 is_read INTEGER NOT NULL DEFAULT 0 CHECK(is_read IN (0,1)),
 is_starred INTEGER NOT NULL DEFAULT 0 CHECK(is_starred IN (0,1)),
 UNIQUE(feed_id, guid)
);
CREATE TABLE "feeds" (
 id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
 folder TEXT NOT NULL DEFAULT '', etag TEXT, modified TEXT,
 checked_at TEXT, success_at TEXT, error TEXT, created_at TEXT NOT NULL
, enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)), poll_interval INTEGER CHECK(poll_interval BETWEEN 60 AND 86400), failures INTEGER NOT NULL DEFAULT 0, source_type TEXT NOT NULL DEFAULT 'rss' CHECK(source_type IN ('rss','x','mastodon','page')), source_kind TEXT, target TEXT, instance_url TEXT, provider_id TEXT, since_id TEXT, page_cursor TEXT, pending_newest TEXT, retry_at TEXT, selector TEXT, settle_ms INTEGER NOT NULL DEFAULT 1000 CHECK(settle_ms BETWEEN 0 AND 10000), snapshot TEXT, observation_seq INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 0, retention_days INTEGER NOT NULL DEFAULT 90 CHECK(retention_days BETWEEN 1 AND 365));
CREATE TABLE note_revisions (
              note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
              revision INTEGER NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, label TEXT NOT NULL,
              archived INTEGER NOT NULL CHECK(archived IN (0,1)), created_at TEXT NOT NULL,
              PRIMARY KEY(note_id,revision)
            );
CREATE TABLE note_tags (
              note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
              tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,PRIMARY KEY(note_id,tag_id)
            );
CREATE TABLE notes (
              id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
              body TEXT NOT NULL DEFAULT '' CHECK(length(body)<=100000),
              label TEXT NOT NULL DEFAULT 'hypothesis' CHECK(label IN ('fact','source-claim','hypothesis')),
              archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
              revision INTEGER NOT NULL CHECK(revision>=1), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
CREATE TABLE page_jobs (feed_id INTEGER PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE,requested_at TEXT NOT NULL);
CREATE TABLE provider_cooldowns (provider TEXT PRIMARY KEY, retry_at TEXT NOT NULL);
CREATE TABLE settings (
              id INTEGER PRIMARY KEY CHECK(id=1), poll_interval INTEGER NOT NULL DEFAULT 900,
              polling_enabled INTEGER NOT NULL DEFAULT 1, page_size INTEGER NOT NULL DEFAULT 30,
              default_view TEXT NOT NULL DEFAULT 'all', api_rate_limit INTEGER NOT NULL DEFAULT 120
            );
CREATE TABLE tags (id INTEGER PRIMARY KEY,name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(name) BETWEEN 1 AND 80));
CREATE TABLE workspace_articles (
              workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
              PRIMARY KEY(workspace_id,article_id)
            );
CREATE TABLE workspace_feeds (
              workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
              PRIMARY KEY(workspace_id,feed_id)
            );
CREATE TABLE workspace_tags (
              workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,PRIMARY KEY(workspace_id,tag_id)
            );
CREATE TABLE workspaces (
              id INTEGER PRIMARY KEY, title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
              purpose TEXT NOT NULL DEFAULT '' CHECK(length(purpose)<=10000),
              questions TEXT NOT NULL DEFAULT '' CHECK(length(questions)<=10000),
              status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused','completed')),
              classification TEXT NOT NULL DEFAULT 'internal' CHECK(classification IN ('public','internal','restricted')),
              archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
CREATE INDEX article_tags_reverse ON article_tags(tag_id,article_id);
CREATE INDEX articles_date ON articles(published_at DESC, id DESC);
CREATE INDEX articles_feed ON articles(feed_id);
CREATE INDEX articles_read ON articles(is_read);
CREATE INDEX articles_starred ON articles(is_starred);
CREATE INDEX note_tags_reverse ON note_tags(tag_id,note_id);
CREATE INDEX notes_workspace ON notes(workspace_id,archived,id);
CREATE INDEX workspace_articles_reverse ON workspace_articles(article_id,workspace_id);
CREATE INDEX workspace_feeds_reverse ON workspace_feeds(feed_id,workspace_id);
CREATE INDEX workspace_tags_reverse ON workspace_tags(tag_id,workspace_id);
PRAGMA user_version=5;
