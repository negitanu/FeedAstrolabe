BEGIN TRANSACTION;
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
 is_starred INTEGER NOT NULL DEFAULT 0 CHECK(is_starred IN (0,1)), source_published_at TEXT,
 UNIQUE(feed_id, guid)
);
CREATE TABLE duplicate_fingerprints (
 evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,kind TEXT NOT NULL,key TEXT NOT NULL,
 PRIMARY KEY(evidence_id,kind)
);
CREATE TABLE duplicate_groups (
 id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,key TEXT NOT NULL,suppressed INTEGER NOT NULL DEFAULT 0 CHECK(suppressed IN (0,1)),
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(kind,key)
);
CREATE TABLE duplicate_members (
 group_id INTEGER NOT NULL REFERENCES duplicate_groups(id) ON DELETE CASCADE,
 evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,PRIMARY KEY(group_id,evidence_id)
);
CREATE TABLE "evidence" (
              id INTEGER PRIMARY KEY AUTOINCREMENT, source_key TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>=1),
              feed_id INTEGER REFERENCES feeds(id) ON DELETE SET NULL,
              article_id INTEGER REFERENCES articles(id) ON DELETE SET NULL,
              source_url TEXT NOT NULL, publisher TEXT NOT NULL, source_guid TEXT NOT NULL,
              title TEXT NOT NULL, method TEXT NOT NULL, published_at TEXT, observed_at TEXT,
              captured_at TEXT NOT NULL, blob_hash TEXT NOT NULL REFERENCES evidence_blobs(hash),
              text_hash TEXT NOT NULL CHECK(length(text_hash)=64), text TEXT NOT NULL CHECK(length(text)<=160000),
              mime TEXT NOT NULL, filename TEXT NOT NULL DEFAULT '',UNIQUE(source_key,version)
            );
CREATE TABLE evidence_blobs (hash TEXT PRIMARY KEY CHECK(length(hash)=64),size INTEGER NOT NULL CHECK(size BETWEEN 0 AND 10485760));
CREATE TABLE evidence_capture_errors (feed_id INTEGER PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE,message TEXT NOT NULL,occurred_at TEXT NOT NULL);
CREATE TABLE evidence_settings (id INTEGER PRIMARY KEY CHECK(id=1),quota_bytes INTEGER NOT NULL DEFAULT 524288000 CHECK(quota_bytes BETWEEN 10485760 AND 10737418240),retention_days INTEGER NOT NULL DEFAULT 90 CHECK(retention_days BETWEEN 1 AND 3650));
INSERT INTO "evidence_settings" VALUES(1,524288000,90);
CREATE TABLE "feeds" (
 id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
 folder TEXT NOT NULL DEFAULT '', etag TEXT, modified TEXT,
 checked_at TEXT, success_at TEXT, error TEXT, created_at TEXT NOT NULL
, enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)), poll_interval INTEGER CHECK(poll_interval BETWEEN 60 AND 86400), failures INTEGER NOT NULL DEFAULT 0, source_type TEXT NOT NULL DEFAULT 'rss' CHECK(source_type IN ('rss','x','mastodon','page')), source_kind TEXT, target TEXT, instance_url TEXT, provider_id TEXT, since_id TEXT, page_cursor TEXT, pending_newest TEXT, retry_at TEXT, selector TEXT, settle_ms INTEGER NOT NULL DEFAULT 1000 CHECK(settle_ms BETWEEN 0 AND 10000), snapshot TEXT, observation_seq INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 0, retention_days INTEGER NOT NULL DEFAULT 90 CHECK(retention_days BETWEEN 1 AND 365));
CREATE TABLE note_evidence (note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,PRIMARY KEY(note_id,evidence_id));
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
CREATE TABLE quotations (id INTEGER PRIMARY KEY,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,text_hash TEXT NOT NULL,start INTEGER NOT NULL,end INTEGER NOT NULL,quote TEXT NOT NULL CHECK(length(quote) BETWEEN 1 AND 10000),created_at TEXT NOT NULL,CHECK(start>=0 AND end>start),UNIQUE(workspace_id,evidence_id,start,end,note_id));
CREATE TABLE settings (
              id INTEGER PRIMARY KEY CHECK(id=1), poll_interval INTEGER NOT NULL DEFAULT 900,
              polling_enabled INTEGER NOT NULL DEFAULT 1, page_size INTEGER NOT NULL DEFAULT 30,
              default_view TEXT NOT NULL DEFAULT 'all', api_rate_limit INTEGER NOT NULL DEFAULT 120
            );
