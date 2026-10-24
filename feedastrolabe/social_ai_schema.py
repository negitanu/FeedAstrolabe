"""Optional public social importance extraction and conservative daily budgets."""
SCHEMA = '''
ALTER TABLE social_topics ADD COLUMN ai_enabled INTEGER NOT NULL DEFAULT 0 CHECK(ai_enabled IN (0,1));
ALTER TABLE social_topics ADD COLUMN ai_criteria TEXT NOT NULL DEFAULT '' CHECK(length(ai_criteria)<=500);
ALTER TABLE social_topics ADD COLUMN ai_revision INTEGER NOT NULL DEFAULT 1;
CREATE TABLE social_ai_config (
 id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
 model TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 1,
 max_output_tokens INTEGER NOT NULL DEFAULT 2048 CHECK(max_output_tokens BETWEEN 256 AND 4096),
 daily_calls INTEGER NOT NULL DEFAULT 24 CHECK(daily_calls BETWEEN 1 AND 100),
 input_rate INTEGER NOT NULL DEFAULT 1000000 CHECK(input_rate BETWEEN 0 AND 100000000),
 output_rate INTEGER NOT NULL DEFAULT 3000000 CHECK(output_rate BETWEEN 0 AND 100000000),
 max_cost INTEGER NOT NULL DEFAULT 100000 CHECK(max_cost BETWEEN 1 AND 10000000),
 daily_cost INTEGER NOT NULL DEFAULT 1000000 CHECK(daily_cost BETWEEN 1 AND 100000000),
 cooldown_until TEXT
);
INSERT INTO social_ai_config(id) VALUES(1);
CREATE TABLE social_ai_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 feed_id INTEGER NOT NULL REFERENCES social_topics(feed_id) ON DELETE CASCADE,
 run_id INTEGER NOT NULL REFERENCES social_runs(id) ON DELETE CASCADE,
 config_revision INTEGER NOT NULL,topic_revision INTEGER NOT NULL,
 automatic INTEGER NOT NULL CHECK(automatic IN (0,1)),
 status TEXT NOT NULL CHECK(status IN ('queued','running','success','failed')),
 input TEXT NOT NULL,input_hash TEXT NOT NULL,sources TEXT NOT NULL,
 input_token_bound INTEGER NOT NULL,reserved_cost INTEGER NOT NULL,
 result TEXT,error TEXT,usage TEXT,lineage TEXT,actual_cost INTEGER,
 created_at TEXT NOT NULL,finished_at TEXT,
 UNIQUE(run_id,config_revision,topic_revision)
);
CREATE INDEX social_ai_jobs_feed ON social_ai_jobs(feed_id,id DESC);
CREATE INDEX social_ai_jobs_status ON social_ai_jobs(status,id);
CREATE TABLE social_ai_budget (
 day TEXT PRIMARY KEY,calls INTEGER NOT NULL DEFAULT 0 CHECK(calls>=0),
 reserved_cost INTEGER NOT NULL DEFAULT 0 CHECK(reserved_cost>=0)
);
'''
