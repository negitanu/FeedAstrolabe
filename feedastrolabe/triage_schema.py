"""Additive workspace triage persistence (schema seven)."""
SCHEMA = """
CREATE TABLE watchlists (
 id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 120),kind TEXT NOT NULL CHECK(kind IN ('watchlist','saved-search')),
 enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),revision INTEGER NOT NULL,last_run TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE INDEX watchlists_schedule ON watchlists(enabled,last_run,id);
CREATE INDEX watchlists_workspace ON watchlists(workspace_id,id);
CREATE TABLE watchlist_versions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL,query TEXT NOT NULL,exclusion TEXT NOT NULL,priority TEXT NOT NULL CHECK(priority IN ('low','normal','high','critical')),
 reason TEXT NOT NULL,cursor INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,UNIQUE(watchlist_id,revision)
);
CREATE TABLE watch_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,version_id INTEGER NOT NULL REFERENCES watchlist_versions(id) ON DELETE CASCADE,
 evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,included INTEGER NOT NULL CHECK(included IN (0,1)),
 explanation TEXT NOT NULL,seen INTEGER NOT NULL DEFAULT 0 CHECK(seen IN (0,1)),created_at TEXT NOT NULL,
 UNIQUE(version_id,evidence_id)
);
CREATE INDEX watch_events_evidence ON watch_events(evidence_id);
CREATE INDEX watch_events_date ON watch_events(created_at,id);
CREATE TABLE duplicate_fingerprints (
 evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,kind TEXT NOT NULL,key TEXT NOT NULL,
 PRIMARY KEY(evidence_id,kind)
);
CREATE INDEX duplicate_fingerprints_key ON duplicate_fingerprints(kind,key,evidence_id);
CREATE TABLE duplicate_groups (
 id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,key TEXT NOT NULL,suppressed INTEGER NOT NULL DEFAULT 0 CHECK(suppressed IN (0,1)),
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(kind,key)
);
CREATE TABLE duplicate_members (
 group_id INTEGER NOT NULL REFERENCES duplicate_groups(id) ON DELETE CASCADE,
 evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,PRIMARY KEY(group_id,evidence_id)
);
CREATE INDEX duplicate_members_evidence ON duplicate_members(evidence_id);
CREATE TABLE triage_state (id INTEGER PRIMARY KEY CHECK(id=1),cursor INTEGER NOT NULL DEFAULT 0);
INSERT INTO triage_state(id) VALUES(1);
CREATE INDEX evidence_text_hash ON evidence(text_hash);
"""