INSERT INTO "settings" VALUES(1,900,1,30,'all',120);
CREATE TABLE tags (id INTEGER PRIMARY KEY,name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(name) BETWEEN 1 AND 80));
CREATE TABLE triage_state (id INTEGER PRIMARY KEY CHECK(id=1),cursor INTEGER NOT NULL DEFAULT 0);
INSERT INTO "triage_state" VALUES(1,0);
CREATE TABLE watch_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,version_id INTEGER NOT NULL REFERENCES watchlist_versions(id) ON DELETE CASCADE,
 evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,included INTEGER NOT NULL CHECK(included IN (0,1)),
 explanation TEXT NOT NULL,seen INTEGER NOT NULL DEFAULT 0 CHECK(seen IN (0,1)),created_at TEXT NOT NULL,
 UNIQUE(version_id,evidence_id)
);
CREATE TABLE watchlist_versions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL,query TEXT NOT NULL,exclusion TEXT NOT NULL,priority TEXT NOT NULL CHECK(priority IN ('low','normal','high','critical')),
 reason TEXT NOT NULL,cursor INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,UNIQUE(watchlist_id,revision)
);
CREATE TABLE watchlists (
 id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 120),kind TEXT NOT NULL CHECK(kind IN ('watchlist','saved-search')),
 enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),revision INTEGER NOT NULL,last_run TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE TABLE workspace_articles (
              workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
              article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
              PRIMARY KEY(workspace_id,article_id)
            );
CREATE TABLE workspace_evidence (workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,PRIMARY KEY(workspace_id,evidence_id));
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
CREATE INDEX articles_date ON articles(published_at DESC, id DESC);
CREATE INDEX articles_feed ON articles(feed_id);
CREATE INDEX articles_read ON articles(is_read);
CREATE INDEX articles_starred ON articles(is_starred);
CREATE INDEX notes_workspace ON notes(workspace_id,archived,id);
CREATE INDEX workspace_feeds_reverse ON workspace_feeds(feed_id,workspace_id);
CREATE INDEX workspace_articles_reverse ON workspace_articles(article_id,workspace_id);
CREATE INDEX workspace_tags_reverse ON workspace_tags(tag_id,workspace_id);
CREATE INDEX article_tags_reverse ON article_tags(tag_id,article_id);
CREATE INDEX note_tags_reverse ON note_tags(tag_id,note_id);
CREATE INDEX workspace_evidence_reverse ON workspace_evidence(evidence_id);
CREATE INDEX note_evidence_reverse ON note_evidence(evidence_id);
CREATE INDEX quotations_evidence ON quotations(evidence_id);
CREATE INDEX evidence_source ON evidence(source_key,id DESC);
CREATE INDEX evidence_article ON evidence(article_id,id DESC);
CREATE INDEX watchlists_schedule ON watchlists(enabled,last_run,id);
CREATE INDEX watchlists_workspace ON watchlists(workspace_id,id);
CREATE INDEX watch_events_evidence ON watch_events(evidence_id);
CREATE INDEX watch_events_date ON watch_events(created_at,id);
CREATE INDEX duplicate_fingerprints_key ON duplicate_fingerprints(kind,key,evidence_id);
CREATE INDEX duplicate_members_evidence ON duplicate_members(evidence_id);
CREATE INDEX evidence_text_hash ON evidence(text_hash);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('evidence',0);
COMMIT;
PRAGMA user_version=7;
