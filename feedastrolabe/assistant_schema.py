"""Exact input snapshots, conservative reservations and independent review revisions."""
SCHEMA='''
CREATE TABLE assistant_profiles (
 id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN('local','cloud')),model TEXT NOT NULL,
 model_digest TEXT,enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN(0,1)),revision INTEGER NOT NULL DEFAULT 1,
 max_output_tokens INTEGER NOT NULL DEFAULT 512,daily_calls INTEGER NOT NULL DEFAULT 10,
 input_rate INTEGER,output_rate INTEGER,price_date TEXT,max_cost INTEGER NOT NULL DEFAULT 100000,daily_cost INTEGER NOT NULL DEFAULT 1000000,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE TABLE assistant_previews (
 id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 profile_id INTEGER NOT NULL REFERENCES assistant_profiles(id) ON DELETE RESTRICT,profile_revision INTEGER NOT NULL,
 mode TEXT NOT NULL,question TEXT NOT NULL,input TEXT NOT NULL,input_hash TEXT NOT NULL,anchors TEXT NOT NULL,
 input_token_bound INTEGER NOT NULL,reserved_cost INTEGER NOT NULL,prompt_hash TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TABLE assistant_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,preview_id INTEGER NOT NULL UNIQUE REFERENCES assistant_previews(id) ON DELETE RESTRICT,
 status TEXT NOT NULL CHECK(status IN('queued','running','success','failed')),result TEXT,error TEXT,
 model_lineage TEXT,usage TEXT,cost_estimate INTEGER,review_revision INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL,finished_at TEXT
);
CREATE TABLE assistant_budget (
 profile_id INTEGER NOT NULL REFERENCES assistant_profiles(id) ON DELETE CASCADE,day TEXT NOT NULL,calls INTEGER NOT NULL DEFAULT 0,reserved_cost INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(profile_id,day)
);
CREATE TABLE assistant_review_versions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,job_id INTEGER NOT NULL REFERENCES assistant_jobs(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN('reviewed','rejected','draft')),text TEXT NOT NULL,author TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(job_id,revision)
);
CREATE TABLE assistant_sources (
 preview_id INTEGER NOT NULL REFERENCES assistant_previews(id) ON DELETE CASCADE,evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,
 PRIMARY KEY(preview_id,evidence_id)
);
CREATE INDEX assistant_job_status ON assistant_jobs(status,id);
'''
