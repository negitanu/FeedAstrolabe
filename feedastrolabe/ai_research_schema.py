"""Append-only AI research versions, reviewed cards and qualified evaluations."""
SCHEMA='''
CREATE TABLE ai_watches (
 id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 provider TEXT NOT NULL REFERENCES connector_settings(provider),target TEXT NOT NULL,term TEXT NOT NULL DEFAULT '',
 outbound_public INTEGER NOT NULL DEFAULT 0 CHECK(outbound_public IN(0,1)),enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN(0,1)),
 interval_seconds INTEGER NOT NULL DEFAULT 86400 CHECK(interval_seconds BETWEEN 3600 AND 604800),revision INTEGER NOT NULL DEFAULT 1,
 page INTEGER NOT NULL DEFAULT 0 CHECK(page BETWEEN 0 AND 19),next_check TEXT NOT NULL,last_processed_at TEXT,last_success_at TEXT,last_cache_signature TEXT,truncated INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(workspace_id,provider,target,term)
);
CREATE TABLE ai_versions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,watch_id INTEGER NOT NULL REFERENCES ai_watches(id) ON DELETE CASCADE,
 record_id TEXT NOT NULL,version TEXT NOT NULL,projection_hash TEXT NOT NULL,response_hash TEXT NOT NULL,
 payload TEXT NOT NULL,source_url TEXT NOT NULL,source_version TEXT NOT NULL,observed_at TEXT NOT NULL,
 evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,UNIQUE(watch_id,record_id,projection_hash)
);
CREATE INDEX ai_versions_watch ON ai_versions(watch_id,id);
CREATE TABLE ai_cards (
 id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,version TEXT NOT NULL,
 quotation_id INTEGER NOT NULL REFERENCES quotations(id) ON DELETE RESTRICT,claims TEXT NOT NULL,
 author TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE INDEX ai_cards_case ON ai_cards(workspace_id,id);
CREATE TABLE ai_links (
 id INTEGER PRIMARY KEY AUTOINCREMENT,card_id INTEGER NOT NULL REFERENCES ai_cards(id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN('paper','repository','model-card')),url TEXT NOT NULL,
 version_id INTEGER REFERENCES ai_versions(id) ON DELETE RESTRICT,quotation_id INTEGER NOT NULL REFERENCES quotations(id) ON DELETE RESTRICT,
 author TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(card_id,kind,url,quotation_id)
);
CREATE TABLE ai_benchmarks (
 id INTEGER PRIMARY KEY AUTOINCREMENT,card_id INTEGER NOT NULL REFERENCES ai_cards(id) ON DELETE CASCADE,
 status TEXT NOT NULL CHECK(status IN('claimed','reproduced','unverified')),conditions TEXT NOT NULL,
 result TEXT NOT NULL,notes TEXT NOT NULL,quotation_id INTEGER REFERENCES quotations(id) ON DELETE RESTRICT,
 author TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE INDEX ai_benchmarks_card ON ai_benchmarks(card_id,id);
'''
